"""The two endpoints a lawyer actually presses: decide a clause, finish a review.

Everything below the route is faked. store.get / decide_clause / set_status and
precedent.index_reviewed are monkeypatched, and require_lawyer is overridden, so
these tests exercise the ROUTE logic (the gates, the status codes, which text
becomes final_text) without a database, a model, or a login.
"""

import pytest
from fastapi.testclient import TestClient

try:
    import api as api_module
except Exception as e:  # store.init_db() runs at import and needs Postgres
    pytest.skip(f"cannot import api ({e})", allow_module_level=True)

from app import precedent, store
from app.users import require_lawyer


class FakeUser:
    id = "00000000-0000-0000-0000-000000000001"
    email = "priya@papyrus.dev"
    role = "lawyer"
    is_active = True


@pytest.fixture
def client():
    # deliberately NOT `with TestClient(...)`: the context manager fires the
    # startup hook, which opens an asyncpg connection and pings Weaviate. These
    # tests are about route logic, so the app is driven without ever starting.
    api_module.app.dependency_overrides[require_lawyer] = lambda: FakeUser()
    yield TestClient(api_module.app)
    api_module.app.dependency_overrides.clear()


def _clause(cid, *, findings=True, proposal=None, decision=None, text="their original wording"):
    return {
        "clause_id": cid,
        "number": cid[-1],
        "heading": f"Heading {cid}",
        "text": text,
        "findings": [{"severity": "high", "plain": "bad"}] if findings else [],
        "proposal": proposal,
        "decision": decision,
        "final_text": text,
    }


def _state(**over):
    base = {
        "contract_id": "P-abc123",
        "filename": "deal.docx",
        "status": "needs_review",
        "clauses": [_clause("c01", proposal={"new_text": "our safer wording"}), _clause("c02", findings=False)],
        "meta": {"contract_type": "msa"},
        "summary": {"executive": "a summary"},
    }
    base.update(over)
    return base


@pytest.fixture
def decided(monkeypatch):
    # capture what decide_clause was called with; the SQL itself is covered in test_store
    seen = {}

    def fake_decide(contract_id, clause_id, decision, final_text):
        seen.update(contract_id=contract_id, clause_id=clause_id, decision=decision, final_text=final_text)
        return {"clause_id": clause_id, "decision": decision, "final_text": final_text}

    monkeypatch.setattr(store, "decide_clause", fake_decide)
    return seen


DECIDE = "/contracts/P-abc123/clauses/c01/decision"


# --- the decision gates -----------------------------------------------------


def test_unknown_verdict_is_rejected(client, monkeypatch):
    monkeypatch.setattr(store, "get", lambda cid: _state())
    r = client.post(DECIDE, json={"verdict": "maybe"})
    assert r.status_code == 422


def test_edited_without_text_is_rejected(client, monkeypatch):
    # whitespace only must not count as wording
    monkeypatch.setattr(store, "get", lambda cid: _state())
    r = client.post(DECIDE, json={"verdict": "edited", "edited_text": "   "})
    assert r.status_code == 422


def test_missing_contract_is_404(client, monkeypatch):
    monkeypatch.setattr(store, "get", lambda cid: None)
    r = client.post(DECIDE, json={"verdict": "rejected"})
    assert r.status_code == 404


def test_a_finished_review_cannot_be_reopened(client, monkeypatch):
    monkeypatch.setattr(store, "get", lambda cid: _state(status="reviewed"))
    r = client.post(DECIDE, json={"verdict": "rejected"})
    assert r.status_code == 409


def test_missing_clause_is_404(client, monkeypatch):
    monkeypatch.setattr(store, "get", lambda cid: _state())
    r = client.post("/contracts/P-abc123/clauses/c99/decision", json={"verdict": "rejected"})
    assert r.status_code == 404


def test_accepting_a_clause_with_no_proposal_is_rejected(client, monkeypatch):
    # nothing to accept: the inspectors flagged it but negotiation wrote no rewrite
    monkeypatch.setattr(store, "get", lambda cid: _state(clauses=[_clause("c01", proposal=None)]))
    r = client.post(DECIDE, json={"verdict": "accepted"})
    assert r.status_code == 422


# --- which text becomes final_text ------------------------------------------


def test_accept_uses_the_proposal(client, monkeypatch, decided):
    monkeypatch.setattr(store, "get", lambda cid: _state())
    r = client.post(DECIDE, json={"verdict": "accepted"})
    assert r.status_code == 200
    assert decided["final_text"] == "our safer wording"
    assert decided["decision"] == "accepted"


def test_reject_keeps_their_wording(client, monkeypatch, decided):
    monkeypatch.setattr(store, "get", lambda cid: _state())
    r = client.post(DECIDE, json={"verdict": "rejected"})
    assert r.status_code == 200
    assert decided["final_text"] == "their original wording"


def test_edit_uses_the_lawyers_wording_stripped(client, monkeypatch, decided):
    monkeypatch.setattr(store, "get", lambda cid: _state())
    r = client.post(DECIDE, json={"verdict": "edited", "edited_text": "  my own wording  "})
    assert r.status_code == 200
    assert decided["final_text"] == "my own wording"


def test_a_clause_that_vanished_between_read_and_write_is_404(client, monkeypatch):
    # store.get saw it, decide_clause did not: report it rather than pretend it worked
    monkeypatch.setattr(store, "get", lambda cid: _state())
    monkeypatch.setattr(store, "decide_clause", lambda *a: None)
    r = client.post(DECIDE, json={"verdict": "rejected"})
    assert r.status_code == 404


# --- finish -----------------------------------------------------------------

FINISH = "/contracts/P-abc123/finish"


@pytest.fixture
def finishable(monkeypatch):
    monkeypatch.setattr(store, "set_status", lambda cid, s: True)
    monkeypatch.setattr(precedent, "index_reviewed", lambda *a, **k: None)


def test_finish_missing_contract_is_404(client, monkeypatch, finishable):
    monkeypatch.setattr(store, "get", lambda cid: None)
    assert client.post(FINISH).status_code == 404


def test_finish_twice_is_409(client, monkeypatch, finishable):
    monkeypatch.setattr(store, "get", lambda cid: _state(status="reviewed"))
    assert client.post(FINISH).status_code == 409


def test_finish_before_the_review_is_ready_is_409(client, monkeypatch, finishable):
    monkeypatch.setattr(store, "get", lambda cid: _state(status="processing"))
    assert client.post(FINISH).status_code == 409


def test_finish_with_an_undecided_clause_is_409(client, monkeypatch, finishable):
    monkeypatch.setattr(store, "get", lambda cid: _state())  # c01 flagged, no decision
    assert client.post(FINISH).status_code == 409


def test_finish_assembles_the_document_and_counts(client, monkeypatch, finishable):
    clauses = [
        _clause("c01", proposal={"new_text": "x"}, decision="accepted"),
        _clause("c02", findings=False),
    ]
    clauses[0]["final_text"] = "our safer wording"
    monkeypatch.setattr(store, "get", lambda cid: _state(clauses=clauses))
    r = client.post(FINISH)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "reviewed"
    # the accepted clause contributes its final_text, the clean one its original
    assert "our safer wording" in body["document"]
    assert "their original wording" in body["document"]
    assert body["counts"] == {"clauses": 2, "flagged": 1, "accepted": 1, "rejected": 0, "edited": 0}
    assert body["precedent_filed"] is True


def test_weaviate_being_down_does_not_block_the_finish(client, monkeypatch):
    # filing precedent is a nice-to-have; it must never stop a lawyer signing off
    clauses = [_clause("c01", proposal={"new_text": "x"}, decision="rejected")]
    monkeypatch.setattr(store, "get", lambda cid: _state(clauses=clauses))
    monkeypatch.setattr(store, "set_status", lambda cid, s: True)

    def boom(*a, **k):
        raise RuntimeError("weaviate is down")

    monkeypatch.setattr(precedent, "index_reviewed", boom)
    r = client.post(FINISH)
    assert r.status_code == 200
    assert r.json()["precedent_filed"] is False


# --- the assembler ----------------------------------------------------------


def test_assemble_prefers_final_text_and_keeps_order():
    doc = api_module._assemble(
        [
            {"number": "1", "heading": "Parties", "text": "orig one", "final_text": "final one"},
            {"number": "2", "heading": "Payment", "text": "orig two", "final_text": ""},
        ]
    )
    assert doc == "1. Parties\nfinal one\n\n2. Payment\norig two"
