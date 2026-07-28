# 03. Low-Level Design

**Version 1, 2026-07-28.**

## 1. The state object

One dictionary flows through the pipeline. Two keys are append-only reducers, which is what makes the parallel inspector step safe.

| Key | Written by | Holds |
|---|---|---|
| `contract_id`, `filename`, `source_format` | intake | Identity and the document format |
| `status` | several | `processing`, `extraction_failed`, `needs_review`, `reviewed`, `error` |
| `stage` | every node | Narration key the docket polls: reading, extracting, inspecting, negotiating, summarising, done |
| `meta` | extraction | Parties, contract type, key dates, pages |
| `raw_text` | intake | Normalised plain text |
| `clauses` | extraction, then fan-in | The clause list, each with findings, a proposal, a decision and final wording |
| `findings_raw` | four inspectors, append-only | Every finding before validation |
| `inspector_reports` | four inspectors, append-only | Per inspector: ok or failed, plus a note |
| `missing_clauses` | template inspector | Required clauses absent from the document |
| `contract_risk` | fan-in | Level, score and a one-line why |
| `negotiation_points` | negotiation | Ask, fallback and walk-away per clause |
| `summary` | summary | Executive text and counts |
| `audit` | every node | The hash chain, append-only |

## 2. The three shapes

**Clause**: a stable id, the printed number, heading, original wording, a type from a fixed vocabulary of fourteen, its findings, at most one proposal, the lawyer's decision, and the final text.

**Finding**: a finding id, the clause it belongs to, which inspector raised it, a severity, a plain-English line, the legal term, what is wrong, what to change, what happens if it is ignored, a quote of the offending wording, and an optional hint for the fix.

**Proposal**: the clause it replaces, the full replacement wording, the span struck and the span inserted for the redline, and the finding ids it answers.

A finding is discarded unless **all nine required fields are present** and the severity is one of high, medium or low. Half-formed findings are counted, never shown.

## 3. The reasoning loop

Each inspector is a ReAct agent: it thinks, may call a tool, reads the result, and repeats, up to six steps, after which it must produce its findings. Three details matter:

- **Parsing takes the first complete JSON object** from the model's output, using a streaming decoder. The earlier version sliced from the first brace to the last, which broke deterministically whenever the model emitted a second object after its answer.
- **A generous token ceiling per call.** A finding carries nine fields, so several findings in one answer will exceed a small limit and be cut off mid-string. Truncation shows up as a parse failure at the identical character on both attempts, which is the fingerprint to recognise.
- **Unknown tool names are corrected** with the real options rather than failing the step.

The three tools are read-only: fetch the firm's template for a contract type, read the rules pack, and search the precedent cabinet. All three resolve their paths relative to the code, not the working directory, so launching the server from elsewhere cannot silently tell every inspector that the rules do not exist.

## 4. Guards and failure handling

Every node is wrapped in a guard that gives it a bounded wall-clock and one retry, then records the failure in the state rather than raising into the framework.

| Failure | Behaviour |
|---|---|
| Fewer than three clauses extracted | The review stops with `extraction_failed`; a document that could not be read is never inspected |
| One inspector fails both attempts | Its report is marked failed with a note; the other three still produce findings and the review continues |
| Negotiation or summary fails | The review still reaches the lawyer with findings; the missing part is visible |
| The model lane returns a stray server error | One retry, because a container swap mid-run surfaces exactly this way |
| Parallel calls arriving together | A client-side lock serialises them onto the single container, so the platform never wakes a second billed GPU |

## 5. Fan-in, in plain code

Fan-in is deliberately not an agent. It pins each valid finding to its clause by id, separates an incomplete finding from one naming a clause that does not exist, counts both, rolls severities into a contract risk level and a score, and normalises the capitalisation the model sometimes returns. Doing this in code rather than in a prompt is what makes the numbers reproducible.

## 6. Export

Export rewrites the **original** document rather than generating a new one: it matches each changed clause's original wording against a moving window of paragraphs, keeps the first paragraph's style, and collapses the rest of the matched span. Clauses it cannot locate are named in a response header and surfaced in the interface as a fix-by-hand note. A PDF upload is refused with a clear status rather than mangled, and a contract uploaded before the feature existed is refused with a re-upload instruction.

## 7. Module map

| Module | Responsibility |
|---|---|
| `api.py` | Endpoints, authentication, background processing |
| `app/graph.py` | Nine nodes, guards, conditional edge after extraction |
| `app/agents.py` | Six agent prompts plus finding stamping and inspector running |
| `app/agents_base.py` | The reasoning loop and the JSON parser |
| `app/tools.py` | The three read-only tools and the registry |
| `app/router.py` | The single model lane, lock, retry, timeout |
| `app/store.py` | Postgres access |
| `app/precedent.py` | Weaviate collection, lazy embedding load |
| `app/export.py` | Document rewrite |
| `app/intake.py` | File to text |
| `app/state.py` | Shapes, validation, risk roll-up |
| `app/audit.py` | Hash chain |
| `app/users.py` | Accounts, roles, sessions |
| `app/report.py` | The printable review report |
