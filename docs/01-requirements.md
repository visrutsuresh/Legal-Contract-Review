# 01. Requirements

**Version 1, 2026-07-28.** Authoritative source: the client requirement PDF in this folder, plus the project scope and design documents in the planning repository. Status is measured against the code, and the evidence is in [16-traceability-matrix.md](16-traceability-matrix.md).

## 1. Problem

Reviewing a commercial contract means reading every clause, comparing it against the firm's standard wording and rules, spotting what is missing as well as what is wrong, drafting replacement language, and explaining to a client what each issue actually means. It is slow, it is expensive, and the quality depends on which lawyer picked up the file.

## 2. What this product is

A multi-agent assistant **for a lawyer**. It reads an uploaded contract, splits it into numbered clauses, inspects every clause four ways in parallel, drafts replacement wording for what it flags, rolls the whole thing into a risk level and a plain-English summary, and hands it to a lawyer who accepts, rejects or edits **clause by clause**. Nothing is signed off without a human, and the corrected document can be exported with only the changed clauses rewritten.

Contracts never touch a cloud model. There is exactly one self-hosted model lane.

## 3. Functional requirements

| ID | Requirement | Status |
|---|---|---|
| FR-1 | Accept a contract as an uploaded file, normalise it to plain text, and identify its type, parties and key dates | MET, `.docx` and `.pdf` |
| FR-2 | Split the contract into numbered clauses with headings, original wording, and a clause type from a fixed vocabulary | MET |
| FR-3 | Inspect every clause for rule breaches, commercial risk, deviation from the firm's template, and financial terms | MET, four inspectors running in parallel |
| FR-4 | Identify required clauses that are **absent** from the contract, not only faults in what is present | MET |
| FR-5 | Every finding must carry a clause reference, an inspector, a severity, a plain-English line, the legal term, what is wrong, what to change, what happens if it is ignored, and a quote of the offending wording | MET, enforced by validation; incomplete findings are dropped and counted |
| FR-6 | Draft replacement wording for flagged clauses, with an ask, a fallback and a walk-away position | MET |
| FR-7 | Roll findings into a contract-level risk level and score, and an executive summary in plain English | MET |
| FR-8 | Let a lawyer accept, reject or edit each flagged clause, and record which | MET |
| FR-9 | Retrieve comparable prior reviews as precedent, so later contracts can cite earlier rulings | MET |
| FR-10 | Keep a tamper-evident audit trail of every pipeline step, readable through the API | MET, and verified against a forged database entry |
| FR-11 | Export the reviewed contract as the original document with only the changed clauses rewritten | MET for `.docx`; PDF is refused rather than silently mangled |
| FR-12 | Administer users: an administrator creates lawyer accounts; there is no open signup | MET |

## 4. Non-functional requirements

| ID | Requirement | Target | Status |
|---|---|---|---|
| NFR-1 | Contract text never reaches a third-party model | Zero exceptions | MET by construction: one lane, no cloud client in the codebase |
| NFR-2 | A whole contract review completes without human intervention | under 45 minutes | MET, measured mean 429 seconds over 13 contracts |
| NFR-3 | A stuck or crashed agent must not hang the review | Per-node guard | MET, guarded nodes with a 1200 second ceiling and a retry |
| NFR-4 | Parallel inspectors must not multiply GPU cost | One container | MET, single-container lane plus a client-side lock so calls queue |
| NFR-5 | A half-formed finding is never shown to a lawyer | Validation before display | MET |
| NFR-6 | The audit trail detects tampering | Detection, not prevention | MET |
| NFR-7 | Synthetic contracts only, secrets outside the repository | No real client data | MET |
| NFR-8 | Reuse the skeleton from the ticket-triage system | Module-level reuse | MET |

## 5. Out of scope

No scanned-document handling beyond text extraction, no optical character recognition, no signature or execution workflow, no matter management or billing, no jurisdiction-specific legal advice, and no automatic sending of anything to a counterparty. The system produces a marked-up document for a lawyer; the lawyer decides what leaves the building.

## 6. Known requirement gaps

- Attribution is imperfect: a planted defect is often caught by a different inspector than the one that should have caught it. Recall is what matters and it is measured; attribution is reported honestly at 71 percent.
- A contract with no findings is reported as low risk, which is indistinguishable from a slightly untidy one. This is pinned by a test so that changing it is a deliberate act.
