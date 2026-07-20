from app import router
from app.agents_base import _parse

CLAUSE_TYPES = {
    "parties",
    "scope",
    "payment",
    "term_termination",
    "confidentiality",
    "ip",
    "liability",
    "indemnity",
    "restraint",
    "data_protection",
    "governing_law",
    "notices",
    "boilerplate",
    "other",
}

CONTRACT_TYPES = {"nda", "msa", "sow", "vendor", "employment"}

EXTRACTION_SYSTEM = """ You are the Clause Extraction agent for Papyrus, a legal contract review product.
You are given the full plain text of ONE contract. Split it into its clauses and pull out the basic facts of the deal. 
Copy clause wording EXACTLY as written: never paraphrase, never summarise, never invent a clause that is not there.

Reply with ONE JSON object, nothing else:
  {"clauses": [
      {"number": "<the clause number as printed, e.g. 4 or
  7.2>",
       "heading": "<the clause heading as printed, or a
  short label if it has none>",
       "text": "<the clause's full original wording, copied
  exactly>",
       "clause_type": "<one label from the list below>"}
    ],
  "parties": ["<each party exactly as named in the contract>"],
 "contract_type": "<one of: nda, msa, sow, vendor, employment>",
 "key_dates": [{"label": "<what the date is, e.g. effective date>", "value": "<the date as written, or none stated>"}]
  }

  clause_type must be EXACTLY one of: parties, scope, payment, term_termination, confidentiality, ip, liability,
  indemnity, restraint, data_protection, governing_law, notices, boilerplate, other
  Use "other" only when nothing on the list fits. Keep the clauses in document order. Every clause of the contract must appear. """


def _clause_rows(move: dict) -> list:
    # turn the model's raw clause list into full Clause dicts, ids in document order
    raw_clauses = move.get("clauses")
    if not isinstance(raw_clauses, list):
        raw_clauses = []
    rows = []
    for c in raw_clauses:
        if not isinstance(c, dict):
            continue
        text = str(c.get("text", "")).strip()
        if not text:
            continue
        ctype = str(c.get("clause_type", "")).strip().lower()
        rows.append(
            {
                "clause_id": "",
                "number": str(c.get("number", "")).strip(),
                "heading": str(c.get("heading", "")).strip(),
                "text": text,
                "clause_type": ctype if ctype in CLAUSE_TYPES else "other",
                "findings": [],
                "proposal": None,
                "decision": None,
                "final_text": text,
            }
        )
    for i, row in enumerate(rows, start=1):
        row["clause_id"] = f"c{i:02d}"
    return rows


def extraction_agent(raw_text: str) -> dict:
    """One structuring read of the whole contract. Not a tool loop: it has no tools to call,
    so it is a single careful call with one repair retry."""
    prompt = f"{EXTRACTION_SYSTEM}\n\nContract text:\n{raw_text}\n\nYour JSON:"
    move, last_err = None, None
    for attempt in range(2):
        ask = prompt if attempt == 0 else (f"{prompt}\n\nYour previous reply was not valid JSON ({last_err}). Reply again with ONE valid JSON object, nothing else.")
        try:
            move = _parse(router.think(ask, max_new_tokens=4096))
            break
        except ValueError as e:  # json.JSONDecodeError is a ValueError
            last_err, move = str(e), None
    if move is None:
        return {"status": "extraction_failed", "error": "The text was readable but could not be split into clauses. A person needs to look at this one."}
    clauses = _clause_rows(move)
    if len(clauses) < 3:
        return {"status": "extraction_failed", "error": f"Only {len(clauses)} clause(s) could be identified. That is too few to review safely; a person needs to look at this one."}
    parties = move.get("parties")
    key_dates = move.get("key_dates")
    return {
        "clauses": clauses,
        "meta": {
            "parties": parties if isinstance(parties, list) else [],
            "contract_type": str(move.get("contract_type", "")).strip().lower(),
            "key_dates": key_dates if isinstance(key_dates, list) else [],
        },
    }
