"""Intake: bytes in, plain text out. No model call anywhere in this path,
which is exactly why it is worth pinning down hard."""

import io

from docx import Document

from app.intake import MIN_TEXT_CHARS, NEEDS_A_PERSON, _normalise, extract_text
from tests.conftest import GOLDEN


def _docx_bytes(paragraphs: list[str]) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _assert_failed(out: dict):
    # the exact failure shape the graph's intake_node branches on
    assert out == {
        "source_format": "scanned",
        "raw_text": "",
        "pages": 0,
        "status": "extraction_failed",
        "error": NEEDS_A_PERSON,
    }


def test_docx_happy_path():
    # tests/golden/tiny.docx is a 3-clause mutual NDA, ~865 chars: the smallest
    # thing that still clears MIN_TEXT_CHARS
    out = extract_text("tiny.docx", GOLDEN.joinpath("tiny.docx").read_bytes())
    assert out["error"] is None
    assert out["source_format"] == "docx"
    assert out["pages"] >= 1  # docx has no page count, intake estimates one
    assert "Governing Law" in out["raw_text"]
    assert len(out["raw_text"]) >= MIN_TEXT_CHARS
    assert "status" not in out  # success never stamps a status


def test_docx_keeps_one_line_per_paragraph():
    # clause splitting downstream leans on these breaks, so count them
    out = extract_text("tiny.docx", GOLDEN.joinpath("tiny.docx").read_bytes())
    assert out["raw_text"].count("\n") == 6  # 7 paragraphs, 6 breaks


def test_uppercase_extension_is_still_recognised():
    out = extract_text("TINY.DOCX", GOLDEN.joinpath("tiny.docx").read_bytes())
    assert out["error"] is None
    assert out["source_format"] == "docx"


def test_unknown_extension_fails():
    _assert_failed(extract_text("contract.txt", b"a" * 1000))


def test_missing_filename_fails():
    _assert_failed(extract_text("", b"a" * 1000))


def test_text_under_the_minimum_fails():
    # a real docx, just far too little text in it
    out = extract_text("stub.docx", _docx_bytes(["Agreement.", "Signed."]))
    _assert_failed(out)


def test_empty_docx_fails():
    _assert_failed(extract_text("blank.docx", _docx_bytes([])))


def test_unopenable_bytes_fail_rather_than_raise():
    # the graph treats a raised exception differently; intake should swallow it
    _assert_failed(extract_text("broken.docx", b"not a zip file at all"))


def test_normalise_collapses_spacing_but_keeps_line_breaks():
    # LOAD-BEARING: the line breaks are the clause-boundary hints extraction
    # relies on. Runs of spaces/tabs inside a line go, the newlines stay.
    raw = "  1.   Parties \t\t here\n\n\n2.    Payment\n   \n3. Term  "
    assert _normalise(raw) == "1. Parties here\n2. Payment\n3. Term"


def test_normalise_drops_blank_lines_and_trims_the_ends():
    assert _normalise("\n\n  hello  \n\n  world  \n\n") == "hello\nworld"


def test_normalise_of_whitespace_only_is_empty():
    assert _normalise("   \n\t\n  ") == ""
