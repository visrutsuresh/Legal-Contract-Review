# 02. High-Level Design

**Version 1, 2026-07-28.**

## 1. The shape of the system

```
                    Lawyer / administrator
                              |
                              v
        +--------------------------------------------+
        |  Next.js web app (frontend/)                |
        |  docket  |  two-pane redline  |  people     |
        +--------------------------------------------+
                              | HTTP + cookie session
                              v
        +--------------------------------------------+
        |  FastAPI backend (api.py)                   |
        |  upload, poll, decide a clause, finish,     |
        |  audit, export                              |
        +--------------------------------------------+
              |               |                |
              v               v                v
     +----------------+  +-----------+  +----------------+
     | Agent pipeline |  | Postgres  |  | Weaviate       |
     | (LangGraph)    |  | contracts |  | precedent      |
     +----------------+  +-----------+  +----------------+
              |
              v
     +----------------------------------------+
     |  One model lane: self-hosted open-weight|
     |  model on a serverless GPU. No cloud.   |
     +----------------------------------------+
```

## 2. The pipeline

```
START -> intake -> extraction -+-> compliance -+
                               |-> risk        |
                               |-> template    +-> fan_in -> negotiation -> summary -> END
                               |-> financial   |
                               +-> (too few clauses) END
```

Nine nodes. The four inspectors run as one parallel step and write only to append-only keys, so their results cannot overwrite each other. Fan-in is plain code: it pins each finding to its clause, drops invalid ones, and rolls up the contract risk.

| Node | Model call | Responsibility |
|---|---|---|
| `intake` | no | File to plain text, plus the document's format |
| `extraction` | yes | Clause list with numbers, headings, wording and types, plus parties, contract type and dates |
| `compliance` | yes, with tools | Breaches of the firm's rules pack |
| `risk` | yes, with tools | Liability caps, one-way indemnities, intellectual-property grabs, auto-renewal, restraint |
| `template` | yes, with tools | Deviations from the standard, and required clauses that are missing |
| `financial` | yes, with tools | Payment days, fee increases, interest, penalties, totals that do not add up |
| `fan_in` | no | Attach findings to clauses, drop invalid ones, roll up risk |
| `negotiation` | yes | One replacement proposal per flagged clause, with ask, fallback and walk-away |
| `summary` | yes | Executive summary and counts |

## 3. Components

| Component | Where | Responsibility |
|---|---|---|
| Web app | `frontend/` | Docket with live stage narration, two-pane redline review, people administration |
| API | `api.py` | Upload, polling, clause decisions, finish, audit read, export |
| Pipeline | `app/graph.py` | The nine nodes and their guards |
| Agents | `app/agents.py`, `app/agents_base.py` | Prompts, the reasoning loop, finding validation |
| Tools | `app/tools.py` | Template fetch, rules read, precedent search |
| Model lane | `app/router.py` | One endpoint, one lock, one retry |
| System of record | `app/store.py` on Postgres | One row per contract, plus the uploaded bytes |
| Precedent cabinet | `app/precedent.py` on Weaviate | Finished reviews, retrieved by similarity |
| Export | `app/export.py` | Rewrites the original document in place |
| Audit | `app/audit.py` | Hash chain over every step |

## 4. Flow of one review

1. A lawyer uploads a file. The API stores the bytes, creates a row, and returns immediately.
2. The pipeline runs in the background. The docket row narrates the stage: reading, extracting, inspecting, negotiating, summarising, done.
3. The finished review shows every clause, its findings, and a proposed replacement where there is one.
4. The lawyer accepts, rejects or edits each flagged clause. The final wording is whichever they chose.
5. Finishing the review files it into the precedent cabinet, so a later contract can retrieve it.
6. The corrected document can be exported: the original file with only the changed clauses rewritten.

## 5. Technology choices

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python and FastAPI | Shared skeleton with the ticket-triage system |
| Agent wiring | LangGraph | Parallel fan-out with append-only merge keys is exactly the shape needed |
| Vector store | Weaviate | Precedent search by meaning, running locally |
| Relational store | Postgres | One row per contract, whole state as JSON, plus the original file bytes |
| Frontend | Next.js, TypeScript, Tailwind | Shared skeleton |
| Model | One self-hosted open-weight model on serverless GPU | Contracts are confidential; there is no cloud lane at all |

## 6. What is deliberately different from the ticket-triage system

- **One lane, not four.** No cloud model, no tier switch, no routing grid. Confidentiality is absolute here, so the routing question does not arise.
- **Parallel inspectors, not a chain.** Four opinions on the same clause list, merged by plain code.
- **Clause-level human control.** The human gate is per clause rather than per document.
- **The document itself is the deliverable**, so the original bytes are kept and rewritten on export.
