"""all_decided is pure. decide_clause is a CTE plus a nested jsonb_set, which
is exactly the kind of SQL a mock would prove nothing about, so it runs against
the real Postgres and skips when there is no database to talk to."""

import uuid

import psycopg  # type:ignore
import pytest
from psycopg.types.json import Jsonb  # type:ignore

from app import store

# --- all_decided ------------------------------------------------------------


def _clause(cid, findings=True, decision=None) -> dict:
    return {
        "clause_id": cid,
        "text": f"text {cid}",
        "findings": [{"severity": "high"}] if findings else [],
        "decision": decision,
    }


def test_no_clauses_at_all_counts_as_done():
    assert store.all_decided({}) is True
    assert store.all_decided({"clauses": []}) is True


def test_a_contract_with_nothing_flagged_counts_as_done():
    # clean clauses need no decision; the lawyer has nothing to answer
    assert store.all_decided({"clauses": [_clause("c01", findings=False)]}) is True


def test_one_undecided_flagged_clause_blocks_the_finish():
    state = {"clauses": [_clause("c01", decision="accepted"), _clause("c02")]}
    assert store.all_decided(state) is False


def test_every_flagged_clause_decided_is_done():
    state = {"clauses": [
        _clause("c01", decision="accepted"),
        _clause("c02", decision="rejected"),
        _clause("c03", decision="edited"),
        _clause("c04", findings=False),  # untouched, still fine
    ]}
    assert store.all_decided(state) is True


def test_an_empty_string_decision_does_not_count():
    assert store.all_decided({"clauses": [_clause("c01", decision="")]}) is False


# --- decide_clause, against the real database -------------------------------


@pytest.fixture
def db_contract():
    """Insert a throwaway TEST- contract and always delete it again, pass or fail."""
    try:
        conn = psycopg.connect(store.DATABASE_URL, connect_timeout=3)
    except Exception as e:
        pytest.skip(f"no Postgres on {store.DATABASE_URL!r}: {e}")
    contract_id = f"TEST-{uuid.uuid4().hex[:12]}"
    state = {
        "contract_id": contract_id,
        "filename": "throwaway.docx",
        "status": "needs_review",
        "clauses": [
            {"clause_id": "c01", "text": "first", "final_text": "first", "decision": None, "findings": []},
            {"clause_id": "c02", "text": "second", "final_text": "second", "decision": None,
             "findings": [{"severity": "high"}]},
            {"clause_id": "c03", "text": "third", "final_text": "third", "decision": None, "findings": []},
        ],
    }
    with conn:
        store.init_db()  # the table may not exist on a fresh database
        conn.execute(
            """INSERT INTO contracts (contract_id, filename, status, stage, state, created_at)
               VALUES (%s, %s, 'needs_review', 'done', %s, now())""",
            (contract_id, "throwaway.docx", Jsonb(state)),
        )
    try:
        yield contract_id
    finally:
        with psycopg.connect(store.DATABASE_URL, connect_timeout=3) as cleanup:
            cleanup.execute("DELETE FROM contracts WHERE contract_id = %s", (contract_id,))


def test_decide_clause_patches_the_named_clause(db_contract):
    out = store.decide_clause(db_contract, "c02", "edited", "second, rewritten")
    assert out["clause_id"] == "c02"
    assert out["decision"] == "edited"
    assert out["final_text"] == "second, rewritten"


def test_decide_clause_leaves_its_neighbours_alone(db_contract):
    store.decide_clause(db_contract, "c02", "accepted", "second, agreed")
    state = store.get(db_contract)
    by_id = {c["clause_id"]: c for c in state["clauses"]}
    assert by_id["c01"]["decision"] is None
    assert by_id["c03"]["final_text"] == "third"
    assert [c["clause_id"] for c in state["clauses"]] == ["c01", "c02", "c03"]  # order held


def test_decide_clause_can_be_changed_afterwards(db_contract):
    store.decide_clause(db_contract, "c01", "accepted", "first")
    out = store.decide_clause(db_contract, "c01", "rejected", "first, refused")
    assert out["decision"] == "rejected"
    assert store.get(db_contract)["clauses"][0]["final_text"] == "first, refused"


def test_decide_clause_on_an_unknown_clause_returns_none(db_contract):
    assert store.decide_clause(db_contract, "c99", "accepted", "nope") is None
    # and nothing was written
    assert all(c["decision"] is None for c in store.get(db_contract)["clauses"])


def test_decide_clause_on_an_unknown_contract_returns_none(db_contract):
    assert store.decide_clause("TEST-does-not-exist", "c01", "accepted", "nope") is None


def test_decide_clause_feeds_all_decided(db_contract):
    # the two together are the finish gate the API leans on
    assert store.all_decided(store.get(db_contract)) is False
    store.decide_clause(db_contract, "c02", "accepted", "second")
    assert store.all_decided(store.get(db_contract)) is True
