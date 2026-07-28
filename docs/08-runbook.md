# 08. Runbook

**Version 1, 2026-07-28.** First-time installation is in the repository `README.md`; this is for running, recovering and diagnosing.

## 1. Daily start

```bash
docker compose up -d                    # Postgres 5433 + Weaviate 8081
uv run uvicorn api:app --reload         # API on :8000
cd frontend && npm run dev              # web app on :3000
```

Behind a TLS-intercepting proxy, set the exclusions **in the same shell** as the backend and as any seed script, or the vector database calls hang and then fail:

```bash
export NO_PROXY=127.0.0.1,localhost no_grpc_proxy=127.0.0.1,localhost
```

## 2. Seeding

| Command | Effect |
|---|---|
| `uv run python seed_users.py` | Creates the administrator and lawyer accounts |
| `uv run python seed_precedent.py` | Fills the precedent cabinet with eight fictional prior reviews. Idempotent and tagged, so re-running never destroys a real filed review |

Both are needed on a fresh machine, and again after any `docker compose down -v`.

## 3. Health checks

| Check | How | Healthy answer |
|---|---|---|
| API alive | `GET http://localhost:8000/` | Status ok |
| Sign-in | The login page with a seeded account | Reaches the docket |
| Model lane warm | A short probe prompt | A short answer in about a minute from cold |
| Precedent cabinet | Upload and finish any contract, then search | Results, not an error observation |

## 4. Running a review

1. Sign in and drop a `.docx` on the docket.
2. Watch the row narrate: reading, extracting, inspecting, negotiating, summarising, done.
3. Open the review, work down the flagged clauses, and accept, reject or edit each one.
4. Finish the review. It locks and is filed as precedent.
5. Download the corrected document if you need it.

Expect a full review to take several minutes: the four inspectors queue on a single GPU by design.

## 5. Incidents

### The review stops at extraction

Fewer than three clauses were extracted, so the pipeline refused to inspect a document it could not read. Check the file: a scanned PDF has no extractable text. Re-upload as `.docx` if you have one.

### One inspector reports failed, the others are fine

Expected behaviour rather than a crash: the review continues with the remaining inspectors and the failure is visible in the report. If it repeats at the identical character on both attempts, that is the fingerprint of truncated model output rather than randomness.

### Every model call fails with an invalid address

The lane variables are blank in the environment file. This costs nothing because the run dies before the GPU is reached, but it looks alarming.

### The whole review hangs, then times out

The lane is cold, or a container swap happened mid-run. The guard gives each node a bounded wall clock and one retry. Warm the lane and try again rather than retrying cold repeatedly, because each cold wake costs money.

### Precedent search returns an error observation to the agents

The vector collection does not exist on this machine, or the proxy is intercepting its port. Run the precedent seed, with the localhost exclusions set.

### Finishing a review fails

Either a flagged clause has no decision yet, or the review is already finished. Both are deliberate conflicts, not bugs.

## 6. Before a demo

1. Warm the model lane about ten minutes ahead. A cold first call takes roughly a minute; a full contract takes several minutes.
2. Have a finished review already in the docket as a fallback, so the walkthrough does not depend on a live run.
3. Follow `demo-script.md` in this folder.

## 7. Cost discipline

Every wake of the GPU lane costs real money and the free credit is finite. Never run the benchmark contract by contract; use the single-contract switch as a cost fence, then run the whole corpus in one warm window.
