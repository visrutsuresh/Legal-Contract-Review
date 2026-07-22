"""fan_in is where four parallel inspectors' output becomes one case file.
Everything here builds the state dict by hand: the graph itself is never run,
because every node above fan_in is a model call."""

import pytest

from app import store
from app.graph import fan_in, inspector_status


@pytest.fixture(autouse=True)
def no_db(monkeypatch):
    # fan_in narrates its stage to Postgres. That is not what we are testing
    # and a missing DB would just cost us a connection timeout per test.
    monkeypatch.setattr(store, "set_stage", lambda *a, **k: True)


def _finding(clause_id, **over) -> dict:
    f = {
        "finding_id": f"f-{clause_id}-cmp-1",
        "clause_id": clause_id,
        "inspector": "compliance",
        "severity": "medium",
        "plain": "plain",
        "term": "term",
        "wrong": "wrong",
        "change": "change",
        "ignore": "ignore",
        "evidence": "evidence",
    }
    f.update(over)
    return f


def _state(findings, clause_ids=("c01", "c02"), **over) -> dict:
    s = {
        "contract_id": "TEST-fan-in",
        "clauses": [{"clause_id": cid, "text": f"text {cid}", "findings": []} for cid in clause_ids],
        "findings_raw": findings,
        "inspector_reports": [{"inspector": n, "status": "ok"} for n in ("compliance", "risk", "template", "financial")],
        "missing_clauses": [],
    }
    s.update(over)
    return s


def test_findings_are_pinned_to_the_clause_they_name():
    out = fan_in(_state([_finding("c02"), _finding("c01"), _finding("c02", severity="high")]))
    by_id = {c["clause_id"]: c for c in out["clauses"]}
    assert len(by_id["c01"]["findings"]) == 1
    assert len(by_id["c02"]["findings"]) == 2
    assert "3 findings pinned, 0 dropped" in out["audit"][0]


def test_invalid_findings_are_dropped():
    bad = [
        _finding("c01", evidence=""),        # blank required field
        _finding("c01", severity="urgent"),  # outside the vocabulary
        "not a dict at all",                 # model emitted a bare string
        None,
    ]
    out = fan_in(_state([_finding("c01")] + bad))
    by_id = {c["clause_id"]: c for c in out["clauses"]}
    assert len(by_id["c01"]["findings"]) == 1
    assert "1 findings pinned, 4 dropped" in out["audit"][0]
    # the two bare non-dicts have no clause to land on, so they count as unknown;
    # only the two malformed dicts are "incomplete". The split is the whole point
    # of the counters, so assert it rather than just the total.
    assert "(2 incomplete, 2 unknown clause)" in out["audit"][0]


def test_findings_for_an_unknown_clause_are_dropped():
    # a hallucinated clause_id has nowhere to go; showing it unpinned would be
    # worse than losing it
    out = fan_in(_state([_finding("c99"), _finding(None), _finding("c01")]))
    assert sum(len(c["findings"]) for c in out["clauses"]) == 1
    assert "1 findings pinned, 2 dropped" in out["audit"][0]
    # both are well-formed findings citing a clause that does not exist here,
    # which is a prompt problem, not a schema one
    assert "(0 incomplete, 2 unknown clause)" in out["audit"][0]


def test_fan_in_clears_any_findings_already_on_the_clauses():
    # fan_in owns the pinning; a rerun must not double up
    state = _state([_finding("c01")])
    state["clauses"][1]["findings"] = [_finding("c02")]
    out = fan_in(state)
    by_id = {c["clause_id"]: c for c in out["clauses"]}
    assert by_id["c02"]["findings"] == []


def test_fan_in_does_not_mutate_the_incoming_clauses():
    state = _state([_finding("c01")])
    out = fan_in(state)
    assert state["clauses"][0]["findings"] == []
    assert out["clauses"][0] is not state["clauses"][0]


def test_missing_clauses_are_filtered_to_valid_severities():
    state = _state([], missing_clauses=[
        {"clause_type": "confidentiality", "severity": "high"},
        {"clause_type": "ip", "severity": "urgent"},  # bad severity
        {"clause_type": "notices"},                   # no severity
        "liability",                                  # not a dict
    ])
    out = fan_in(state)
    assert [m["clause_type"] for m in out["missing_clauses"]] == ["confidentiality"]


def test_risk_rollup_only_counts_the_kept_findings():
    out = fan_in(_state([_finding("c01", severity="high"), _finding("c99", severity="high")]))
    assert out["contract_risk"] == {"level": "high", "score": 25, "why": "1 serious, 0 medium, 0 minor issues"}


def test_audit_line_reports_the_inspector_checks():
    state = _state([], inspector_reports=[{"inspector": "compliance", "status": "ok"}])
    out = fan_in(state)
    line = out["audit"][0]
    assert "'compliance': 'ok'" in line
    assert "'risk': 'failed'" in line
    assert out["stage"] == "negotiating"


def test_fan_in_stamps_the_stage_for_the_docket(monkeypatch):
    seen = []
    monkeypatch.setattr(store, "set_stage", lambda cid, stage: seen.append((cid, stage)))
    fan_in(_state([]))
    assert seen == [("TEST-fan-in", "negotiating")]


def test_stage_write_failure_never_kills_the_review(monkeypatch):
    # the DB is optional narration, not part of the result
    def boom(*a, **k):
        raise RuntimeError("no database here")

    monkeypatch.setattr(store, "set_stage", boom)
    assert fan_in(_state([]))["stage"] == "negotiating"


# --- inspector_status -------------------------------------------------------


def test_missing_report_defaults_to_failed():
    # an inspector that never reported is NEVER assumed ok: silence must read
    # as a gap in the review, not as a clean bill of health
    assert inspector_status([]) == {
        "compliance": "failed",
        "risk": "failed",
        "template": "failed",
        "financial": "failed",
    }


def test_a_report_without_a_status_key_is_failed():
    assert inspector_status([{"inspector": "risk"}])["risk"] == "failed"


def test_reported_statuses_are_carried_through():
    out = inspector_status([
        {"inspector": "compliance", "status": "ok"},
        {"inspector": "risk", "status": "failed", "note": "timeout"},
    ])
    assert out["compliance"] == "ok"
    assert out["risk"] == "failed"
    assert out["template"] == "failed"


def test_an_unknown_inspector_name_is_ignored():
    out = inspector_status([{"inspector": "astrology", "status": "ok"}])
    assert "astrology" not in out
    assert set(out) == {"compliance", "risk", "template", "financial"}
