"""The WRITE tools: the moment Papyrus's agents stopped being advisors.

Every tool before these READ. These change a contract, so they carry stricter
rules and every one is pinned here: the two-phase confirm, the hash chain entry,
the refusals, and the promise the whole product rests on, which is that an agent
can never accept, reject or edit a clause. $0, no model, no Modal.
"""

import pytest

from app import audit, store, tools

CONTRACT = "K-0001"
CLAUSE = "c04"


@pytest.fixture
def desk(monkeypatch):
    """One contract with one flagged clause, held in a dict instead of Postgres."""
    state = {
        "contract_id": CONTRACT,
        "filename": "msa_cobalt.docx",
        "status": "needs_review",
        "clauses": [
            {
                "clause_id": CLAUSE,
                "number": "4",
                "heading": "Payment Terms",
                "clause_type": "payment",
                "text": "Payment within one hundred and twenty (120) days.",
                "findings": [{"finding_id": "f-c04-fin-1", "severity": "high", "plain": "You would wait four months to get paid."}],
                "decision": None,
            }
        ],
        "audit": audit.chain([], ["summary done"]),
    }
    db = {CONTRACT: state}
    monkeypatch.setattr(store, "get", lambda cid: db.get(cid))
    monkeypatch.setattr(store, "save", lambda s: db.__setitem__(s["contract_id"], s))
    return db


def clause_of(db):
    return db[CONTRACT]["clauses"][0]


# --- escalate_clause: single-phase, because asking a partner to look blocks nothing ---


def test_escalate_really_marks_the_clause(desk):
    out = tools.escalate_clause(CONTRACT, CLAUSE, "net-120 against a net-30 standard")
    assert out["status"] == "escalated"
    assert clause_of(desk)["escalated"]["reason"] == "net-120 against a net-30 standard"
    assert clause_of(desk)["escalated"]["by"] == "agent"


def test_escalate_lands_on_the_chain_and_leaves_it_intact(desk):
    before = len(desk[CONTRACT]["audit"])
    tools.escalate_clause(CONTRACT, CLAUSE, "unbounded liability")
    log = desk[CONTRACT]["audit"]
    assert len(log) == before + 1
    assert audit.verify(log) == -1
    assert "agent_action escalate_clause" in log[-1]["step"]


def test_escalate_refuses_a_finished_review(desk):
    desk[CONTRACT]["status"] = "reviewed"
    out = tools.escalate_clause(CONTRACT, CLAUSE, "too late")
    assert out["status"] == "error"
    assert clause_of(desk).get("escalated") is None


def test_unknown_contract_or_clause_is_an_error_not_a_crash(desk):
    assert tools.escalate_clause("K-9999", CLAUSE, "x")["status"] == "error"
    assert tools.escalate_clause(CONTRACT, "c99", "x")["status"] == "error"


# --- request_concession: two-phase, because it is the firm's negotiating position ---


def test_first_call_changes_nothing_and_returns_a_code(desk):
    out = tools.request_concession(CONTRACT, CLAUSE, "Move to net-30.")
    assert out["status"] == "awaiting_confirmation"
    assert len(out["confirm_code"]) == 5
    assert clause_of(desk).get("concession_ask") is None


def test_a_matching_code_records_the_ask(desk):
    code = tools.request_concession(CONTRACT, CLAUSE, "Move to net-30.")["confirm_code"]
    out = tools.request_concession(CONTRACT, CLAUSE, "Move to net-30.", code=code)
    assert out["status"] == "recorded"
    assert clause_of(desk)["concession_ask"]["ask"] == "Move to net-30."


def test_a_wrong_code_never_records(desk):
    tools.request_concession(CONTRACT, CLAUSE, "Move to net-30.", code="ZZZZZ")
    assert clause_of(desk).get("concession_ask") is None


def test_the_code_is_recomputable_and_specific_to_the_clause():
    assert tools._confirm_code("c04") == tools._confirm_code("c04")
    assert tools._confirm_code("c04") != tools._confirm_code("c05")


def test_only_the_committed_call_touches_the_chain(desk):
    before = len(desk[CONTRACT]["audit"])
    tools.request_concession(CONTRACT, CLAUSE, "Move to net-30.")
    assert len(desk[CONTRACT]["audit"]) == before
    tools.request_concession(CONTRACT, CLAUSE, "Move to net-30.", code=tools._confirm_code(CLAUSE))
    assert len(desk[CONTRACT]["audit"]) == before + 1
    assert audit.verify(desk[CONTRACT]["audit"]) == -1


# --- the promise the product rests on ---


def test_no_write_tool_touches_the_clause_wording(desk):
    """An agent may escalate and may ask. It may never change what the contract says."""
    original = clause_of(desk)["text"]
    tools.escalate_clause(CONTRACT, CLAUSE, "high risk")
    tools.request_concession(CONTRACT, CLAUSE, "Move to net-30.", code=tools._confirm_code(CLAUSE))
    assert clause_of(desk)["text"] == original
    assert clause_of(desk)["decision"] is None
    assert clause_of(desk).get("final_text") is None


def test_no_tool_can_accept_reject_edit_or_finish(desk):
    """The registry is the contract. A tool named like a lawyer's verdict should
    fail this test before it ever reaches a review."""
    forbidden = ("accept", "reject", "edit", "sign", "finish", "decide")
    assert [n for n in tools.TOOLS if any(w in n for w in forbidden)] == []
