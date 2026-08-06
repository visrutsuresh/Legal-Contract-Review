# Demo recordings

Screen recordings of the live app on localhost, driven end to end: the contracts
were really uploaded, every review is a real pipeline run on the private GPU
lane (Modal), and every lawyer decision shown was actually clicked. Pipeline
reading and long typing are fast-forwarded 10x; the transcripts mark those
moments.

- `04-contract-review-walkthrough.mp4` — the full walkthrough (4:06), spliced
  from the clips below in order, with
  `04-contract-review-walkthrough-transcript.md` for narration and timestamps.
- `clips/` — the individual chapters, each with its own transcript:
  - `04a-upload-and-read` — the MSA goes in as a Word file; the six-stage
    pipeline reads it (extract, clauses, four parallel inspectors, negotiation
    angles, report) and lands the verdict screen.
  - `04b-accept-and-keep` — first flagged clause accepted, second kept as-is;
    both rulings recorded under the lawyer's name.
  - `04c-edit-and-counsel` — the lawyer rewrites one clause in their own words,
    then wakes the senior-counsel agent on a hard one and rules with its ask in
    hand.
  - `04d-signoff-and-export` — the hash-chained audit trail verified intact,
    Finish review, the corrected .docx export, and the printable review report.
  - `04e-people` — no open signup: the admin creates a lawyer account.
  - `04f-docket-close` — the NDA goes in; the docket holds the full lifecycle
    side by side (one signed off, one mid-read).

Rebuild: `demo-media-kit/cap/` in the ascendion-internship repo (recorder
scripts `clip-04*.json`, `record2.js`, `edit.py`, `combine.py`).

Every clip passed a frame-by-frame check against its narration before the
walkthrough was stitched; the full beat-by-beat log, including the one retake
it forced, is in `VERIFICATION.md`.
