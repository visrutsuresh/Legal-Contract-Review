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

## Walkthrough

`04-contract-review-walkthrough.mp4` (4:06) was spliced from the six all-PASS
clips in order a → f after the 04e retake. Nothing was seeded or faked: both
contracts ran the live pipeline on the private GPU lane, and every ruling shown
was clicked during the take.
