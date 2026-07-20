import hashlib
from datetime import date

import seed_data
from app import billing, crm, kb, orders, store

TOOLS = {}  # name -> function (the phone book)
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # unambiguous: no 0/O/1/I/L


def tool(fn):
    # Register a function so an agent can call it by name
    TOOLS[fn.__name__] = fn
    return fn


@tool
def crm_lookup(email: str) -> dict | None:
    # Look up a customer by email. Returns their record or None
    return crm.lookup(email)


def run_tool(name: str, args: dict) -> str:
    # Dial a tool by name with its args; return the result as text
    fn = TOOLS.get(name)
    if fn is None:
        return f"ERROR:unknown tool {name!r}"

    try:
        return str(fn(**args))
    except Exception as e:
        return f"ERROR: {e}"


@tool
def kb_search(query: str) -> list:
    # Search the knowledge base + past resolved tickets. Returns ranked articles.
    return kb.search(query)


def _clean(row):
    # make a DB row readable for the agent: decimal -> float, date -> iso string
    if not row:
        return row
    out = {}
    for k, v in row.items():
        if isinstance(v, date):
            out[k] = v.isoformat()
        elif hasattr(v, "__float__") and not isinstance(v, (int, float, bool)):
            out[k] = float(v)  # Decimal
        else:
            out[k] = v
    return out


@tool
def order_lookup(order_id: str):
    # one order by its id (customer quoted a number)
    return _clean(orders.lookup_order(order_id))


@tool
def orders_by_email(email: str):
    # all of a customer's orders (no id given, look them up by who they are)
    return [_clean(o) for o in orders.orders_for(email)]


@tool
def billing_history(email: str):
    return [_clean(c) for c in billing.charges_for(email)]


@tool
def subscription_details(email: str):
    c = crm.lookup(email)
    if not c:
        return None
    return {"plan": c["plan"], "subscription_status": c["subscription_status"], "signup_date": _clean(c)["signup_date"]}


@tool
def account_status(email: str):
    c = crm.lookup(email)
    return None if not c else {"account_status": c["account_status"], "tier": c["tier"]}


@tool
def past_tickets(email: str):
    return store.past_tickets(email)


@tool
def service_status():
    return seed_data.SERVICE_INCIDENTS


@tool
def refund_eligibility(email: str):
    # eligible if the customer's most recent order or charge is inside the refund window
    win, today = seed_data.REFUND_WINDOW_DAYS, seed_data.TODAY
    dates = [o["ordered_at"] for o in orders.orders_for(email)] + [c["charged_at"] for c in billing.charges_for(email)]
    if not dates:
        return {"eligible": False, "reason": "no orders or charges on file"}
    days = (today - max(dates)).days
    return {"eligible": days <= win, "days_since_last_purchase": days, "window_days": win}


def _confirm_code(ticket_id: str) -> str:
    # deterministic 5 char code per ticket; recomputable, so we verify without storing it
    digest = hashlib.sha256(ticket_id.encode()).digest()
    return "".join(_CODE_ALPHABET[b % len(_CODE_ALPHABET)] for b in digest[:5])


@tool
def request_refund(order_id: str):
    # option A: prepare a refund for a human to approve; does NOT move money
    o = orders.lookup_order(order_id)
    if not o:
        return {"status": "error", "message": f"no order {order_id} on file"}
    o = _clean(o)
    return {"status": "prepared", "order_id": order_id, "amount": o["amount"], "message": f"Refund of {o['amount']} for order {order_id} prepared for agent approval."}


@tool
def cancel_subscription(email: str, ticket_id: str, code: str = ""):
    # two-phase: first call issues a confirm code; a matching code confirms. Does NOT cancel live.
    expected = _confirm_code(ticket_id)
    if code.strip().upper() == expected:
        return {"status": "cancellation_confirmed", "email": email, "message": "Cancellation confirmed and queued for processing."}
    return {"status": "awaiting_confirmation", "confirm_code": expected, "message": f"Ask the customer to reply with the exact code {expected} to confirm cancellation."}
