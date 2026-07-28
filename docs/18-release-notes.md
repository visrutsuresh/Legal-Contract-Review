# 18. Release Notes

**Version 1, 2026-07-28.** No version tags; 27 commits, from 2026-07-20 to 2026-07-27. Grouped by theme.

## 2026-07-27, reporting

- Per-contract risk panel and an exportable review report.
- Documentation corrections to the sign-in credentials.

## 2026-07-26, measurement

- **Full thirteen-contract benchmark committed:** recall 87.5 percent, all three deliberately removed clauses caught, zero errors, mean 429 seconds per contract.

## 2026-07-25, the document as the deliverable

- **Corrected-document export.** The reviewed contract is returned as the original file with only the changed clauses rewritten, matching each clause's original wording against a moving window of paragraphs. Uploads now keep the original bytes, which is why contracts uploaded before this change must be re-uploaded to export.
- Limits surfaced rather than silent: `.docx` only, and unlocatable clauses named in a response header and in the interface.
- **Fix:** the reasoning loop now takes the first complete JSON object from model output. The previous parse, from the first brace to the last, broke deterministically whenever the model emitted a second object. The identical bug existed in the sibling governance system and was fixed there too.

## 2026-07-24, making the model lane usable

Three layers of failure, all fixed in one session:

- **Timeouts:** the stack's ceilings were ordered smallest-first, so nothing could ever finish. Raised in the correct order, and the model later swapped for one that loads in about a minute rather than four to six.
- **Truncation:** every reasoning call used a small token ceiling, so a finish message carrying several nine-field findings was cut off mid-string. Raised.
- **Concurrency, the expensive one:** four inspectors fanning out made the platform start a second billed GPU whose model was still loading, so requests queued for minutes and died. The lane is now pinned to one container, calls are serialised client-side, and a stray server error is retried once.
- **Recall tuning, free, on a local model:** one contract went from 2 of 5 to 4 of 5, and an unseen one to 5 of 5 with zero unplanted noise. Four prompt fixes did it: a three-step working method, teaching the financial inspector that penalties are money terms, carrying mid-thought observations into the final findings, and correcting invented tool names.

## 2026-07-22, testing and the interface

- **The lawyer's desk:** docket with live stage narration, the two-pane redline review, and the people administration page.
- **Test suite** over every deterministic seam, no model calls.
- **Audit trail exposed** through an endpoint and a panel.
- **Precedent cabinet seeded** with eight fictional prior reviews, deliberately not drawn from the benchmark corpus so recall still means something.
- **Benchmark harness** scoring against the planted manifests.
- **Fixes:** tool paths anchored to the repository root rather than the working directory, which would otherwise have quietly told all four inspectors that the rules pack did not exist; fan-in now separates an incomplete finding from one naming an unknown clause; and a duplicated paste that left the API unable to import.

## 2026-07-21, the agents

- Tool registry, precedent store, and the four inspectors.
- Negotiation and summary agents, and the full nine-node graph.
- Lawyer decision endpoints, finish, and precedent filing.

## 2026-07-20, the fork

- Forked from the ticket-triage skeleton: stripped, authentication swapped to administrator-created accounts with no open signup, and its own database and vector stack on separate ports so both systems can run at once.
- Contract state, storage, and document intake for `.docx` and `.pdf`.
- Data: the template library, the rules pack, and thirteen synthetic contracts with planted-defect manifests.
- Shared reasoning loop and the extraction agent.

## Known issues carried forward

- The README still names an earlier, larger model than the code runs.
- A contract with zero findings is reported as low risk, indistinguishable from a slightly untidy one. Pinned by a test so changing it is deliberate.
- One low-severity planted defect is consistently missed, deliberately not chased to avoid tuning prompts to a single contract.
- Severity agreement is the weakest measured dimension at roughly three in five.
