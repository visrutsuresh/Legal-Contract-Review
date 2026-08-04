import json
from pathlib import Path

from app import precedent

TOOLS = {}  # name -> function

# anchored to this file, NOT the working directory: run_tool swallows every
# exception into an "ERROR: ..." string the agent reads as a normal observation,
# so a bad relative path would not crash, it would quietly tell all four
# inspectors the rules pack and the templates do not exist
REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "data" / "templates"
RULES_FILE = REPO_ROOT / "policy_rules.md"


def tool(fn):
    # Register a function so an agent can call it by name
    TOOLS[fn.__name__] = fn
    return fn


def run_tool(name: str, args: dict) -> str:
    # Dial a tool by name with its args; return the result as a text
    fn = TOOLS.get(name)
    if fn is None:
        return f"ERROR: unknown tool {name!r}"
    try:
        return str(fn(**args))
    except Exception as e:
        return f"ERROR: {e}"


@tool
def template_fetch(contract_type: str) -> dict:
    # The firm's standard contract of this type: clause list with required flags
    path = TEMPLATE_DIR / f"{contract_type.lower().strip()}.json"
    if not path.exists():
        known = sorted(p.stem for p in TEMPLATE_DIR.glob("*.json"))
        return {"error": f"no template for {contract_type!r}", "known_types": known}
    return json.loads(path.read_text())


@tool
def rules_read(contract_type: str) -> str:
    # the firm's compliance rules pack (small markdown file, returned whole)
    return RULES_FILE.read_text()


@tool
def precedent_search(query: str) -> list:
    # Past reviewed contracts that read like the query, best match first
    return precedent.search(query)


# --- WRITE tools: the agents can now act, not only look -----------------------
#
# Everything above READS. Everything below CHANGES a contract, so it plays by
# stricter rules, carried over from #1's proven refund/cancellation pattern:
#
#   1. Every write appends to that contract's hash chain, attributed to the agent.
#   2. A write that commits the firm to a negotiating position is TWO-PHASE: the
#      first call returns a confirm code and changes nothing; only a call carrying
#      the matching code commits. The code is derived from the target id, so it is
#      recomputable and never stored.
#   3. NOTHING here can accept, reject, edit or finish a clause. Those four verbs
#      belong to the lawyer and only to the lawyer. That is Papyrus's promise:
#      the system drafts, it never signs.

import hashlib

from app import audit, store

_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L, so a human can read it aloud


def _confirm_code(target_id: str) -> str:
    # deterministic 5-char code per target; recomputable, so we verify without storing it
    digest = hashlib.sha256(target_id.encode()).digest()
    return "".join(_CODE_ALPHABET[b % len(_CODE_ALPHABET)] for b in digest[:5])


def _clause_on(contract_id: str, clause_id: str):
    state = store.get(contract_id)
    if state is None:
        return None, None
    clause = next((c for c in state.get("clauses", []) if c.get("clause_id") == clause_id), None)
    return state, clause


def _commit(state: dict, entry: str) -> None:
    state["audit"] = audit.chain(state.get("audit") or [], [entry])
    store.save(state)


@tool
def escalate_clause(contract_id: str, clause_id: str, reason: str) -> dict:
    """Mark a clause as needing senior counsel before anyone signs. Single-phase:
    asking a partner to look is not destructive, and it blocks nothing."""
    state, clause = _clause_on(contract_id, clause_id)
    if state is None:
        return {"status": "error", "message": f"no contract {contract_id!r}"}
    if clause is None:
        return {"status": "error", "message": f"no clause {clause_id!r} on {contract_id}"}
    if state.get("status") == "reviewed":
        return {"status": "error", "message": "this review is finished; escalating it now would change a signed record"}
    clause["escalated"] = {"reason": str(reason).strip(), "by": "agent"}
    _commit(state, f"agent_action escalate_clause: {clause_id} to senior counsel ({str(reason).strip()})")
    return {"status": "escalated", "clause_id": clause_id, "reason": str(reason).strip()}


@tool
def request_concession(contract_id: str, clause_id: str, ask: str, code: str = "") -> dict:
    """Record what we will ask the counterparty to change on this clause. Two-phase,
    because it is the firm's negotiating position. It DRAFTS the ask; it never sends
    anything and it never alters the clause wording."""
    state, clause = _clause_on(contract_id, clause_id)
    if state is None:
        return {"status": "error", "message": f"no contract {contract_id!r}"}
    if clause is None:
        return {"status": "error", "message": f"no clause {clause_id!r} on {contract_id}"}
    if state.get("status") == "reviewed":
        return {"status": "error", "message": "this review is finished; it takes no new asks"}
    expected = _confirm_code(clause_id)
    if str(code).strip().upper() != expected:
        return {
            "status": "awaiting_confirmation",
            "confirm_code": expected,
            "message": f"Call again with code={expected} to record this ask against {clause_id}.",
        }
    clause["concession_ask"] = {"ask": str(ask).strip(), "by": "agent"}
    _commit(state, f"agent_action request_concession: {clause_id} ask recorded ({str(ask).strip()[:80]})")
    return {"status": "recorded", "clause_id": clause_id, "ask": str(ask).strip()}
