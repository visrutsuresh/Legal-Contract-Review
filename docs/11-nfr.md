# 11. Non-Functional Requirements

**Version 1, 2026-07-28.**

## 1. Performance

| Property | Target | Measured |
|---|---|---|
| Full contract review | minutes, unattended | mean 429 seconds over 13 contracts, warm lane |
| First call after the lane idles | under two minutes | roughly 60 to 90 seconds |
| Per-node ceiling | bounded, with one retry | 1200 seconds per guarded node |
| Whole-contract ceiling in the benchmark | bounded | 2700 seconds |
| Upload response | immediate | The file is stored and an id returned before any model runs |

The dominant cost is deliberate: four inspectors queue on one GPU container rather than running truly in parallel, because letting the platform start a second container doubled the bill and broke mid-run.

## 2. Scale

Single concurrent user, one contract at a time, a corpus in the low tens. Contracts of about nine to fourteen clauses are the tested size. Nothing here is designed for a firm's real caseload.

## 3. Availability

No availability target and no failover. The narrower guarantee that is met: **a failure never loses a review and never hides itself.** A node that fails records the failure in the state, the other inspectors still produce findings, and the review reaches the lawyer with the gap visible. A document that could not be read stops with an explicit extraction failure rather than being inspected on empty text.

## 4. Privacy

| Requirement | Status |
|---|---|
| Contract text never reaches a third-party model | Met by construction: one lane, and no cloud client anywhere in the codebase |
| Embeddings computed locally | Met |
| Original documents stored locally | Met, kept as bytes in the local database |
| No open signup | Met, an administrator creates every account |

This is a stronger position than the sibling ticket system, which has a cloud lane for non-sensitive work. Here the question does not arise.

## 5. Auditability

Every step appends to a hash chain stored with the contract and verified when read through the audit endpoint, which reports the first broken index. This has been tested against a row forged directly in the database and the break was reported at the exact index. The chain proves tampering; it does not prevent it.

## 6. Quality bar

A finding must carry all nine required fields or it is discarded before display. That is a deliberate quality-over-quantity choice: the measured recall of 87.5 percent is achieved **after** dropping incomplete findings, not before.

## 7. Cost

The GPU lane bills per warm window. A full benchmark of thirteen contracts is roughly an hour and a half of GPU time and is the single largest cost in the project. Controls: a hard platform spend cap, a single-container lane, a single-contract switch as a cost fence, and batching every paid check into one warm window.

## 8. Maintainability

The system is a fork of the ticket-triage skeleton, and several modules are near-identical to their siblings. That duplication is measured, and the decision to replace it with a shared package after the deadline is recorded in the planning repository. Until then, a fix in a shared-looking module should be checked in all three repositories.
