# 10. Benchmark Report

**Version 1, 2026-07-28.** Raw results are committed as `bench_papyrus.json`.

## 1. Method

Thirteen synthetic contracts, each carrying **planted defects with known answers**, plus three contracts with a required clause deliberately removed. `bench.py` runs each contract through the full nine-node pipeline on the live model lane and scores:

| Measure | Definition |
|---|---|
| Recall | Planted defects the system found, as a share of those planted |
| Attribution | Of those found, the share caught by the inspector whose beat it is |
| Severity | Of those found, the share given the expected severity |
| Unplanted rate | Findings raised that were not planted |
| Missing-clause recall | Deliberately removed clauses that were reported as absent |
| Extraction | Contracts whose clauses were read successfully |
| Latency | Wall clock per contract |

## 2. Results, full corpus

| Measure | Result |
|---|---|
| Contracts | 13 |
| Errors | **0** |
| Extraction succeeded | 13 of 13 |
| Planted defects found | **35 of 40, recall 87.5%** |
| Correct inspector | 71.4% |
| Correct severity | 62.9% |
| Missing clauses caught | **3 of 3** |
| Total findings raised | 109 |
| Unplanted findings | 25, which is 22.9% |
| Mean latency | 429 seconds per contract |
| Total run | 5,577 seconds |

An earlier single-contract probe on the same lane returned recall 5 of 5 with zero unplanted noise, in 490 seconds.

## 3. What these numbers mean

- **Recall is the number that matters and it is high.** The system finds roughly seven of every eight planted defects, and caught every deliberately removed clause. For a review assistant whose output a lawyer checks clause by clause, recall is worth more than precision.
- **Attribution is mediocre and that is acceptable.** Nearly three in ten found defects were caught by a different inspector than the one whose beat it is. The defect is still surfaced with full evidence, so the lawyer sees it. It matters only for explaining which agent does what.
- **Severity agreement is the weakest measure**, at roughly three in five. Severity drives the risk roll-up, so this is the number to improve first if quality work resumes.
- **About a fifth of findings were unplanted.** Some are genuine issues the corpus author did not plant, and some are noise. Without a second reviewer they cannot be separated, so the figure is reported raw rather than adjusted.
- **Seven minutes per contract** is the cost of four inspectors queueing on a single GPU container, which is a deliberate cost decision, not a performance bug.

## 4. Limits, stated plainly

- Thirteen contracts is a batch, not a statistical sample. No confidence intervals are claimed.
- The corpus is synthetic and written by the same person who built the system, which is the strongest bias in these numbers.
- The precedent cabinet is deliberately seeded from different counterparties, so no inspector can retrieve a planted answer rather than finding it. This is why the recall figure means something.
- Latency assumes a warm lane; a cold start adds about a minute.
- One low-severity planted defect is known to be missed consistently and was deliberately not chased, to avoid tuning the prompts to one contract.

## 5. Earlier measurement, for contrast

Before the prompt work, the same pipeline on a smaller locally hosted model scored 2 of 5 on one contract. Four targeted prompt fixes, none of them model changes, took that to 4 of 5 on the same contract and 5 of 5 on an unseen one with zero unplanted noise. The fixes were: a three-step working method telling an inspector to sweep every clause to the last; teaching the financial inspector that penalties are money terms even without a payment schedule; making the loop carry issues noticed mid-thought into the final findings; and correcting invented tool names instead of failing.

That sequence is the useful story: the gains came from telling the agents how to work, not from a larger model.

## 5a. The vLLM + AWQ trial, and why the numbers above still stand

On 2026-07-28 the lane was swapped to vLLM serving the official AWQ checkpoint, for speed. On 2026-07-29 the **full corpus was rerun on that stack** and the swap was rolled back. Both result files are in the repository, so the comparison can be checked rather than taken on trust: `bench_papyrus.json` is the shipped stack, `bench_papyrus_vllm_13.json` is the trial.

| | bitsandbytes (shipped) | vLLM + AWQ (rejected) |
|---|---|---|
| Detection recall | **87.5%** | 67.5% |
| Findings produced | 109 | 69 |
| Severity agreement | 62.9% | 59.3% |
| Extraction succeeded | 13/13 | 11/13 |
| Mean latency | 429s | **144.8s** |

Three times faster, twenty points less recall. The decision and its reasoning are ADR-012.

Two things are worth recording about how this was measured. The first rerun attempt was **abandoned partway** because the log showed inspectors failing to parse their own output; continuing would have measured a bug rather than a model. The cause was the model emitting Python literals inside its JSON, which made strict parsing discard entire inspector answers. That was fixed first, and only then was the comparison run, so the 67.5% is the model's real performance and not an artifact.

The second: a single contract had suggested this same conclusion a day earlier, at 3/5 against 5/5. That signal was correct, but it was **not trustworthy at the time** and was rightly not acted on, because one contract cannot separate quantisation damage from ordinary run-to-run variation. Thirteen can.

## 6. Reproducing

```bash
uv run python bench.py --only kestrel     # one contract, the cost fence
uv run python bench.py                    # the full corpus, one warm window
```

Each run costs real GPU money. Warm the lane first and never run the corpus one contract at a time.
