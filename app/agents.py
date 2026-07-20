import json
import re

from app import router, tools
from app.kb import index_resolved
from app.pii import scan
from app.state import public_messages

MAX_STEPS = 8


def _parse(raw: str) -> dict:
    # same trick as graph.py: grab the first {...} block the model emitted
    s, e = raw.find("{"), raw.rfind("}")
    return json.loads(raw[s : e + 1])


CLASSIFY_SYSTEM = """
You are the Classification and Prioritization agent for customer support.
Decide the ticket's category, priority, business_impact, sentiment, difficulty, and whether it is sensitive.
You MAY look the customer up first to inform priority (a premium customer, or money at stake, raises it).

Tool available:
  crm_lookup(email) -> the customer's record (tier, order history) or null
Do not repeat a tool call you already made. If crm_lookup returns null the customer is not in our records, so do not call it again; classify from the ticket text.

Reply every turn with ONE JSON object, nothing else.
  To use the tool:  {"thought": "...", "action": "crm_lookup", "args": {"email": "<email>"}}
  To finish:        {"thought": "...", "action": "finish", "result": {"category": "...", "priority": "...", "business_impact": "...", "sentiment": "...", "difficulty": "...", "sensitive": true}}

Definitions:
  category:        [billing, technical, account, general, shipping, refund, feature_request, complaint]
  priority:        [Critical, High, Medium, Low]
  business_impact: [low, medium, high]
  sentiment:       [positive, neutral, negative]
  difficulty:      simple = a routine self-serve request a KB article answers in one step (password reset, order status).
                   complex = needs judgement, multiple steps, investigation, or careful handling (angry refund, account recovery, vague "nothing works", anything with money or a frustrated customer).
  sensitive:       true if the ticket contains or discusses sensitive data (financial/card/bank, government ID, health, passwords/2FA, legal matters, protected personal traits), else false.
"""


def classify_agent(ticket) -> dict:
    context = f"Ticket:\n from: {ticket.customer_name} <{ticket.customer_email}>\n  subject: {ticket.subject}\n body:{ticket.body}"

    transcript = ""

    for _ in range(MAX_STEPS):
        prompt = f"{CLASSIFY_SYSTEM}\n\n {context}\n{transcript}\nYour JSON:"
        move = _parse(router.think(prompt, max_new_tokens=512))
        if move.get("action") == "finish":
            return move["result"]

        # else it's a tool call: run it, feed the result back into the loop
        obs = tools.run_tool(move.get("action"), move.get("args", {}))
        transcript += f"\nYou called {move.get('action')} ({move.get('args', {})}) -> {obs}"

    # fallback: it never finished in MAX_STEPS return a safe default
    return {"category": "general", "priority": "Medium", "business_impact": "medium", "sentiment": "neutral", "difficulty": "simple", "sensitive": False}


RETRIEVE_SYSTEM = """
You are the Knowledge Retrieval agent for customer support.
Find the knowledge-base articles most relevant to solving this ticket.
You may search more than once, refining the query, until you have good coverage.
Do not repeat a query you already ran. As soon as a search gives results you can use, finish.

Tool available:
  kb_search(query) -> a ranked list of articles, each {title, score}

Reply every turn with ONE JSON object, nothing else.
  To search:  {"thought": "...", "action": "kb_search", "args": {"query": "<query>"}}
  To finish:  {"thought": "...", "action": "finish", "result": {"relevant_titles": ["<title>", ...]}}
Search at least once before finishing. Keep only titles that genuinely help.
"""


def retrieve_agent(ticket, lane="private", level="complex") -> list:
    context = f"Ticket:\n subject: {ticket.subject}\n body:{ticket.body}"
    transcript = ""
    seen = {}  # title -> full article dict
    for _ in range(MAX_STEPS):
        prompt = f"{RETRIEVE_SYSTEM}\n\n{context}\n{transcript}\nYOUR JSON:"
        move = _parse(router.think(prompt, max_new_tokens=512, lane=lane, level=level))
        if move.get("action") == "finish":
            titles = move["result"].get("relevant_titles", [])
            chosen = [seen[t] for t in titles if t in seen]
            return chosen or list(seen.values())
        if move.get("action") == "kb_search":
            hits = tools.kb_search(move.get("args", {}).get("query", ""))
            for h in hits:
                seen[h["title"]] = h
            summary = [{"title": h["title"], "score": h["score"]} for h in hits]
            transcript += f"\nkb_search({move['args']}) -> {summary}"
        else:
            transcript += f"\nunknown action {move.get('action')!r}"
    return list(seen.values())


GENERATE_SYSTEM = """
You are the Response Generation agent for Nimbus customer support.
Decide how to handle this ticket, gathering any context you need first.
You are shown the knowledge-base articles our retrieval already found (in the context below). Read them before you decide.

Tools available (call the ones you need before deciding):
  crm_lookup(email)            -> customer record (tier, plan, account status) or null
  order_lookup(order_id)       -> one order by its id (status, tracking)
  orders_by_email(email)       -> all of this customer's orders (use when no order id was given)
  billing_history(email)       -> this customer's charges
  subscription_details(email)  -> plan and subscription status
  account_status(email)        -> account state and tier
  past_tickets(email)          -> this customer's earlier resolved tickets
  service_status()             -> current known incidents or outages
  refund_eligibility(email)    -> whether a refund is within the 30-day window
  request_refund(order_id)     -> prepare a refund for a human to approve (use only after checking eligibility)
  cancel_subscription(email)   -> start a cancellation; it returns a code the customer must reply with to confirm
Do not repeat a tool call you already made. Once you have what you need, finish.

Use these tools to ANSWER instead of escalating: look up the order, charge, or account and tell the customer what you find.
Before you escalate, gather context with the tools and read the conversation and KB articles. Escalate only if, even then, you still cannot help.
To act on money or a subscription, call request_refund or cancel_subscription, then answer telling the customer it has been submitted for processing.
If the customer replied with a confirmation code, call cancel_subscription again with that code to confirm.

Choose one outcome:
  answer   - we can reply helpfully (from the KB, the tools, or both). PREFER THIS whenever you have enough to help.
  question - a key detail is missing; ask the customer for exactly that. PREFER THIS over escalate when the missing thing is something the customer can give you.
  escalate - ONLY if you genuinely cannot help and a human is required. Not just because the ticket is important or the customer is upset.

Reply every turn with ONE JSON object, nothing else.
  To use a tool: {"thought":"...","action":"<tool>","args":{...}}
  To finish:     {"thought":"...","action":"finish","result":{"kind":"answer|question|escalate","confidence":<0-100>,"notes":"<what to say, including any facts you found; or what is missing; or why escalate>"}}
confidence = 0-100, how sure you are the answer is correct AND complete. Be honest.
"""


def _write_reply(ticket, articles, customer, notes, lane, tier, convo="") -> str:
    kb_text = "\n\n".join(f"[{a['title']}]\n{a['content']}" for a in articles)
    greeting = f"Hi {ticket.customer_name.split()[0]}," if ticket.customer_name else "Hi there,"
    cust = f"tier={customer['tier']}, plan={customer['plan']}" if customer else "no customer record found"
    prompt = f"""
    You are a warm, helpful customer support agent. Write a reply to this ticket.
    Customer: {cust}
    Subject: {ticket.subject}
    Body: {ticket.body}
    Internal context to use when answering (NEVER mention this, the word 'triage', 'guidance', 'notes', or any internal team to the customer): {notes}
    Conversation so far (oldest first):
    {convo}
    The last line above is the customer's latest message. Reply to that, using the earlier turns for context. Do not repeat a solution you already gave, and do not contradict an earlier reply.
    Use the guidance from triage above and these knowledge base articles. Do not invent details beyond what they contain:
    {kb_text}
    Open with exactly "{greeting}" and sign off as 'The Nimbus Support Team'. No placeholders like [NAME.
    """
    return router.generate_reply(prompt, lane, tier)


def generate_agent(ticket, articles, lane="cloud", tier="complex", history=None) -> dict:
    convo = "\n".join(f"{'Customer' if m['role'] == 'customer' else 'Support'}: {m['body']}" for m in public_messages(history))
    kb_preview = "\n".join(f"- {a['title']}: {a.get('content', '')[:200]}" for a in articles) or "(retrieval returned no articles)"
    context = (
        f"Ticket:\n from: {ticket.customer_name} <{ticket.customer_email}>\n"
        f"  subject: {ticket.subject}\n body: {ticket.body}\n"
        f"Conversation so far (oldest first):\n{convo}\n"
        f"Knowledge-base articles retrieved for this ticket:\n{kb_preview}"
    )
    transcript, customer, proposed, calls = "", None, None, []
    cache, redundant = {}, 0  # the 14B re-calls the same tool forever; block repeats and force a decision
    for step in range(MAX_STEPS):
        # once we have enough context, or the model starts repeating, demand a decision instead of more tools
        must_finish = len(cache) >= 4 or redundant >= 2 or step >= MAX_STEPS - 1
        hint = "\nSTOP calling tools. You have enough context now. Reply ONLY with the finish JSON." if must_finish else ""
        move = _parse(router.think(f"{GENERATE_SYSTEM}\n\n{context}\n{transcript}{hint}\nYour JSON:", max_new_tokens=512))
        action = move.get("action")
        if action == "finish":
            r = move["result"]
            kind = r.get("kind", "escalate")
            conf = r.get("confidence")
            diag = {"tools_called": calls, "steps": step + 1, "finished": True}
            if kind == "escalate":
                return {"kind": "escalate", "reply": "", "confidence": conf, "proposed_action": proposed, **diag}
            reply = _write_reply(ticket, articles, customer, r.get("notes", ""), lane, tier, convo)
            return {"kind": kind, "reply": reply.strip(), "confidence": conf, "proposed_action": proposed, **diag}
        args = move.get("args", {}) or {}
        if action != "crm_lookup" and action not in tools.TOOLS:
            transcript += f"\nunknown action {action!r}"
            continue
        key = f"{action}:{json.dumps(args, sort_keys=True)}"
        if key in cache:  # already called with these args: block the repeat, push toward finishing
            redundant += 1
            transcript += f"\n{action} already called; its result is above. Do not repeat it, decide now."
            continue
        if action == "crm_lookup":
            calls.append("crm_lookup")
            customer = tools.crm_lookup(**args)
            cache[key] = customer
            transcript += f"\ncrm_lookup -> {customer}"
        else:
            calls.append(action)
            targs = dict(args)
            if action == "cancel_subscription":
                targs["ticket_id"] = ticket.ticket_id  # injected; the model never provides it
            obs = tools.run_tool(action, targs)
            cache[key] = obs
            transcript += f"\n{action}({args}) -> {obs}"
            if action in ("request_refund", "cancel_subscription"):
                proposed = {"tool": action, "args": args, "result": obs}
    # fallback: still no decision after all that -> escalate (should now be rare)
    return {"kind": "escalate", "reply": "", "confidence": None, "proposed_action": proposed,
            "tools_called": calls, "steps": MAX_STEPS, "finished": False}


REVIEW_SYSTEM = """
You are the Compliance and Quality Review agent for customer support.
Check the draft reply against the policy rules AND for factual accuracy.
You MAY look the customer up to verify any claim the reply makes about their account or orders.

Tools available for fact-checking:
  crm_lookup(email)        -> customer record (tier, plan, account status) or null
  order_lookup(order_id)   -> an order's status and tracking
  billing_history(email)   -> the customer's charges

Reply every turn with ONE JSON object, nothing else.
  To use a tool: {"thought":"...","action":"<tool>","args":{...}}
  To finish:       {"thought":"...","action":"finish","result":{"verdict":"pass|fail","issues":["<reason>", ...]}}
FAIL if the reply breaks a policy rule, or states something about the customer's account/orders
that the CRM contradicts. Asking the customer for information is allowed and PASSES. When unsure, PASS.
"""


def review_agent(ticket, draft_reply, lane="private", level="complex") -> dict:
    # deterministic safety checks (always run, never optional)
    issues = []
    if re.search(r"\[[A-Za-z0-9 _/]+\]", draft_reply):
        issues.append("contains an unfilled placeholder in square brackets")
    if "Support Team" not in draft_reply:
        issues.append("missing the Nimbus Support Team sign-off")
    leaked = scan(draft_reply)
    if leaked:
        issues.append("reply exposes PII: " + ", ".join(leaked))

    # autonomous policy + fact-check pass
    with open("policy.md") as f:
        policy = f.read()
    context = f"Customer email: {ticket.customer_email}\nTicket: {ticket.subject} - {ticket.body}\nDraft reply to check:\n{draft_reply}"
    transcript = ""
    for _ in range(MAX_STEPS):
        prompt = f"{REVIEW_SYSTEM}\n\nPolicy:\n{policy}\n\n{context}\n{transcript}\nYour JSON:"
        move = _parse(router.think(prompt, max_new_tokens=512, lane=lane, level=level))
        if move.get("action") == "finish":
            if move["result"].get("verdict") == "fail":
                issues.extend(move["result"].get("issues", []))
            break
        action = move.get("action")
        if action in ("crm_lookup", "order_lookup", "billing_history"):
            transcript += f"\n{action} -> {tools.run_tool(action, move.get('args', {}))}"
        else:
            transcript += f"\nunknown action {action!r}"

    return {"verdict": "fail" if issues else "pass", "issues": issues}


LEARN_SYSTEM = """You are the Learning agent for customer support.
A ticket has just been resolved. Decide whether its problem+solution is worth saving to the
knowledge base to help FUTURE tickets. Save ONLY if it is general and reusable (not a one-off,
no personal data, no customer-specific details). If worth saving, write a concise reusable article.

Reply with ONE JSON object, nothing else:
  {"thought":"...", "save": true, "title":"<short general title>", "content":"<concise problem + solution, no personal data>"}
  or
  {"thought":"...", "save": false}
"""


def learn_agent(ticket, draft_reply, resolved: bool) -> dict:
    if not resolved or not draft_reply:
        return {"learned": False, "reason": "ticket not resolved"}
    # autonomous quality gate: is this resolution worth keeping?
    prompt = (
        f"A support ticket was resolved. Decide if its resolution is general and reusable "
        f"enough to help future tickets (not a one-off, no sensitive personal data).\n"
        f"Ticket: {ticket.subject} - {ticket.body}\n"
        f"Resolution: {draft_reply}\n"
        f'Reply with ONE JSON object: {{"thought":"...","save":true}} or {{"thought":"...","save":false}}'
    )
    move = _parse(router.think(prompt, max_new_tokens=256))
    if move.get("save"):
        content = f"Problem: {ticket.body} Resolution: {draft_reply}"
        index_resolved(ticket.subject, content)  # stays a resolved-ticket record, source preserved
        return {"learned": True}
    return {"learned": False, "reason": "not general enough"}
