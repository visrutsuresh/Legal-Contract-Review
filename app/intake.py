"""Turn an uploaded contract file into plain text for the pipeline.

Plain code on purpose: intake has no judgement to make. Reading bytes
out of a .docx or .pdf is mechanical, so a model call here would add
cost, latency, and a new failure mode while deciding nothing. Bounded
autonomy means agents where there are decisions, functions where not.
"""

import io

from docx import Document
from pypdf import PdfReader

MIN_TEXT_CHARS = 200  # under this we assume a scan or an empty file

NEEDS_A_PERSON = (
    "We could not read any text in this file. It may be a scanned image, "
    "an unsupported file type, or an empty document. A person needs to "
    "look at this one."
)


def _normalise(text: str) -> str:
    # collapse messy spacing inside each line, drop blank lines, KEEP the
    # line breaks: they are the clause-boundary hints extraction relies on
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line).strip()


def read_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


def read_pdf(file_bytes: bytes) -> tuple[str, int]:
    reader = PdfReader(io.BytesIO(file_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text, len(reader.pages)


def _failed() -> dict:
    # "scanned" doubles as the catch-all source_format for anything unreadable
    return {"source_format": "scanned", "raw_text": "", "pages": 0,
            "status": "extraction_failed", "error": NEEDS_A_PERSON}


def extract_text(filename: str, file_bytes: bytes) -> dict:
    """Parse one upload. Returns a dict of ContractState updates.

    Success -> {"source_format": "docx"|"pdf", "raw_text": str, "pages": int,
                "error": None}
    Failure -> {"source_format": "scanned", "raw_text": "", "pages": 0,
                "status": "extraction_failed", "error": NEEDS_A_PERSON}

    The error key is the caller's one-glance verdict: None means the text
    is good. The graph's intake_node (Task 30) reads this dict, puts
    source_format and raw_text into the state directly, folds pages into
    meta, and treats any non-None error as "stop, this one needs a person".
    """
    name = (filename or "").lower()
    try:
        if name.endswith(".docx"):
            text = read_docx(file_bytes)
            pages = max(1, round(len(text.split()) / 400))  # docx has no fixed pages, rough estimate
            fmt = "docx"
        elif name.endswith(".pdf"):
            text, pages = read_pdf(file_bytes)
            fmt = "pdf"
        else:
            return _failed()
    except Exception:
        return _failed()
    text = _normalise(text)
    if len(text) < MIN_TEXT_CHARS:
        # a real contract is never this short: treat it as a scan or empty file
        return _failed()
    return {"source_format": fmt, "raw_text": text, "pages": pages, "error": None}
