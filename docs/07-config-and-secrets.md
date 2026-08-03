# 07. Configuration and Secrets

**Version 1, 2026-07-28.**

## 1. Rules

- Real values live only in a git-ignored `.env` at the repository root. The repository carries `.env.example` with blank placeholders.
- The lane URL and token are read when the model router is imported, so the API refuses to start without them.
- This system has **no cloud model key at all**, by design. If one appears in the configuration, something has gone wrong.

## 2. Variables

| Name | Required | Meaning |
|---|---|---|
| `DATABASE_URL` | yes | Postgres connection string, port 5433, user `legal`, database `contracts`. Use `127.0.0.1` rather than `localhost` to force IPv4 |
| `AUTH_SECRET` | yes | Signs the session cookie. The application refuses to start without it. Changing it signs everyone out |
| `PRIVATE_LANE_URL` | yes | HTTPS endpoint of the self-hosted model |
| `PRIVATE_LANE_TOKEN` | yes | Shared secret that endpoint requires |
| `BRAND_NAME`, `BRAND_TAGLINE` | no | Branding shown in the interface |
| `CORS_ORIGINS` | no | Comma-separated origins the browser may call the API from, exact origin and no trailing slash. Defaults to `http://localhost:3000` |
| `COOKIE_SECURE`, `COOKIE_SAMESITE` | no | Default to `false` and `lax`, which is what local development wants. Deployed, with the front end and the API on different domains, they must be `true` and `none` or the session cookie is silently dropped and login appears to do nothing |

The same lane endpoint and token are shared with the sibling governance system. Both projects point at one deployment, which is why a blank value in one repository is a common and confusing failure: the review dies before the GPU is ever reached, with a message about an invalid address.

## 3. Where secrets live

| Secret | Home |
|---|---|
| Lane token | The `.env` file on each machine, and a platform secret on the GPU service side |
| GPU platform credentials | The platform's own token file in the user profile, on the personal machine only |
| Database password | The `.env` file, and it must match the compose file |
| Session secret | The `.env` file |

## 4. Ports

| Service | Address |
|---|---|
| Web app | http://localhost:3000 |
| API | http://localhost:8000, interactive docs at `/docs` |
| Weaviate | http://localhost:8081, gRPC 50052 |
| Postgres | localhost:5433 |

These deliberately avoid the ticket-triage system's ports for the data stores, so both stacks can run at once. The application ports are shared, so only one backend and one web app run at a time.

## 5. Common configuration mistakes

| Symptom | Cause |
|---|---|
| The API will not start | A lane URL or token, or the session secret, is missing |
| A review fails immediately with an invalid address | The lane variables are present but blank |
| Database authentication failed | The connection string disagrees with the compose credentials |
| Precedent search returns errors, or seeding hangs | A local proxy is intercepting the vector database's gRPC port; exclude localhost |
| The vector collection does not exist | The precedent seed has never been run on this machine, or the volume was wiped |

## 6. Spend control

Every model call wakes a rented GPU, and the lane bills per warm window rather than per token. A hard spend cap is set on the platform. Measurement runs use a single-contract switch first as a cost fence, then the full corpus in one warm window.
