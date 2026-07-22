# Papyrus — Legal Contract Review

A multi-agent AI system that reads a contract, splits it into clauses, inspects every clause four
ways, drafts replacement wording for what it flags, and hands the whole thing to a lawyer to accept,
reject, or edit clause by clause. Nothing is signed off without a human.

Use case #4 of the Ascendion internship build, forked from the #1 [REDACTED_SQL_PASSWORD_1]-ticket skeleton.

**Contracts never touch a cloud model.** There is exactly one model lane, a self-hosted
Qwen3-30B-A3B on a Modal GPU. That is the whole privacy story, and it is why there is no
`ANTHROPIC_API_KEY` or model-tier switch here the way there is in #1.

---

## What's in the box

| Piece | Tech | What it does |
|---|---|---|
| Agent pipeline | LangGraph (`app/graph.py`) | intake → extraction → 4 inspectors in parallel → fan-in → negotiation → summary |
| Backend API | FastAPI (`api.py`) | upload a contract, poll the docket, decide a clause, finish a review, read the audit trail |
| System of record | Postgres (`app/store.py`) | one row per contract: status/stage/risk columns + the full state blob |
| Precedent cabinet | Weaviate (`app/precedent.py`) | finished reviews, retrieved by similarity so later contracts can cite earlier rulings |
| Model lane | Modal GPU (`app/router.py`) | Qwen3-30B-A3B, 4-bit. One lane, no cloud fallback, by design |
| Lawyer UI | Next.js (`frontend/`) | the docket, the two-pane redline review, the people admin |
| Audit trail | `app/audit.py` | SHA-256 hash chain over every pipeline step, verified on read |

### The four inspectors

They run in a single parallel LangGraph superstep, each writing only to reducer keys:

| Inspector | Looks for | Tools |
|---|---|---|
| `compliance` | breaches of the firm's rules pack (`policy_rules.md`) | `rules_read`, `precedent_search` |
| `risk` | liability caps, one-way indemnities, IP grabs, auto-renewal, restraint | `precedent_search`, `template_fetch` |
| `template` | deviations from our standard, and required clauses that are missing | `template_fetch` |
| `financial` | payment days, fee increases, interest, penalties, totals that don't add up | `template_fetch` |

A finding is thrown away unseen unless it carries all of `clause_id`, `inspector`, `severity`,
`plain`, `term`, `wrong`, `change`, `ignore`, `evidence`. Half-formed findings are never shown to a
lawyer.

---

## Prerequisites

- **Docker Desktop** — runs Postgres + Weaviate. Must be up before the backend.
- **uv** — Python package manager. https://docs.astral.sh/uv/
- **Node.js 18+** and npm.
- **A `.env`** in the repo root (gitignored, never committed).

> The model runs on Modal as a web endpoint, deployed separately from `modal_lane/llm_service.py`.
> You only need its URL + token in `.env`; you do not install Modal to run the app.

### `.env` (copy from `.env.example`)

```
DATABASE_URL=postgresql://legal:<password>@127.0.0.1:5433/contracts
AUTH_SECRET=...             # signs the login cookie; the app refuses to start without it
PRIVATE_LANE_URL=...        # the Modal Qwen3 endpoint (REQUIRED, read at import time)
PRIVATE_LANE_TOKEN=...      # shared secret for that endpoint (REQUIRED)
BRAND_NAME=Papyrus          # optional, shown in the UI header
BRAND_TAGLINE=              # optional
```

`DATABASE_URL` and the two lane variables are read the moment `app/store.py` / `app/router.py` are
imported, so a missing one is a startup crash, not a runtime surprise. Use `127.0.0.1`, not
`localhost`, to force IPv4. Note the port is **5433** — #1 owns 5432, and both stacks are meant to
run side by side.

---

## First-time setup

```bash
uv sync                                  # backend deps from pyproject.toml / uv.lock
docker compose up -d                     # Postgres 5433 + Weaviate 8081
uv run python seed_users.py              # one admin + two lawyers (idempotent)
uv run python seed_precedent.py          # 8 starter precedents (idempotent)
cd frontend && npm install && cd ..
```

Seeded dev accounts (rotate before this is reachable by anyone else):

| Email | Password | Role |
|---|---|---|
| `[REDACTED_EMAIL_ADDRESS_2]` | `admin-dev-password` | admin |
| `[REDACTED_EMAIL_ADDRESS_3]` | `lawyer-dev-password` | lawyer |
| `[REDACTED_EMAIL_ADDRESS_4]` | `lawyer-dev-password` | lawyer |

There is **no open signup**. The admin creates every account from the People page.

---

## Run it (two terminals)

**Terminal 1 — backend**
```bash
export NO_PROXY=127.0.0.1,localhost no_grpc_proxy=127.0.0.1,localhost   # see the proxy note below
uv run uvicorn api:app --reload          # http://localhost:8000
```

**Terminal 2 — frontend**
```bash
cd frontend
npm run dev                              # http://localhost:3000
```

Open http://localhost:3000, sign in, and drop a `.docx` or `.pdf` on the docket. The row narrates
its stage while the pipeline runs (the docket polls every 4s), then flips to "Needs your review".
Sample contracts to try live in `data/contracts/`.

### Behind a TLS-intercepting proxy (mitmproxy / corporate CA)

If your machine sets `HTTPS_PROXY`, it hijacks the localhost Weaviate gRPC calls on port 50052 and
times them out, so precedent search and `seed_precedent.py` fail with
`WeaviateGRPCUnavailableError`. Keep the proxy for external calls, exclude localhost:

PowerShell:
```powershell
$env:NO_PROXY="127.0.0.1,localhost"; $env:no_grpc_proxy="127.0.0.1,localhost"
```
bash:
```bash
export NO_PROXY=127.0.0.1,localhost no_grpc_proxy=127.0.0.1,localhost
```

Set it before the backend **and** before `seed_precedent.py`.

---

## Tests

```bash
uv run pytest tests -q
```

80 tests, none of which call the model. They cover the deterministic seams: the hash chain, intake,
finding validation, the fan-in pinning logic, the ReAct loop's duplicate-call blocking, and the
`decide_clause` SQL against real Postgres. The store test skips itself if Postgres is unreachable.

---

## Bench

`bench.py` scores the pipeline against the labelled defects in `data/manifests/`. Each manifest lists
what was deliberately planted in its contract — clause number, severity, and which inspector should
catch it — so the harness can report detection recall, inspector attribution, severity agreement,
unplanted findings, extraction health, and latency.

```bash
uv run python bench.py                   # all 13 contracts — real GPU time, ~30+ min
uv run python bench.py --only kestrel    # one contract, substring match on the manifest name
```

Results land in `bench_papyrus.json`. Start with `--only`; the full run is not cheap.

> The precedent seed is deliberately **not** built from these thirteen contracts. If it were, an
> inspector could retrieve a planted defect through `precedent_search` instead of finding it, and
> recall would measure nothing. The seeded entries cover the same classes of term with different
> counterparties.

---

## Ports and URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| Weaviate | http://localhost:8081 (gRPC 50052) |
| Postgres | localhost:5433 (user `legal`, db `contracts`) |

---

## Common gotchas

- **Weaviate gRPC times out, precedent search returns nothing.** An `HTTPS_PROXY` is routing
  localhost gRPC through the proxy. See the proxy section above.
- **`precedent_search` returns an empty list on a fresh machine.** The cabinet only fills when a
  lawyer finishes a review. Run `uv run python seed_precedent.py`.
- **A contract lands on "Needs a person" / `extraction_failed`.** Either the file had no readable
  text (a scan — intake needs a real text layer, there is no OCR), or fewer than 3 clauses could be
  identified, which is treated as too few to review safely.
- **Upload returns instantly but the row says "Working" for minutes.** Expected. The upload parks a
  row and returns; the pipeline runs in a background task. Per-node cap is 240s with one retry, and
  the whole run is abandoned at 20 minutes.
- **A review ends at `error` with "The review run crashed or timed out".** Deliberate: a dead run
  must say it died rather than strand at "processing". Check the backend log and re-upload.
- **App won't start, `KeyError: 'DATABASE_URL'` or `'PRIVATE_LANE_URL'`.** A required `.env` var is
  missing; they are read at import time.
- **`RuntimeError: AUTH_SECRET missing from .env`.** Exactly what it says.
- **Port 5432 vs 5433.** This stack is on **5433** so it can run alongside #1. A `DATABASE_URL`
  pointing at 5432 will silently talk to the wrong project's database.

---

## Repo layout

```
api.py                FastAPI backend (upload, docket, decisions, finish, audit, users)
bench.py              scores the pipeline against data/manifests/
seed_users.py         one admin + two lawyers
seed_precedent.py     starter precedent cabinet
make_contracts.py     generates the synthetic contract corpus + manifests
policy_rules.md       the firm's rules pack, read by the compliance inspector
docker-compose.yml    Postgres 5433 + Weaviate 8081/50052
app/
  graph.py            the LangGraph pipeline: 9 nodes, one parallel fan-out, the per-node guard
  state.py            ContractState + the Clause / Finding / Proposal shapes
  agents.py           extraction, the four inspectors, negotiation, summary
  agents_base.py      the shared ReAct loop (blocks repeat tool calls, forces a finish)
  tools.py            the tool registry: template_fetch, rules_read, precedent_search
  intake.py           .docx / .pdf → normalised plain text (plain code, no model)
  router.py           the single Modal model lane
  precedent.py        Weaviate precedent cabinet + embeddings
  store.py            Postgres system of record
  audit.py            hash-chain tamper-evident audit trail
  users.py            fastapi-users auth, lawyer | admin roles
  schemas.py          the user read/create/update schemas
modal_lane/
  llm_service.py      the Qwen3-30B-A3B service deployed to Modal
data/
  contracts/          13 synthetic contracts (.docx / .pdf)
  manifests/          what was planted in each, the bench ground truth
  templates/          the firm's standard clause sets per contract type
tests/                pytest suite (no model calls)
frontend/             Next.js lawyer UI (App Router, Tailwind, TypeScript)
```
