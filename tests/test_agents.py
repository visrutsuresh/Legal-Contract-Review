"""_clause_rows and summary_counts: the deterministic half of app.agents.
The agent functions around them are model calls and are deliberately untested here."""

from app.agents import _clause_rows, summary_counts


def _c(**over) -> dict:
    c = {"number": "1", "heading": "Parties", "text": "The parties are A and B.", "clause_type": "parties"}
    c.update(over)
    return c


def test_ids_are_assigned_in_document_order():
    rows = _clause_rows({"clauses": [_c(number=str(i)) for i in range(1, 4)]})
    assert [r["clause_id"] for r in rows] == ["c01", "c02", "c03"]
    assert [r["number"] for r in rows] == ["1", "2", "3"]


def test_ids_are_zero_padded_past_nine():
    rows = _clause_rows({"clauses": [_c() for _ in range(11)]})
    assert rows[8]["clause_id"] == "c09"
    assert rows[9]["clause_id"] == "c10"


def test_non_dict_entries_are_skipped_without_burning_an_id():
    # ids must stay contiguous: findings reference them by name later
    rows = _clause_rows({"clauses": [_c(), "a bare string", None, 42, _c()]})
    assert [r["clause_id"] for r in rows] == ["c01", "c02"]


def test_clauses_with_no_text_are_skipped():
    rows = _clause_rows({"clauses": [_c(text=""), _c(text="   \n "), _c(), _c(heading="No text")]})
    assert len(rows) == 2
    assert rows[0]["clause_id"] == "c01"


def test_text_is_stripped():
    rows = _clause_rows({"clauses": [_c(text="  padded wording  ")]})
    assert rows[0]["text"] == "padded wording"
    assert rows[0]["final_text"] == "padded wording"  # their wording stands until a decision


def test_unknown_clause_type_is_coerced_to_other():
    rows = _clause_rows({"clauses": [_c(clause_type="force_majeure"), _c(clause_type=""), _c()]})
    assert [r["clause_type"] for r in rows] == ["other", "other", "parties"]


def test_clause_type_is_case_and_space_insensitive():
    rows = _clause_rows({"clauses": [_c(clause_type="  Governing_Law ")]})
    assert rows[0]["clause_type"] == "governing_law"


def test_missing_keys_become_empty_strings_not_crashes():
    rows = _clause_rows({"clauses": [{"text": "some wording"}]})
    assert rows[0]["number"] == ""
    assert rows[0]["heading"] == ""
    assert rows[0]["clause_type"] == "other"


def test_every_row_is_a_full_clause_dict():
    row = _clause_rows({"clauses": [_c()]})[0]
    assert row["findings"] == []
    assert row["proposal"] is None
    assert row["decision"] is None


def test_a_missing_or_wrong_shaped_clause_list_yields_nothing():
    assert _clause_rows({}) == []
    assert _clause_rows({"clauses": None}) == []
    assert _clause_rows({"clauses": "c1, c2"}) == []


# --- summary_counts ---------------------------------------------------------


def test_summary_counts_adds_up():
    clauses = [
        {"clause_id": "c01", "findings": [{"severity": "high"}, {"severity": "low"}], "proposal": {"new_text": "x"}},
        {"clause_id": "c02", "findings": [{"severity": "medium"}], "proposal": None},
        {"clause_id": "c03", "findings": []},
    ]
    counts = summary_counts(clauses, [{"severity": "medium"}])
    assert counts == {"clauses": 3, "flagged": 2, "proposals": 1, "high": 1, "medium": 2, "low": 1, "missing": 1}


def test_summary_counts_of_a_clean_contract():
    counts = summary_counts([{"clause_id": "c01", "findings": []}], [])
    assert counts["flagged"] == 0
    assert counts["high"] == counts["medium"] == counts["low"] == 0
