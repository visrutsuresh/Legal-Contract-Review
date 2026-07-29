# 06. Decision Log (Architecture Decision Records)

**Version 1, 2026-07-28.**

---

## ADR-001. Fork the ticket-triage skeleton rather than start fresh

**Context.** A second multi-agent system was needed in days, not weeks, and a working skeleton already existed.
**Options.** Build from scratch; extract a shared library first; copy the repository and adapt.
**Decision.** Copy-fork, strip the domain, swap the authentication model, keep the pipeline shape.
**Consequences.** The system was standing in days. The cost is real duplication, since several modules now exist in more than one repository, which has already caused a bug fixed twice. The plan to replace copies with a shared package is recorded in the planning repository.

---

## ADR-002. One model lane, no cloud, no tier switch

**Context.** Contracts are confidential by nature. The ticket system's routing grid exists because some tickets are safe to send to a provider; here none are.
**Decision.** Exactly one lane, a self-hosted open-weight model on a serverless GPU. No cloud client, no key, no switch.
**Consequences.** The privacy claim is provable by reading the code rather than by trusting a rule. The cost is that model quality is capped by what fits on a rented GPU, and every measurement run costs money.

---

## ADR-003. Four inspectors in parallel, merged by plain code

**Context.** A clause can be wrong in unrelated ways: it can breach a rule, carry commercial risk, deviate from the standard, or be financially wrong.
**Options.** One agent with a long prompt; four agents in sequence; four in parallel.
**Decision.** Four in parallel, each writing only to append-only keys, merged by a plain-code fan-in that pins findings to clauses, drops invalid ones and rolls up risk.
**Consequences.** Each inspector has a short, sharp prompt, and the merge is reproducible because it is not a model. The cost is that attribution blurs: an inspector often catches a defect belonging to another's beat, which is why the benchmark reports recall and attribution separately.

---

## ADR-004. A finding is worthless unless it is complete

**Context.** Early output produced fragments: a severity with no evidence, a complaint with no fix.
**Decision.** Nine fields are required, including a plain-English line, a quote of the offending wording, and what happens if it is ignored. A finding missing any of them is dropped and counted.
**Consequences.** What a lawyer sees is always actionable. The cost is fewer findings, and a stricter dependency on model obedience.

---

## ADR-005. Absence is a finding

**Context.** The dangerous defect in a contract is often a clause that is simply not there.
**Decision.** The template inspector reports required clauses that are missing, and they roll into risk exactly like faults in present clauses.
**Consequences.** The benchmark tracks them separately and all three planted omissions were caught.

---

## ADR-006. The human gate is per clause, not per document

**Context.** A contract review is not one decision; it is dozens.
**Decision.** Every flagged clause needs an explicit accept, reject or edit, and the review cannot be finished until they all have one.
**Consequences.** Sign-off is meaningful and traceable. The cost is more clicks, which is the correct trade for legal work.

---

## ADR-007. Export rewrites the original document

**Context.** A lawyer's deliverable is the document, not a web page.
**Options.** Generate a fresh document from the clause list; produce a change list; rewrite the original in place.
**Decision.** Rewrite the original, matching each changed clause against a moving window of paragraphs, keeping the first paragraph's style.
**Consequences.** Formatting, numbering and everything untouched survive. The limits are real and surfaced rather than hidden: `.docx` only, and any clause that cannot be located is named for manual fixing.

---

## ADR-008. Precedent seeds must not come from the benchmark corpus

**Context.** The precedent cabinet is empty on a fresh machine, so early contracts get nothing from it.
**Decision.** Seed eight fictional prior reviews covering the same classes of term as the benchmark, with different counterparties, tagged as seeds.
**Consequences.** Cold start is solved without letting an inspector retrieve a planted defect instead of finding it, which would have made the recall number meaningless.

---

## ADR-009. Pin the lane to a single container and serialise calls

**Context.** Four inspectors fan out at once. The platform responded by starting a second billed GPU, whose model was still loading, so requests queued for minutes and then failed.
**Decision.** Cap the lane at one container, add a client-side lock so parallel nodes queue, and retry once on a stray server error.
**Consequences.** Predictable cost and no mid-run container swaps. The cost is that the four inspectors run one after another in practice, which is most of the wall-clock time per contract.

---

## ADR-010. Take the first complete JSON object from model output

**Context.** Parsing from the first brace to the last broke deterministically whenever the model emitted a second object after its answer.
**Decision.** Decode the first complete object with a streaming decoder.
**Consequences.** A whole class of deterministic failure disappeared. The same bug existed in the sibling governance system and was fixed there in the same session.

---

## ADR-011. Do not change the risk roll-up before collecting numbers

**Context.** A contract with zero findings is reported as low risk, which is indistinguishable from a slightly untidy one.
**Decision.** Leave it, and pin today's behaviour with a test, rather than change risk semantics immediately before a measurement run.
**Consequences.** The benchmark numbers are comparable. The oddity is documented, and changing it later will break the test loudly rather than silently.

---

## ADR-012. Roll back the vLLM + AWQ lane, keep the tolerant JSON parser

**Context.** On 2026-07-28 the lane moved from one-at-a-time transformers generation with a bitsandbytes-quantised model to vLLM serving the official AWQ checkpoint, batching up to 8 requests in one container. It was 3.3x faster on a single contract, but that same contract scored recall 3/5 against the earlier run's 5/5. One contract could not separate quantisation damage from run noise, so the decision was deferred and the headline benchmark numbers in these documents still described the old stack.

**What was measured, 2026-07-29.** The full 13-contract benchmark was rerun on vLLM, after fixing a parser bug found on the way (below), so the comparison is like for like against the committed `bench_papyrus.json`.

| | bitsandbytes | vLLM + AWQ |
|---|---|---|
| Detection recall | 35/40 = **87.5%** | 27/40 = **67.5%** |
| Findings produced | 109 | 69 |
| Severity agreement | 62.9% | 59.3% |
| Extraction succeeded | 13/13 | 11/13 |
| Mean latency | 429s | **144.8s** |

The speed was real and reproducible: 3.0x. The quality loss was also real, concentrated rather than diffuse (`nda_kestrel` 5/5 to 2/5, `vendor_larkspur` 5/5 to 3/5), and it survived excluding the contracts whose extraction failed. `vendor_brightquay.pdf` additionally stopped extracting at all, stranding five planted defects.

**Options.** Keep vLLM and restate the benchmark numbers downward; keep it and try to recover recall through prompt work; roll back.

**Decision.** Roll back. Recall is the product in contract review, and 3.0x speed does not buy back twenty points of it. A slow demonstration is survivable; one that misses a fifth of the planted defects is not. The lane returns to bitsandbytes and both routers return to the client-side lock.

**Consequences.** Per-contract latency goes back to roughly seven minutes, which the demonstration must be planned around: warm the lane first and prefer the recorded fallback. Rolling back also restores the validity of every benchmark number already published in both systems' documents, which removes the contradiction that had opened between the model cards and the benchmark reports.

**One change from the episode is deliberately KEPT**, because it is a real defect independent of the swap: `_parse` now falls back to a tolerant read when the model emits Python literals (`True`, `False`, `None`) inside otherwise valid JSON. Strict JSON rejected the entire reply, so a 7kB template-inspector answer containing real findings was discarded over one capital letter, and `temperature=0` meant the retry reproduced the failure exactly rather than recovering. Both attempts failed identically and the inspector reported nothing. The fallback is string-aware, so a finding whose text merely mentions the word True is untouched. Applied to both this system and the governance sibling, which share the parser.
