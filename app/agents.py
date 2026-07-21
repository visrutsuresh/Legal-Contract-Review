from app import router
from app.agents_base import _parse, react
from app.state import valid_finding

CLAUSE_TYPES = {
    "parties",
    "scope",
    "payment",
    "term_termination",
    "confidentiality",
    "ip",
    "liability",
    "indemnity",
    "restraint",
    "data_protection",
    "governing_law",
    "notices",
    "boilerplate",
    "other",
}

CONTRACT_TYPES = {"nda", "msa", "sow", "vendor", "employment"}

EXTRACTION_SYSTEM = """ You are the Clause Extraction agent for Papyrus, a legal contract review product.
You are given the full plain text of ONE contract. Split it into its clauses and pull out the basic facts of the deal. 
Copy clause wording EXACTLY as written: never paraphrase, never summarise, never invent a clause that is not there.

Reply with ONE JSON object, nothing else:
  {"clauses": [
      {"number": "<the clause number as printed, e.g. 4 or
  7.2>",
       "heading": "<the clause heading as printed, or a
  short label if it has none>",
       "text": "<the clause's full original wording, copied
  exactly>",
       "clause_type": "<one label from the list below>"}
    ],
  "parties": ["<each party exactly as named in the contract>"],
 "contract_type": "<one of: nda, msa, sow, vendor, employment>",
 "key_dates": [{"label": "<what the date is, e.g. effective date>", "value": "<the date as written, or none stated>"}]
  }

  clause_type must be EXACTLY one of: parties, scope, payment, term_termination, confidentiality, ip, liability,
  indemnity, restraint, data_protection, governing_law, notices, boilerplate, other
  Use "other" only when nothing on the list fits. Keep the clauses in document order. Every clause of the contract must appear. """


def _clause_rows(move: dict) -> list:
    # turn the model's raw clause list into full Clause dicts, ids in document order
    raw_clauses = move.get("clauses")
    if not isinstance(raw_clauses, list):
        raw_clauses = []
    rows = []
    for c in raw_clauses:
        if not isinstance(c, dict):
            continue
        text = str(c.get("text", "")).strip()
        if not text:
            continue
        ctype = str(c.get("clause_type", "")).strip().lower()
        rows.append(
            {
                "clause_id": "",
                "number": str(c.get("number", "")).strip(),
                "heading": str(c.get("heading", "")).strip(),
                "text": text,
                "clause_type": ctype if ctype in CLAUSE_TYPES else "other",
                "findings": [],
                "proposal": None,
                "decision": None,
                "final_text": text,
            }
        )
    for i, row in enumerate(rows, start=1):
        row["clause_id"] = f"c{i:02d}"
    return rows


def extraction_agent(raw_text: str) -> dict:
    """One structuring read of the whole contract. Not a tool loop: it has no tools to call,
    so it is a single careful call with one repair retry."""
    prompt = f"{EXTRACTION_SYSTEM}\n\nContract text:\n{raw_text}\n\nYour JSON:"
    move, last_err = None, None
    for attempt in range(2):
        ask = prompt if attempt == 0 else (f"{prompt}\n\nYour previous reply was not valid JSON ({last_err}). Reply again with ONE valid JSON object, nothing else.")
        try:
            move = _parse(router.think(ask, max_new_tokens=4096))
            break
        except ValueError as e:  # json.JSONDecodeError is a ValueError
            last_err, move = str(e), None
    if move is None:
        return {"status": "extraction_failed", "error": "The text was readable but could not be split into clauses. A person needs to look at this one."}
    clauses = _clause_rows(move)
    if len(clauses) < 3:
        return {"status": "extraction_failed", "error": f"Only {len(clauses)} clause(s) could be identified. That is too few to review safely; a person needs to look at this one."}
    parties = move.get("parties")
    key_dates = move.get("key_dates")
    return {
        "clauses": clauses,
        "meta": {
            "parties": parties if isinstance(parties, list) else [],
            "contract_type": str(move.get("contract_type", "")).strip().lower(),
            "key_dates": key_dates if isinstance(key_dates, list) else [],
        },
    }


# four inspectors
_INSPECTOR_CODE = {"compliance": "cmp", "risk": "rsk", "template": "tpl", "financial": "fin"}


def _clause_sheet(state: dict) -> str:
    # the whole contract as numbered blocks; findings must echo these exact id
    blocks = []
    for c in state.get("clauses", []):
        blocks.append(f"[{c['clause_id']}] clause {c.get('number', '?')}: {c.get('heading') or 'no heading'}\n{c.get('text', '')}")
    return "\n\n".join(blocks)


def _inspector_context(state: dict) -> str:
    meta = state.get("meta", {})
    parties = ", ".join(meta.get("parties", [])) or "unknown"
    return (
        f"Contract type: {meta.get('contract_type', 'unknown')}\n"
        f"Parties: {parties}\n"
        f"Clauses (use these exact clause_id values):\n\n{_clause_sheet(state)}"
    )


FINDING_RULES = """
<finding> is this exact JSON object, every field filled:
  {"clause_id": "c04", "severity": "high",
   "plain": "You would wait four months to get paid.",
   "term": "Net-120 payment term; the firm standard is net-30.",
   "wrong": "Payment lands 120 days after invoice, four times the firm standard.",
   "change": "Push for net-30 and cash arrives when the work is done.",
   "ignore": "You bank-roll the client for a third of a year on every invoice.",
   "evidence": "within one hundred and twenty (120) days",
   "fix_hint": "net-30"}
Field rules (a finding missing any of these is thrown away unseen):
  clause_id: the [cXX] id from the clause list, exactly as printed there.
  severity:  high, medium or low, lowercase.
  plain:     ONE sentence a non-lawyer feels in their gut. No legal words in it.
  term:      the legal name of the issue, stated second, after plain.
  wrong:     what is wrong with the clause as written.
  change:    what we gain if the other side accepts a change.
  ignore:    what we risk if we sign it unchanged.
  evidence:  a short quote copied word for word from the clause.
  fix_hint:  the wording or number the fix should move to, or null. The ONLY optional field.
Severity guide: high = money or the whole deal at risk, medium = a real but survivable cost, low = untidy but harmless.
Flag only what you can quote evidence for. An empty findings list is a valid answer.
"""


def _stamp(f, name: str, n: int):
    # tag one model finding with its inspector, a stable id, lowercase severity
    if not isinstance(f, dict):
        return None
    f = dict(f)
    f["inspector"] = name
    f["severity"] = str(f.get("severity", "")).lower()
    f["finding_id"] = f"f-{f.get('clause_id', 'unknown')}-{_INSPECTOR_CODE[name]}-{n}"
    return f


def _run_inspector(name: str, system: str, state: dict, allowed: list[str]) -> tuple[dict, dict]:
    # run one inspector to it finish JSON; keep only findings that pass valid-finding
    result = react(system, _inspector_context(state), allowed)
    raw = result.get("findings", []) or []
    kept, dropped = [], 0
    for n, f in enumerate(raw, start=1):
        f = _stamp(f, name, n)
        if f is not None and valid_finding(f):
            kept.append(f)
        else:
            dropped += 1
    note = f"dropped {dropped} invalid finding(s)" if dropped else ""
    update = {
        "findings_raw": kept,
        "inspector_reports": [{"inspector": name, "status": "ok", "note": note}],
        "audit": [f"{name} done"],
    }
    return update, result


def _add_note(update: dict, extra: str) -> None:
    rep = update["inspector_reports"][0]
    rep["note"] = f"{rep['note']}; {extra}" if rep["note"] else extra


COMPLIANCE_SYSTEM = """
You are the Compliance inspector in a legal contract review pipeline.
Your job: find every clause that breaks the firm's rules pack.
Work in this order: call rules_read first, then check every clause against every rule.
Use precedent_search when you want to see how a similar term was handled in a past review.

Tools available:
  rules_read(contract_type)     -> the firm's rules pack, plain markdown text
  precedent_search(query)       -> past reviewed contracts similar to the query, each {title, content, score}
Do not repeat a tool call you already made.

Reply every turn with ONE JSON object, nothing else.
  To use a tool: {"thought": "...", "action": "rules_read", "args": {"contract_type": "<type>"}}
             or: {"thought": "...", "action": "precedent_search", "args": {"query": "<text>"}}
  To finish:     {"thought": "...", "action": "finish", "result": {"findings": [<finding>, ...]}}
""" + FINDING_RULES


def compliance_agent(state: dict) -> dict:
    update, _ = _run_inspector("compliance", COMPLIANCE_SYSTEM, state, ["rules_read", "precedent_search"])
    return update


RISK_SYSTEM = """
You are the Risk inspector in a legal contract review pipeline.
Your job: flag terms that expose our side to serious harm. Look hardest at:
liability (missing or unlimited caps), indemnities that bind only us, termination rights,
auto-renewal, IP ownership transfers, exclusivity or restraint, data-protection duties.
Use template_fetch to see what a safe standard clause looks like, and precedent_search
to see how similar terms were judged in past reviews.

Tools available:
  precedent_search(query)       -> past reviewed contracts similar to the query, each {title, content, score}
  template_fetch(contract_type) -> the firm's standard contract, {"clauses": [{clause_type, heading, standard_text, required}]}
Do not repeat a tool call you already made.

Reply every turn with ONE JSON object, nothing else.
  To use a tool: {"thought": "...", "action": "precedent_search", "args": {"query": "<text>"}}
             or: {"thought": "...", "action": "template_fetch", "args": {"contract_type": "<type>"}}
  To finish:     {"thought": "...", "action": "finish", "result": {"findings": [<finding>, ...], "overall_note": "<ONE plain sentence on the contract's overall risk; optional>"}}
""" + FINDING_RULES


def risk_agent(state: dict) -> dict:
    update, result = _run_inspector("risk", RISK_SYSTEM, state, ["precedent_search", "template_fetch"])
    note = str(result.get("overall_note") or "").strip()
    if note:
        _add_note(update, note)
    return update


TEMPLATE_SYSTEM = """
You are the Template inspector in a legal contract review pipeline.
Your job: compare this contract against the firm's standard template of the same type.
Call template_fetch FIRST; you cannot inspect without the standard. Then report two things:
  1. Deviations: clauses whose terms differ from the standard against us.
     Report each as a finding; set fix_hint to the standard wording or number.
  2. Missing clauses: every template clause marked "required": true that this
     contract does not contain anywhere, listed under "missing".

Tool available:
  template_fetch(contract_type) -> the firm's standard contract, {"clauses": [{clause_type, heading, standard_text, required}]}
Do not repeat a tool call you already made.

Reply every turn with ONE JSON object, nothing else.
  To use the tool: {"thought": "...", "action": "template_fetch", "args": {"contract_type": "<type>"}}
  To finish:       {"thought": "...", "action": "finish", "result": {"findings": [<finding>, ...], "missing": [{"clause_type": "confidentiality", "severity": "medium", "plain": "<ONE sentence a non-lawyer feels>", "term": "<the legal name of the missing clause>", "why_needed": "<what the standard clause protects>"}, ...]}}
A missing entry needs clause_type, severity (high, medium or low, lowercase), plain, term, why_needed.
Do not invent a clause_id for a clause that is not there.
""" + FINDING_RULES


def template_agent(state: dict) -> dict:
    update, result = _run_inspector("template", TEMPLATE_SYSTEM, state, ["template_fetch"])
    raw = result.get("missing", []) or []
    missing = []
    for m in raw:
        if isinstance(m, dict) and str(m.get("severity", "")).lower() in ("high", "medium", "low") and m.get("plain"):
            m = dict(m)
            m["severity"] = str(m["severity"]).lower()
            m["inspector"] = "template"
            missing.append(m)
    if len(missing) < len(raw):
        _add_note(update, f"dropped {len(raw) - len(missing)} bad missing-clause entries")
    update["missing_clauses"] = missing
    return update


FINANCIAL_SYSTEM = """
You are the Financial inspector in a legal contract review pipeline.
Your job: check every money term. Look at payment days, fees and fee increases,
late-payment interest, penalties, liability caps as amounts, currency, and totals.
Do the arithmetic yourself inside your thought (for example 3 years x 12 months x monthly fee)
and flag numbers that do not add up or that hurt us.
Use template_fetch to see the firm's standard money terms for this contract type.

Tool available:
  template_fetch(contract_type) -> the firm's standard contract, {"clauses": [{clause_type, heading, standard_text, required}]}
Do not repeat a tool call you already made.

Reply every turn with ONE JSON object, nothing else.
  To use the tool: {"thought": "...", "action": "template_fetch", "args": {"contract_type": "<type>"}}
  To finish:       {"thought": "...", "action": "finish", "result": {"findings": [<finding>, ...]}}
""" + FINDING_RULES


def financial_agent(state: dict) -> dict:
    update, _ = _run_inspector("financial", FINANCIAL_SYSTEM, state, ["template_fetch"])
    return update
