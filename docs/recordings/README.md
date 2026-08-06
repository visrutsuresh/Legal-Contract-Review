# Demo recordings

Screen recordings of the live app on localhost, driven end to end: the contracts
were really uploaded, every review is a real pipeline run on the private GPU
lane (Modal), and every lawyer decision shown was actually clicked. Pipeline
reading and long typing are fast-forwarded 10x; the transcripts mark those
moments.

- `04-contract-review-walkthrough.mp4` (3:40) — the whole engagement in ONE
  CONTINUOUS TAKE: one contract, one lawyer session, no cutting between logins.
  The MSA goes in as a Word file, the six-stage read runs live (10x), the full
  document is panned top to bottom in one slow scroll, then the four flagged
  clauses are ruled on with the finding and its redline dwelt on side by side
  (accept fix, keep their wording, the lawyer's own wording, and an ask-counsel
  ruling), the hash-chained audit trail is verified intact, the review is
  finished, the corrected .docx and the printable report are opened, and the
  only account switch in the film happens on camera: the lawyer signs out, the
  administrator signs in and creates a lawyer account on the managed roster.
  `04-contract-review-walkthrough-transcript.md` carries the narration with
  timestamps.
- `clips/` — the same journey as six standalone chapters (recorded separately,
  each with its own transcript), kept for slide embeds and per-feature demos:
  `04a-upload-and-read`, `04b-accept-and-keep`, `04c-edit-and-counsel`,
  `04d-signoff-and-export`, `04e-people`, `04f-docket-close`.

Every recording passed a frame-by-frame check against its narration before
shipping; the beat-by-beat log, including the retakes it forced, is in
`VERIFICATION.md`.

Rebuild: `demo-media-kit/cap/` in the ascendion-internship repo (recorder
scripts `clip-04-full.json` / `clip-04*.json`, `record2.js`, `edit.py`,
`combine.py`).
