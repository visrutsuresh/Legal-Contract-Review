# 14. Model Card

**Version 1, 2026-07-28.**

## 1. The model

| Property | Value |
|---|---|
| Model | Qwen2.5-14B-Instruct, 4-bit quantised (the official AWQ checkpoint since 2026-07-28) |
| Serving | vLLM since 2026-07-28; previously one-at-a-time transformers generation. Up to 8 requests batch continuously on the one GPU, so parallel inspectors genuinely run in parallel |
| Host | Serverless GPU (A10G), single container, five-minute warm window |
| Lanes | **One.** No cloud model, no tier switch, no fallback |
| Embeddings | A small local model, computed on the machine |
| Sampling | Greedy, so runs are as reproducible as the model allows |
| Token ceiling per call | Generous, because a finding carries nine fields and several findings in one answer will otherwise be truncated |

**Why this model and not a bigger one.** An earlier, larger model (Qwen3-30B-A3B) was tried first and abandoned on 2026-07-24. It took four to six minutes to load, which exceeded every timeout in the stack and made a cold call impossible to answer, and it needed cards costing roughly twice as much. The 14B model loads in about a minute, which is what makes a cold demo call survivable. The comment at the top of `modal_lane/llm_service.py` records the swap.

## 2. What the model is asked to do

| Agent | Output contract |
|---|---|
| Extraction | Clause list with numbers, headings, wording and types, plus parties, contract type and dates |
| Compliance | Findings against the firm's rules pack |
| Risk | Findings on liability, indemnity, intellectual property, renewal, restraint |
| Template | Deviations from the standard, and required clauses that are absent |
| Financial | Findings on payment terms, increases, interest, penalties, totals |
| Negotiation | One replacement clause per flagged clause, with ask, fallback and walk-away |
| Summary | Executive text and counts |

Each inspector runs as a reasoning loop with up to six steps and three read-only tools.

## 3. Measured behaviour

From the thirteen-contract benchmark: recall 87.5 percent of planted defects, all three deliberately removed clauses caught, correct inspector 71 percent, correct severity 63 percent, roughly one finding in five unplanted, zero errors, mean 429 seconds per contract. Full detail and caveats in [10-benchmark-report.md](10-benchmark-report.md).

## 4. Known failure modes

| Failure | How it shows | What contains it |
|---|---|---|
| Truncated output | A parse failure at the identical character on both attempts | A generous token ceiling; the fingerprint is documented so it is not mistaken for randomness |
| A second JSON object after the answer | Parse failure that repeats deterministically | The parser takes the first complete object |
| An inspector burns its loop repeating one tool, then concludes nothing is wrong | A confident empty result on a contract that clearly has issues | An explicit three-step working method in the prompt: use the tool, then sweep every clause to the last, then report every issue including ones noticed mid-thought |
| An issue spotted in an early thought is forgotten by the final answer | A finding that appears in the reasoning but not the output | The loop's finish instruction requires carrying earlier observations into the findings |
| An invented tool name | A wasted step | Unknown names are corrected with the real options |
| Attribution drift | A defect caught by the wrong inspector | Accepted and measured; the finding still reaches the lawyer |
| Severity disagreement | Risk roll-up skewed | Known weakest measure, at roughly three in five |
| Cold container | The first call after idle takes about a minute | Warm the lane before a demonstration |

## 5. What is not measured

Precision cannot be separated from genuine discovery: a fifth of findings were not planted, and some of those are real issues the corpus author missed. There is no second reviewer, so that figure is reported raw. There is also no measure of whether a proposed replacement clause is legally sound; a lawyer decides that, which is the entire point of the clause-by-clause gate.

## 6. Appropriate and inappropriate use

Appropriate: a first pass over a commercial contract, producing evidence-carrying findings and draft replacement wording that a lawyer reviews clause by clause.

Inappropriate: any use where the output is acted on without a qualified human reading it; jurisdiction-specific advice; execution or signature workflows; real client documents before the confidentiality gaps in [13-privacy-and-data-handling.md](13-privacy-and-data-handling.md) are closed.

## 7. Human oversight

Nothing is finished without a decision on every flagged clause. The final wording of every clause is either the original, the proposal a lawyer accepted, or the lawyer's own edit. Export writes only what was decided.
