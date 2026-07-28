# 09. Test Plan and Report

**Version 1, 2026-07-28.**

## 1. Strategy

| Layer | Cost | What it proves |
|---|---|---|
| Automated tests (`tests/`) | free, zero model calls | Shapes, rules, gates, storage, export, and the audit chain |
| Benchmark runs (`bench.py`) | GPU money | Whether the pipeline actually finds planted defects. See [10-benchmark-report.md](10-benchmark-report.md) |

The automated layer drives the application without starting it, with the model replaced by a fake that recognises each agent by the opening phrase of its prompt. That is why the inspector prompts' opening role phrases must not be reworded casually: the fake model identifies agents by them.

## 2. Running them

```bash
uv run python -m pytest tests/ -q
```

Use `python -m pytest`, not `pytest` alone, or collection fails to find the application package.

## 3. Coverage

**103 tests across ten files, green in a few seconds, no model calls and no GPU spend.**

| File | Tests | Covers |
|---|---|---|
| `test_api.py` | 17 | The endpoints: decision verdicts and their status codes, the finish gates, which text becomes the final wording, and that a precedent-store outage cannot block a lawyer signing off |
| `test_agents_base.py` | 14 | The reasoning loop: the step ceiling, duplicate-call blocking, unknown tool handling, and the JSON parser including the first-complete-object behaviour |
| `test_graph.py` | 14 | Node guards, the too-few-clauses stop, the fan-in reducer, and inspector status roll-up |
| `test_agents.py` | 12 | Agent output shapes against a fake model, finding stamping, and inspector context |
| `test_state.py` | 12 | Finding validation and the risk roll-up, including the zero-findings case |
| `test_store.py` | 11 | Postgres round trips, including clause decisions against a real database with its own cleanup |
| `test_intake.py` | 11 | File to text for each supported format |
| `test_audit.py` | 6 | The hash chain and its verifier |
| `test_export.py` | 4 | Document rewriting, including clauses that cannot be located |
| `test_vocabulary.py` | 2 | That no vocabulary from the sibling ticket system leaked into this one, with a small allowlist for legitimate legal English |

**Last recorded run: 103 passed.**

## 4. What testing has caught

- A helper that stamped findings was missing its return, so **every finding from all four inspectors would have been silently dropped**, with no error and no crash.
- Path resolution against the working directory, which would have quietly told all four inspectors that the rules pack and the templates did not exist, if the server were started from anywhere but the repository root.
- A parser that broke deterministically whenever the model emitted a second JSON object.
- A duplicated paste that left the whole API unable to import.

The lesson recorded from those: after any multi-part hand-paste, compile the package before doing anything else.

## 5. Known gaps

| Gap | Why it matters |
|---|---|
| No end-to-end test through a real model | Only paid benchmark runs exercise the whole nine-node path |
| No test asserting contract text never leaves for a third party | The claim rests on there being no cloud client in the codebase, which is strong but is not a test |
| No frontend tests | The review interface is verified by hand |
| Attribution and severity are measured only by the benchmark | There is no unit-level notion of the right inspector for a defect |

## 6. Test data

Thirteen synthetic contracts with **planted defects and known answers**, which is what makes recall measurable here in a way it is not in the sibling ticket system. Precedent seeds are deliberately built from different counterparties so they cannot leak answers into the benchmark.
