# 17. User Guide

**Version 1, 2026-07-28.** For the lawyer using the system, and the administrator running it.

## 1. Signing in

There is no self-service signup. An administrator creates your account and gives you the address and password. Sign in and you land on the docket.

## 2. The docket

The docket is the list of contracts. Each row shows the file, its status, its stage while it is being worked on, and its risk level once finished.

Drop a `.docx` (or a `.pdf`) on the docket to start a review. The row appears immediately and narrates what the system is doing:

| Stage | Meaning |
|---|---|
| reading | Turning the file into text |
| extracting | Splitting it into numbered clauses |
| inspecting | Four reviewers going through every clause |
| negotiating | Drafting replacement wording for what was flagged |
| summarising | Writing the executive summary |
| done | Ready for you |

A full review takes several minutes. That is the four reviewers taking turns on one machine, by design.

If a row says extraction failed, the document could not be read into at least three clauses. A scanned PDF with no text layer is the usual cause. The system refuses to inspect a document it could not read, rather than reviewing an empty page.

## 3. Reading a review

Opening a contract gives you the clause list on one side and the detail on the other.

For each clause you see the original wording, and where something was flagged:

| Part of a finding | What it tells you |
|---|---|
| The plain line | What the problem actually means, in everyday words |
| The term | The legal name for it |
| What is wrong | The specific defect |
| What to change | The fix being proposed |
| If ignored | The consequence of leaving it |
| The quote | The exact wording in the contract that caused it |
| Severity | High, medium or low, which feeds the contract's risk level |

Four reviewers produce these: one checks the firm's rules, one commercial risk, one deviation from your standard template, and one the money terms. A finding that arrives incomplete is thrown away before you see it, so everything on screen is actionable.

**Missing clauses are listed too.** A required clause that simply is not in the contract is treated as a finding in its own right.

## 4. Deciding

Every flagged clause needs your decision:

| Action | Effect |
|---|---|
| **Accept** | The proposed replacement wording becomes the final wording |
| **Reject** | The original wording stands |
| **Edit** | Your own wording becomes the final wording |

You cannot finish a review while any flagged clause is undecided. That is deliberate.

## 5. Finishing and exporting

Finishing locks the review and files it into the precedent cabinet, so a future contract with a similar term can retrieve what was decided here.

After finishing, download the corrected document. It is your original file with **only the changed clauses rewritten**, so formatting, numbering and everything you did not touch survive untouched. Two limits, both shown rather than hidden: export works on `.docx` only, and if a clause's original wording could not be located in the file, it is named for you to fix by hand.

## 6. The audit trail

Every step the system took is recorded in a chain where each entry is sealed against the one before it. Open the audit panel to read it. If any past entry were altered, the chain reports exactly where it broke.

## 7. For administrators

The people page creates accounts, changes roles between lawyer and administrator, resets an address or password, and deactivates an account. You cannot deactivate your own account.

## 8. Worth knowing

- **The first review after a quiet period is slower.** The model server sleeps and takes about a minute to wake.
- **Contracts never leave for an outside model provider.** There is one self-hosted model and no cloud path in the system at all.
- **Every finding carries its evidence.** If you cannot see why a finding was raised, the quote in it tells you which wording triggered it.
- **The system does not give legal advice.** It surfaces issues and drafts wording. Every decision is yours.
