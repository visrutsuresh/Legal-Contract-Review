"""valid_finding is the gate that keeps half-formed model output off the
lawyer's screen; risk_rollup is the number the whole docket is sorted by."""

from app.state import REQUIRED_FINDING_FIELDS, risk_rollup, valid_finding


def _finding(**over) -> dict:
    f = {
        "finding_id": "f-c04-fin-1",
        "clause_id": "c04",
        "inspector": "financial",
        "severity": "high",
        "plain": "You would wait four months to get paid.",
        "term": "Net-120 payment term.",
        "wrong": "Payment lands 120 days after invoice.",
        "change": "Push for net-30.",
        "ignore": "You bank-roll the client for a third of a year.",
        "evidence": "within one hundred and twenty (120) days",
        "fix_hint": "net-30",
    }
    f.update(over)
    return f


def test_complete_finding_passes():
    assert valid_finding(_finding()) is True


def test_fix_hint_is_the_only_optional_field():
    f = _finding()
    del f["fix_hint"]
    assert valid_finding(f) is True


def test_every_required_field_missing_in_turn_fails():
    for field in REQUIRED_FINDING_FIELDS:
        f = _finding()
        del f[field]
        assert valid_finding(f) is False, f"missing {field} should fail"


def test_empty_string_counts_as_missing():
    # the model likes to emit "" rather than omit the key; both must fail
    for field in REQUIRED_FINDING_FIELDS:
        assert valid_finding(_finding(**{field: ""})) is False, f"blank {field} should fail"


def test_bad_severity_fails():
    assert valid_finding(_finding(severity="critical")) is False
    assert valid_finding(_finding(severity="High")) is False  # vocabulary is lowercase


def test_all_three_severities_pass():
    for sev in ("high", "medium", "low"):
        assert valid_finding(_finding(severity=sev)) is True


# --- risk_rollup ------------------------------------------------------------


def _clause(*severities) -> dict:
    return {"clause_id": "c01", "findings": [{"severity": s} for s in severities]}


def test_score_arithmetic():
    # 25 per high, 10 per medium, 4 per low
    out = risk_rollup([_clause("high", "medium", "low")], [])
    assert out["score"] == 39
    assert out["level"] == "high"
    assert out["why"] == "1 serious, 1 medium, 1 minor issues"


def test_missing_clauses_count_towards_the_score():
    out = risk_rollup([_clause("low")], [{"severity": "high"}])
    assert out["score"] == 29
    assert out["level"] == "high"  # a missing required clause can set the level


def test_score_is_capped_at_100():
    out = risk_rollup([_clause(*["high"] * 10)], [])
    assert out["score"] == 100  # 250 uncapped


def test_level_picks_the_worst_severity_present():
    assert risk_rollup([_clause("medium", "low")], [])["level"] == "medium"
    assert risk_rollup([_clause("low", "low")], [])["level"] == "low"


def test_clauses_without_findings_contribute_nothing():
    out = risk_rollup([{"clause_id": "c01"}, _clause("medium")], [])
    assert out["score"] == 10


def test_zero_findings_is_reported_as_low_not_clean():
    # KNOWN OPEN QUESTION: a contract where nothing at all was flagged comes
    # back level="low", score=0 -- indistinguishable from a contract with a
    # couple of minor niggles, and "low" reads as a verdict rather than as
    # "no issues found". This test pins TODAY's behaviour on purpose: if the
    # level vocabulary ever grows a "clean"/"none" value, this fails loudly
    # instead of the change slipping through unnoticed.
    out = risk_rollup([], [])
    assert out == {"level": "low", "score": 0, "why": "0 serious, 0 medium, 0 minor issues"}
