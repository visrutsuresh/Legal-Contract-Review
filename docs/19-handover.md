# 19. Handover

**Version 1, 2026-07-28.**

## 1. Get it running

Repository `README.md` for installation, [08-runbook.md](08-runbook.md) for daily operation. You need Docker, `uv`, Node, and an environment file. The model endpoint and its token are the only values you cannot invent locally; without them the API refuses to start.

Order: containers up, seed the accounts, seed the precedent cabinet, start the API, start the web app, sign in.

## 2. Read these first

1. [02-hld.md](02-hld.md), the pipeline diagram.
2. [03-lld.md](03-lld.md) sections 2 to 4: the three shapes, the reasoning loop, and the guards.
3. [06-adr-log.md](06-adr-log.md), especially the single-lane and single-container decisions, which are where the money and the privacy claim live.

## 3. The five things that will surprise you

1. **Every model call costs money.** The lane wakes a rented GPU and bills a warm window. Never loop the benchmark contract by contract; use the one-contract switch, then the full corpus in one window.
2. **The four inspectors do not really run in parallel.** They fan out in the graph, then queue on one GPU container, because letting the platform start a second one doubled the bill and broke runs mid-way. Seven minutes a contract is that decision, not a performance defect.
3. **The fake model in the tests recognises agents by the opening phrase of their prompts.** Rewording an inspector's opening role line will break tests in a way that looks unrelated.
4. **A finding missing any of its nine fields is discarded silently and counted.** If findings vanish, look at validation before looking at the model.
5. **Two failure fingerprints are worth memorising.** A parse failure at the identical character on both attempts is truncation, not randomness. An immediate invalid-address error means the lane variables are blank, and it costs nothing.

## 4. Where the important logic lives

| Question | File |
|---|---|
| What counts as a valid finding | `valid_finding()` in `app/state.py` |
| How findings attach to clauses and risk is rolled up | `fan_in()` in `app/graph.py` |
| How an inspector thinks and uses tools | `app/agents_base.py` |
| What each inspector looks for | The four prompts in `app/agents.py` |
| How the model is called, and why it locks | `app/router.py` |
| How the corrected document is produced | `app/export.py` |
| What a lawyer's decision does to the final wording | The decision endpoint in `api.py` |

## 5. Open work, in the order worth doing

1. **A test asserting contract text can never reach a third party.** The claim is currently proved by the absence of a cloud client, which is strong but is not a test, and it is the system's headline privacy promise.
2. **Severity agreement**, the weakest measured dimension, and the one that drives the risk roll-up.
3. **Update the README's model line**, which still names the earlier, larger model.
4. **A matter or client boundary** on both contracts and precedent retrieval, which is the first real-world blocker.
5. **Retention and deletion**, including removal from the precedent cabinet.
6. **Extract the shared core** with the sibling systems, per the decision recorded in the planning repository, deliberately scheduled after the current deadline.

## 6. Operational cautions

- `docker compose down -v` destroys the precedent cabinet and every contract. Re-seed afterwards.
- Changing the session secret signs everyone out.
- The database password in the environment file must match the compose file; Postgres only applies credentials when it first initialises an empty volume.
- After any multi-part hand-paste, compile the package before running anything. Three separate incidents in this repository came from pasted code, and each would have been caught in two seconds.

## 7. Related repositories

This system was forked from the ticket-triage system and is the parent of the AI-governance system. Several modules are near-identical across all three; the duplication is measured and the shared-package plan is recorded in the planning repository. A fix in a shared-looking module here is worth checking in both siblings, because that has already been necessary twice.
