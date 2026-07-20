"""Papyrus contract state: the case file every agent adds pages to.

The three shapes that live inside ContractState are documented here.
They are plain dicts, not classes, so they survive JSON round trips
(model output, Postgres JSONB, the API) untouched.

Clause = {
    "clause_id": "c04",           # stable id, assigned at extraction
    "number": "4",                # as printed in the document
    "heading": "Payment Terms",
    "text": "...original wording...",
    "clause_type": "payment",     # one of the vocabulary below
    "findings": [Finding],        # pinned here at fan-in (Task 30)
    "proposal": Proposal | None,  # ONE per clause, authored by negotiation
    "decision": None | "accepted" | "rejected" | "edited",  # the lawyer's call
    "final_text": "...",          # original text, the proposal, or the lawyer's edit
}

Finding = {
    "finding_id": "f-c04-fin-1",
    "clause_id": "c04",
    "inspector": "compliance" | "risk" | "template" | "financial",
    "severity": "high" | "medium" | "low",
    "plain": "You would wait four months to get paid.",        # human line first
    "term": "Net-120 payment term; your standard is net-30.",  # legal name second
    "wrong": "...", "change": "...", "ignore": "...",          # the trio, all required
    "evidence": "within one hundred and twenty (120) days",    # quote of the offending span
    "fix_hint": "net-30",   # optional, input to negotiation's proposal
}

Proposal = {
    "clause_id": "c04",
    "new_text": "...full replacement clause wording...",
    "del_span": "...", "ins_span": "...",   # what the diff strikes and inserts
    "based_on": ["f-c04-fin-1"],            # the finding ids it answers
}

clause_type vocabulary: parties, scope, payment, term_termination,
confidentiality, ip, liability, indemnity, restraint, data_protection,
governing_law, notices, boilerplate, other.
"""

import operator
from typing import Annotated, TypedDict

from app.audit import chain

INSPECTORS = ["compliance", "risk", "template", "financial"]


class ContractState(TypedDict):
    contract_id: str
    filename: str
    source_format: str  # docx | pdf | scanned
    status: str  # processing | extraction_failed | needs_review | reviewed | error
    stage: str  # narration key: reading | extracting | inspecting | negotiating | summarising | done
    meta: dict  # parties, contract_type, key_dates, pages
    raw_text: str  # intake's normalised plain text
    clauses: list  # list[Clause dict], ordered as in the document
    findings_raw: Annotated[list, operator.add]  # inspectors append here in parallel
    inspector_reports: Annotated[list, operator.add]  # [{"inspector": name, "status": "ok"|"failed", "note": str}]
    missing_clauses: list  # template-required clauses absent from the contract
    contract_risk: dict  # {"level": high|medium|low, "score": int, "why": str}
    negotiation_points: list  # [{"clause_id","ask","fallback","walk_away"}]
    summary: dict  # {"executive": str, "counts": {...}}
    audit: Annotated[list, chain]
    error: str | None


REQUIRED_FINDING_FIELDS = ("clause_id", "inspector", "severity", "plain", "term", "wrong", "change", "ignore", "evidence")


def valid_finding(f: dict) -> bool:
    return all(f.get(k) for k in REQUIRED_FINDING_FIELDS) and f["severity"] in ("high", "medium", "low")


def risk_rollup(clauses: list, missing: list) -> dict:
    sevs = [f["severity"] for c in clauses for f in c.get("findings", [])] + [m["severity"] for m in missing]
    score = min(100, sevs.count("high") * 25 + sevs.count("medium") * 10 + sevs.count("low") * 4)
    level = "high" if "high" in sevs else ("medium" if "medium" in sevs else "low")
    why = f"{sevs.count('high')} serious, {sevs.count('medium')} medium, {sevs.count('low')} minor issues"
    return {"level": level, "score": score, "why": why}
