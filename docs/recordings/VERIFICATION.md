# Recording verification log

Every clip passed a frame-level gate before it entered the walkthrough: one frame
extracted per narration beat (`demo-media-kit/cap/check_frames.py` in the
ascendion-internship repo), each frame read and compared against the narration
line, the on-screen state, and the database. A clip ships only if every beat
passes. Any failure means a fresh contract upload and a full retake, never a
patched database row (decisions are part of the hash chain; editing them in
place would break "Verified intact").

Cross-checks run against the live DB for the recorded contract `P-7bd158f5`
(msa_novabright.docx): clause decisions recorded = `accepted` (Fees and
Payment), `rejected` = keep-their-wording (Term and Termination), `edited` =
use-my-wording (Limitation of Liability), `accepted` after counsel (Data
Protection). The clips show exactly these four rulings, in this order.

## 04a-upload-and-read — PASS

| Narration beat | Frame shows | Verdict |
|---|---|---|
| "This is Papyrus, a legal contract review desk..." | Papyrus sign-in card, "No signup here: the admin creates every account." | PASS |
| "A fresh desk: the docket is empty." | The Docket, "Nothing here yet. Upload a contract to start." No leftover contracts. | PASS |
| "It goes in exactly as it arrived..." | msa_novabright.docx row, WORKING, "Reading the document…" | PASS |
| "Papyrus starts reading immediately, and the review narrates itself." | Progress page "STEP 2 OF 6", "Finding the clauses…", skeleton panes. | PASS |
| "Six stages: read, split, four inspectors in parallel, negotiation angles, report." | Six-segment progress bar ("STEP 2 OF 6"). Narration matches the bar's six stages, not the nine internal graph nodes. | PASS |
| "Several minutes of real reading, shown at ten times speed." | "STEP 5 OF 6", "Writing the plain-English report…" (10x section). | PASS |
| "The verdict: ... clean ones as looks standard, flagged ones your call." | Verdict screen: HIGH RISK 100/100, "0 OF 4 DECIDED", clean clauses read "looks standard, no change proposed", flagged clauses carry "YOUR CALL". | PASS |

## 04b-accept-and-keep — PASS

| Narration beat | Frame shows | Verdict |
|---|---|---|
| "The reviewed contract. On the left rail, the risk picture..." | Risk rail (10 serious / 3 medium / 1 minor, per-check bars), Their version / Your redline panes, "0 OF 4 DECIDED". | PASS |
| "The first flagged clause, expanded... what is wrong, what we would change it to, what happens if you ignore it." | Fees and Payment expanded: WHAT IS WRONG / WHAT WE WOULD CHANGE IT TO / IF YOU IGNORE IT cards. | PASS |
| "The lawyer agrees: accept fix..." | Redline diff (~~one hundred and twenty (120) days~~ → thirty (30) days) + "In your redline. The corrected wording replaces theirs in the final document." | PASS (DB: `accepted`) |
| "Next flag. This time the lawyer disagrees." | Term and Termination expanded (auto-renew / 180-day notice findings). | PASS |
| "Keep their wording. Papyrus records that a person saw the flag and chose to keep it." | "Their original wording stays. Papyrus records that you saw the flag and chose to keep it." | PASS (DB: `rejected`) |

## 04c-edit-and-counsel — PASS

| Narration beat | Frame shows | Verdict |
|---|---|---|
| "Two decisions are on the record." | Header reads "2 OF 4 DECIDED". | PASS |
| "On this flag, the lawyer likes neither wording." | Limitation of Liability expanded, unlimited-liability findings. | PASS |
| "Edit opens the proposed text for rewriting." | Textarea open over the proposal, "Use my wording" button. | PASS |
| "The lawyer writes the wording they actually want, sped up here." | Typed custom clause ending "...written agreement of both parties." | PASS |
| "Use my wording. A third kind of ruling." | "Your wording goes into the final document: …" confirmation with the typed text. | PASS (DB: `edited`) |
| "And a hard one, where the lawyer wants a second opinion." | Data Protection clause, YOUR CALL, Ask counsel visible. | PASS |
| "Ask counsel wakes a fifth agent..." | Open card with Accept fix / Keep their wording / Edit / Ask counsel. | PASS |
| "A minute or two of extra reading, sped up ten times, and the ruling lands right on the open clause." | "Ask recorded: Require the Provider to notify the Client of any personal data breach within seventy-two (72) hours of becoming aware of it." rendered in place on the open card (no re-click of the header). | PASS |
| "Counsel's ruling... the concrete concession to demand." | Same "Ask recorded" concession text on the clause record. | PASS |
| "With that in hand, the lawyer accepts the fix. Four flags, four different human rulings." | Accept confirmation "In your redline. The corrected wording replaces theirs in the final document." | PASS (DB: `accepted`) |

Note: this run of the counsel agent recorded a concession-ask rather than an
escalation; the narration says exactly that and the frame shows it.

## 04d-signoff-and-export — PASS

| Narration beat | Frame shows | Verdict |
|---|---|---|
| "Under every review sits the audit trail." | "4 OF 4 DECIDED", Finish review active. | PASS |
| "Every pipeline step... hash-chained in order." | Audit trail expanded: **"Verified intact · 20 steps, each one hash-linked to the one before it."** Clause 10 marked DECIDED / ACCEPTED. | PASS (required check) |
| "Finish review. The contract flips to reviewed." | "Review complete... filed as precedent" banner, FINAL REDLINED DOCUMENT with clause 3 at thirty (30) days. | PASS |
| "The final redlined document, assembled from the four rulings." | Full document: accepted fix (clause 3), kept wording (clause 4 unchanged), lawyer's own wording (clause 7), 72-hour breach notice (clause 10). | PASS |
| "Download corrected docx..." | "Download corrected .docx" + "Review report" buttons. | PASS |
| "And the review report: the whole engagement on one printable page." | :8000 report page: contract ID P-7bd158f5, HIGH RISK 100/100, "Clause-level findings (4 flagged of 14 clauses)", Print / Save as PDF. | PASS |

## 04e-people — RETAKE, then PASS

**Take 1 (2026-08-06 ~05:45): FAIL.** The roster frame showed the dev accounts
`testadmin`, `testlawyer` and `mixedcase` (other4@papyrus.dev) as deactivated
cards while the narration claimed "Every account here is one the firm chose to
make." Deactivated is not deleted; the roster was not production-grade.

**Fix:** deleted the three dev accounts AND `lena@papyrus.dev` (residue of the
failed take, which would otherwise pre-exist her own on-camera creation) from
the user table, then re-recorded the whole clip. No video was patched.

**Take 2: PASS.**

| Narration beat | Frame shows | Verdict |
|---|---|---|
| "Who gets to sit at this desk is managed, not open." | People page with exactly admin / priya / theo, all active. No dev accounts, no leftover lena. | PASS |
| "A new lawyer joins the team: email, password, role." | New account modal: lena@papyrus.dev, masked password, role lawyer. | PASS |
| "Created, and on the roster next to everyone else." | "Lawyer account created for lena@papyrus.dev.", lena's card active on the roster. | PASS |

## 04f-docket-close — PASS

| Narration beat | Frame shows | Verdict |
|---|---|---|
| "Back on the docket, the desk keeps moving." | Docket with msa_novabright.docx SIGNED OFF · "4 flagged clauses decided" · High risk. | PASS |
| "The next contract goes in, an NDA this time..." | nda_kestrel.docx row, WORKING, "Finding the clauses…". Live pipeline run (contract P-4a498106 in DB). | PASS |
| "The closing shot is the docket holding the whole lifecycle side by side." | One contract SIGNED OFF, one WORKING. Exactly two rows. | PASS |
| "That is Papyrus..." | Same closing docket, steady. | PASS |

## Chapter splice (superseded as the main walkthrough)

The first walkthrough (4:06) was spliced from the six all-PASS clips in order
a → f after the 04e retake. It was superseded the same day by the single-take
recording below; the chapter clips themselves remain in `clips/`.

## Single-take walkthrough — one RETAKE, then PASS

CEO direction: the whole flow in one continuous recording, login only twice
(lawyer, then admin), one contract only, a slow top-to-bottom pan of the whole
processed contract, and long dwells on each finding beside its redline.
Recorded via `clip-04-full.json` against a fresh empty docket each take.

**Take 1 (rehearsal timing): superseded.** Completed cleanly but used the
pre-feedback pacing; re-cut with slower pan and longer redline dwells.

**Take 2: FAIL, caught by the frame gate + DB cross-check.** On this live run
the counsel agent's concession-ask REMOVED the Accept fix button from the open
clause card (on the chapter take it had stayed). The scripted accept therefore
never registered: DB showed clause 10 undecided, the contract stuck at
needs_review, the audit chain ended at 13 steps with no finish entry, and the
frame at "Finish review" showed the guard banner "Decide every flagged clause
first." while the narration claimed the review closed. Full retake, fresh
upload; no database row was touched (patching a decision would fork the hash
chain).

**Hardening added before take 3:** the post-counsel ruling became "Keep their
wording" (present in every UI variant) with matching narration, and two
outcome guards now abort a bad take instead of shipping it: `assertText "4 OF
4 DECIDED"` after the final ruling and `assertText "Review complete"` after
Finish review.

**Take 3 (the shipped video): PASS on all 38 beats.** Contract `P-61aff302`,
verified against the DB: decisions `accepted` (clause 3), `rejected`/kept
(clause 4), `edited` (clause 7), `rejected`/kept-with-counsel's-ask (clause
10); table status `reviewed`; audit chain "Verified intact · 14 steps" on
camera before finish, ending "review finished: 14 clauses signed off". Key
frames read against narration:

| Beat | Frame shows | Verdict |
|---|---|---|
| Opening / sign-in | Papyrus login card, then priya's empty docket ("Nothing here yet"). | PASS |
| Upload + six stages | msa_novabright.docx WORKING; progress page steps of 6. | PASS |
| Verdict | HIGH RISK 100/100, "0 OF 4 DECIDED", missing-clauses card first in the redline pane. | PASS |
| Slow pan (5 beats) | Continuous top-to-bottom pass: their version beside the redline, clean clauses "looks standard", flagged clauses YOUR CALL, down to clause 14. | PASS |
| Ruling 1: accept | Trio card + strikethrough diff (120 days → thirty (30) days), "In your redline" confirmation. | PASS |
| Ruling 2: keep | Term and Termination diff dwelt on, then "Their original wording stays…" | PASS |
| Ruling 3: own wording | Edit textarea, typed clause, "Your wording goes into the final document". | PASS |
| Ruling 4: counsel | "Ask recorded: …seventy-two (72) hours…" lands on the open card (no re-click), then keep confirmation; header hits 4 OF 4 DECIDED (asserted). | PASS |
| Audit + finish | "Verified intact · 14 steps, each one hash-linked", all four decisions and the concession in the chain; "Review complete… filed as precedent" (asserted). | PASS |
| Final document | Clause 3 net-30 applied, clause 4 kept, clause 7 lawyer's wording, clause 10 kept. | PASS |
| Export + report | Download corrected .docx; report page for P-61aff302, "4 flagged of 14 clauses". | PASS |
| Account switch | Sign out lands the login card ON CAMERA; admin signs in — the film's only account switch. | PASS |
| People | Clean roster (admin, priya, theo), lena created, "Lawyer account created for lena@papyrus.dev". | PASS |

Nothing was seeded or faked: the contract ran the live pipeline on the private
GPU lane, counsel is a real agent call, and every ruling shown was clicked
during the take.
