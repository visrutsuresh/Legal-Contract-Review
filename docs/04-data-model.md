# 04. Data Model

**Version 1, 2026-07-28.** Two stores: Postgres holds one row per contract, Weaviate holds finished reviews as searchable precedent.

## 1. Postgres, database `contracts`

Created at startup by an idempotent initialiser. New columns are added in the same place with `ADD COLUMN IF NOT EXISTS`, so an existing database migrates itself on boot.

### `contracts`

| Column | Type | Meaning |
|---|---|---|
| `contract_id` | TEXT, primary key | Identity of the review |
| `filename` | TEXT | The uploaded file's name |
| `status` | TEXT | `processing`, `extraction_failed`, `needs_review`, `reviewed`, `error` |
| `stage` | TEXT | Narration for the docket: reading, extracting, inspecting, negotiating, summarising, done |
| `risk_level` | TEXT | `high`, `medium`, `low`, rolled up from the findings |
| `state` | JSONB | The entire pipeline state: clauses, findings, proposals, decisions, summary, audit chain |
| `created_at` | TIMESTAMPTZ | Upload time |
| `file_bytes` | BYTEA | The original uploaded document, kept so export can rewrite it in place |

Status, stage and risk are duplicated out of the state as real columns because the docket lists and filters on them; everything else is read from the JSON.

### Accounts

Managed by the authentication library: id, email, hashed password, active flag, and a `role` of `lawyer` or `admin`. **There is no open signup and no customer role.** An administrator creates every account.

## 2. The shapes inside `state`

### Clause

| Field | Meaning |
|---|---|
| `clause_id` | Stable id assigned at extraction, for example `c04` |
| `number`, `heading` | As printed in the document |
| `text` | The original wording |
| `clause_type` | One of fourteen: parties, scope, payment, term and termination, confidentiality, intellectual property, liability, indemnity, restraint, data protection, governing law, notices, boilerplate, other |
| `findings` | The findings pinned to this clause at fan-in |
| `proposal` | At most one replacement, authored by the negotiation agent |
| `decision` | `accepted`, `rejected`, `edited`, or nothing yet |
| `final_text` | The original wording, the proposal, or the lawyer's own edit |

### Finding

Nine fields are required, and a finding missing any of them is discarded before a lawyer ever sees it: the clause it belongs to, which inspector raised it, severity, a plain-English line, the legal term, what is wrong, what to change, what happens if it is ignored, and a quote of the offending wording. An optional hint feeds the negotiation agent.

The plain-English line comes first by design: the product's claim is that a non-lawyer can understand why a clause is a problem.

### Proposal

The clause it replaces, the full replacement wording, the struck span and the inserted span for the redline view, and the finding ids it answers.

### Missing clause

A required clause that is absent from the document, with a severity. Absence is treated as a first-class finding rather than a footnote.

## 3. Weaviate, collection `Precedent`

| Property | Meaning |
|---|---|
| Title and summary of a prior review | What the search returns |
| Contract type | For filtering by like-for-like |
| `source` | `seed` for the cold-start entries, otherwise a real filed review |

Search has a relevance floor, and embeddings are computed locally so no contract text is sent anywhere to be indexed.

**Integrity point, deliberately preserved:** the seeded precedent entries are *not* built from the benchmark contracts. If they were, an inspector could retrieve a planted defect instead of finding it, and the recall number in [10-benchmark-report.md](10-benchmark-report.md) would measure nothing. The seeds cover the same classes of term with different counterparties.

## 4. Audit chain

Every pipeline step appends an entry holding the step, the previous entry's hash, and its own. The chain is stored inside the state and read back through the audit endpoint, which verifies it on read and reports the first broken index. This has been tested against a forged row written directly into Postgres, and the break was reported at the exact index.

## 5. Retention

Contracts, their state, and the original bytes are kept indefinitely. Finished reviews are additionally copied into the precedent cabinet. There is no purge, no retention schedule, and no deletion workflow. All contracts in the system are synthetic.

## 6. Backup and recovery

Both stores are Docker volumes on the developer machine. Recovery means re-running the seed scripts: accounts, and the precedent cold start. There is no scheduled backup, which is acceptable only because the data is synthetic and reproducible.
