"""Write the reviewed contract back into the original .docx.

Only the paragraphs belonging to changed clauses are touched; every other
paragraph, style, table, header, and footer rides through untouched because
we edit the uploaded file itself instead of rebuilding a document from text.
"""

import io

from docx import Document


def _norm(s: str) -> str:
    return " ".join((s or "").split())


def _find_span(norm_paras: list[str], clause_text: str) -> tuple[int, int] | None:
    """Locate the contiguous paragraph run whose joined text equals the clause.

    Returns (start, end) as a half-open index range, or None if the clause
    text (as extracted) cannot be found verbatim in the document.
    """
    for i, first in enumerate(norm_paras):
        if not first or not clause_text.startswith(first):
            continue
        parts = []
        for j in range(i, len(norm_paras)):
            if norm_paras[j]:
                parts.append(norm_paras[j])
            joined = " ".join(parts)
            if joined == clause_text:
                return (i, j + 1)
            if not clause_text.startswith(joined + " "):
                break
    return None


def export_docx(file_bytes: bytes, clauses: list[dict]) -> tuple[bytes, list[str]]:
    """Return (corrected .docx bytes, clause_ids whose text could not be located).

    A clause counts as changed when the lawyer accepted a proposal or supplied
    an edit and the final wording differs from the original. Its paragraph run
    is collapsed into one paragraph carrying the new wording; the first
    paragraph's style is kept, so numbering and look survive.
    """
    doc = Document(io.BytesIO(file_bytes))
    paras = doc.paragraphs
    norm = [_norm(p.text) for p in paras]
    unmatched: list[str] = []
    spans: list[tuple[int, int, str]] = []

    for c in clauses:
        if c.get("decision") not in ("accepted", "edited"):
            continue
        new = _norm(c.get("final_text") or "")
        old = _norm(c.get("text") or "")
        if not new or new == old:
            continue
        span = _find_span(norm, old)
        if span is None:
            unmatched.append(c.get("clause_id", "?"))
            continue
        spans.append((span[0], span[1], new))

    # apply after all matching so one clause's rewrite can't shift another's search
    for start, end, new in spans:
        paras[start].text = new  # replaces the runs, keeps the paragraph style
        for p in paras[start + 1 : end]:
            p._element.getparent().remove(p._element)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue(), unmatched
