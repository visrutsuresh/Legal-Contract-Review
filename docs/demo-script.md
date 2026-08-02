# Demo script: the four beats

Audience takeaway: a contract goes in, every risky clause comes out flagged
against the playbook with a proposed redline, a lawyer rules on each one, and
the finished review becomes precedent the next review learns from.

## Pre-demo checklist (30 min before)

1. `docker compose up -d` (Postgres 5433 + Weaviate 8081), then seeds if the
   machine is fresh: `uv run python seed_users.py` and
   `uv run python seed_precedent.py`.
2. WARM THE MODAL LANE about ten minutes ahead (a cold first call takes about
   a minute; a full contract takes several minutes). Never demo on a cold lane.
3. Backend `uv run uvicorn api:app --reload` (:8000), frontend
   `cd frontend && npm run dev` (:3000). One sibling app at a time.
4. Sign in as priya@papyrus.dev. Have a FINISHED review already sitting in the
   docket (run one earlier the same day): it is beat 3's subject and the
   fallback if the live run misbehaves.
5. Pick the live-run contract: `data/contracts/msa_cobalt.docx` (or any of the
   five authored ones). Know what is planted in it so you can point at a catch.
6. The recorded backup of all four beats is loaded and ready to play (mandatory).

## Beat 1 - drop a contract on the docket (1 min)

Drag `msa_cobalt.docx` in. The row narrates the pipeline honestly: reading,
extracting, inspecting, negotiating, summarising. While it starts, one
sentence on privacy: the contract text goes to a private GPU lane we deploy
ourselves, not to a public API, because clients do not mail their contracts
to third parties.

## Beat 2 - the inspectors at work (3-5 min)

While it runs, narrate the crew, using the same words as the on-screen badges:
four specialist inspectors (compliance, risk, standard-terms, financial) read
every clause against the playbook,
a negotiator drafts the redline for each catch, and a summariser writes the
cover memo. Each inspector cites the playbook rule it fired and searches
precedent (past filed reviews) before judging. If one inspector fails, the
review continues without it and says so on screen: a partial answer that
admits it beats a confident silence.

## Beat 3 - the lawyer rules (3 min, on the pre-run review)

Open the finished review: the two-pane redline, original clause left,
proposed language right, each flag pinned to a named playbook rule with a
severity. Accept one, reject one with a reason, edit one. The point: the
system proposes, the lawyer disposes, and every ruling is recorded. Then show
the measured honesty: on the 13-contract benchmark it caught 87.5% of the
planted issues (the benchmark JSON ships in the repo, re-runnable).

## Beat 4 - finish, file, and the flywheel (2 min)

Finish the review. It locks (no quiet edits after sign-off), lands in the
audit trail (`GET /contracts/{id}/audit`, hash-chained), and is filed as
precedent, so the NEXT review of a similar clause retrieves this lawyer's
ruling as context. Download the corrected document. One closing sentence:
the firm's judgement compounds; the tool gets more like the firm every
review it finishes.

## If the lane misbehaves

Beats 1-2 are the Modal-dependent ones. Fall back to the recording for them
and run beats 3-4 live on the pre-run review (both are $0 and local).
