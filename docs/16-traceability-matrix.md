# 16. Traceability Matrix

**Version 1, 2026-07-28.** Each requirement from [01-requirements.md](01-requirements.md), the code that satisfies it, and the test or measurement that proves it.

## Functional

| Req | Verdict | Code | Proof |
|---|---|---|---|
| FR-1 upload and normalise, identify type, parties, dates | MET | `POST /contracts`, `app/intake.py`, extraction agent | `test_intake.py` (11 tests); benchmark extraction 13 of 13 |
| FR-2 clause splitting with types | MET | `extraction_agent` in `app/agents.py`, vocabulary in `app/state.py` | `test_agents.py`; benchmark |
| FR-3 four-way inspection | MET | Four inspector agents, parallel step in `app/graph.py` | `test_agents.py`, `test_graph.py`; benchmark recall 87.5% |
| FR-4 missing clauses reported | MET | Template inspector, `missing_clauses` in the state | Benchmark: 3 of 3 caught |
| FR-5 findings complete or discarded | MET | `valid_finding()` in `app/state.py`, `_stamp` in `app/agents.py` | `test_state.py` (12 tests) |
| FR-6 replacement wording with ask, fallback, walk-away | MET | `negotiation_agent` | `test_agents.py`; benchmark |
| FR-7 risk roll-up and executive summary | MET | `risk_rollup()` in `app/state.py`, `summary_agent` | `test_state.py`, including the zero-findings case |
| FR-8 clause-by-clause accept, reject, edit | MET | `POST /contracts/{id}/clauses/{clause_id}/decision` | `test_api.py`: verdicts, status codes, which text becomes final |
| FR-9 precedent retrieval | MET | `app/precedent.py`, `precedent_search` tool | `test_api.py` proves an outage cannot block sign-off; seeding proven live |
| FR-10 tamper-evident audit, readable | MET | `app/audit.py`, `GET /contracts/{id}/audit` | `test_audit.py` (6 tests); verified live against a forged database row |
| FR-11 export the corrected document | MET | `app/export.py`, `GET /contracts/{id}/export` | `test_export.py` (4 tests) including unlocatable clauses |
| FR-12 administrator-created accounts, no open signup | MET | `app/users.py`, the users endpoints | `test_api.py` role gates |

## Non-functional

| Req | Verdict | Evidence |
|---|---|---|
| NFR-1 no third-party model | MET | One lane in `app/router.py`; no cloud client exists in the codebase. **Not covered by a test**, which is the one gap worth closing |
| NFR-2 unattended review completes | MET | Benchmark mean 429 seconds, 0 errors over 13 contracts |
| NFR-3 a stuck agent cannot hang the review | MET | `guarded()` in `app/graph.py`; `test_graph.py` covers node guards |
| NFR-4 parallel inspectors do not multiply cost | MET | Single-container lane plus the lock in `app/router.py` |
| NFR-5 no half-formed finding reaches a lawyer | MET | `valid_finding()`, with drops counted at fan-in; `test_state.py`, `test_graph.py` |
| NFR-6 tampering detectable | MET | `test_audit.py` plus the live forged-row check |
| NFR-7 synthetic data, secrets outside the repository | MET | 13 synthetic contracts with manifests; ignored environment file |
| NFR-8 reuse of the skeleton | MET | Forked from the ticket system; duplication measured in the planning repository |

## Coverage summary

103 automated tests, no model calls, covering every deterministic seam: shapes, validation, the reasoning loop, node guards, the fan-in reducer, storage, export, the audit chain, the endpoint gates, and a check that no vocabulary from the sibling ticket system leaked in.

The two things automated tests do **not** cover are stated plainly: the full nine-node path through a real model, which only the paid benchmark exercises, and an assertion that contract text can never leave for a third party, which today rests on the absence of any cloud client rather than on a test.
