# 15. Risk Register

**Version 1, 2026-07-28.** Likelihood and impact are low, medium or high.

## Open risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | A live demonstration runs on a cold lane, so a review takes far longer than the audience will wait | Medium | High | Warm the lane ten minutes ahead, keep a finished review in the docket, and follow the demo script |
| R-2 | GPU spend exhausts the credit before the work is finished | Medium | High | Hard platform cap, single-container lane, a one-contract cost fence, and batching every paid check into one warm window |
| R-3 | Severity judgement is only about three in five correct, and severity drives the risk roll-up | High | Medium | Reported openly in the benchmark. The first quality work to resume if time allows |
| R-4 | A fifth of findings are unplanted, and some may be noise a lawyer must wade through | Medium | Medium | Findings must be complete and carry evidence, so each is quick to dismiss. Not separable without a second reviewer |
| R-5 | Prompt injection inside a contract steers or suppresses a finding | Medium | Medium | Evidence quotes and the clause-by-clause human gate. Not systematically tested, and this product is an obvious target for it |
| R-6 | Export matches the wrong paragraph in an unusual document | Low | Medium | Matching is on the clause's original wording, and anything unlocatable is named rather than guessed |
| R-7 | The precedent cabinet mixes clients, which would be a real confidentiality problem outside a demonstration | Low here, High in production | High | Documented as the largest design change needed before real use |
| R-8 | Duplicated modules mean a bug fixed here is left unfixed in the sibling systems | Medium | Medium | The duplication is measured and the shared-package plan is written. Two such bugs have already occurred |
| R-9 | The README describes an older model than the code runs | Certain, already true | Low | Corrected in the model card; the README line should be updated |
| R-10 | No per-matter access control | Low here, High in production | High | Named as the first control to add before real client documents |

## Closed risks

| # | Risk | How it closed |
|---|---|---|
| C-1 | The model took four to six minutes to load, so a cold call could never answer | Timeouts raised in the right order, then a smaller model that loads in about a minute |
| C-2 | Parallel inspectors woke a second billed GPU whose model was still loading, killing runs mid-way | Single-container lane, a client-side lock, and one retry on a stray server error |
| C-3 | Every finding from all four inspectors would have been silently dropped by a helper missing its return | Caught by reading the code after a hand-paste; the standing rule is now to compile after any multi-part paste |
| C-4 | All four inspectors could have been silently told the rules pack did not exist, if the server were started from another directory | Paths anchored to the code rather than the working directory, and verified from a foreign directory |
| C-5 | A second JSON object in the model's output broke parsing deterministically | The parser takes the first complete object |
| C-6 | The precedent cabinet was empty on a fresh machine, so early contracts got nothing from it | Eight seeded fictional reviews, deliberately not drawn from the benchmark corpus |
| C-7 | The audit chain was built but never exposed or verified | Exposed through an endpoint, verified on read, and tested against a forged database row |
