# 05. API Specification

**Version 1, 2026-07-28.** Base URL `http://localhost:8000`. The framework serves a live version at `/docs`; this is the reviewed narrative version.

## 1. Authentication and roles

Sessions are a signed cookie. Two roles: `lawyer` and `admin`. **There is no open signup**; an administrator creates every account. Every endpoint below except health, configuration and the two first-run setup routes requires a signed-in account.

The one exception to "an administrator creates every account" is the **first-run bootstrap**. A freshly installed system has no accounts, therefore no administrator, therefore no way to create the first one. `GET /auth/needs-setup` reports that state and `POST /auth/bootstrap` closes it by creating the founding administrator. The bootstrap route refuses with 403 the moment any account exists, so the door opens once and never again.

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/auth/login` | anyone | Form credentials (email address), returns a session cookie |
| POST | `/auth/login-flex` | anyone | Same, but the identifier may be **either** the email address or the username, matched case-blind. This is what the sign-in screen posts to |
| GET | `/auth/needs-setup` | anyone | `{"needs_setup": true}` only while the system holds zero accounts |
| POST | `/auth/bootstrap` | anyone, once | Creates the founding administrator from email, username and password. 403 once any account exists, 409 on a duplicate address |
| POST | `/auth/logout` | signed in | Ends the session |
| GET | `/users/me` | signed in | The current account and its role |

## 2. Public

| Method | Path | Returns |
|---|---|---|
| GET | `/` | Health |
| GET | `/config` | Brand name and tagline |

## 3. Contracts

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/contracts` | lawyer or admin | Multipart upload of a `.docx` or `.pdf`. Returns immediately with an id while the pipeline runs in the background. 400 on an empty file |
| GET | `/contracts` | lawyer or admin | The docket: id, filename, status, stage, risk level, created time |
| GET | `/contracts/{id}` | lawyer or admin | The full review: clauses, findings, proposals, decisions, summary. 404 if unknown |
| GET | `/contracts/{id}/audit` | lawyer or admin | The hash chain with a verification result. 404 if unknown |
| GET | `/contracts/{id}/report` | lawyer or admin | The printable review report |

The docket is polled while a review runs; the `stage` field is what the row narrates.

## 4. Clause decisions

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/contracts/{id}/clauses/{clause_id}/decision` | `{verdict, edited_text?}` | `verdict` is `accepted`, `rejected` or `edited` |

Status codes, all of them deliberate:

| Code | When |
|---|---|
| 422 | The verdict is not one of the three |
| 422 | `edited` was sent with no replacement wording |
| 422 | `accepted` was sent for a clause that has no proposal to accept |
| 404 | Unknown contract, or unknown clause |
| 409 | The review is already finished |

The final wording is set from the verdict: accepting takes the proposal, rejecting keeps the original, editing takes the lawyer's text.

## 5. Finishing a review

| Method | Path | Notes |
|---|---|---|
| POST | `/contracts/{id}/finish` | Locks the review and files it into the precedent cabinet |

| Code | When |
|---|---|
| 404 | Unknown contract |
| 409 | Already finished |
| 409 | The review is not ready to finish |
| 409 | Some flagged clause has no decision yet |

A precedent-store outage must never block a lawyer signing off; that is covered by a test.

## 6. Export

| Method | Path | Returns |
|---|---|---|
| GET | `/contracts/{id}/export` | The original document with only the changed clauses rewritten |

| Code | When |
|---|---|
| 409 | The review is not finished yet |
| 422 | The upload was a PDF; export is `.docx` only |
| 410 | The contract was uploaded before the original bytes were kept: upload it again |

Clauses whose original wording could not be located in the document are named in a response header, and the interface shows a fix-by-hand note. The limitation is surfaced rather than silent.

## 7. User administration

| Method | Path | Who | Notes |
|---|---|---|---|
The People screen is the administrator's landing page after sign-in and is the only place accounts are made. An administrator can create administrators as well as lawyers.

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/users` | admin | All accounts |
| POST | `/users` | admin | Create an account from email, username, password and role. 422 if the role is not lawyer or admin, 409 if either the address **or the username** already exists |
| PATCH | `/users/{id}` | admin | Change role, address, username or password. 404 unknown, 409 duplicate address or username, 422 bad role |
| DELETE | `/users/{id}` | admin | Deactivate. 400 if you attempt it on your own account |

## 8. Status codes used

| Code | Meaning here |
|---|---|
| 200 | Success |
| 400 | Empty upload, or deactivating yourself |
| 401 | No session |
| 403 | Wrong role |
| 404 | Unknown contract, clause or account |
| 409 | Already finished, not ready, undecided clauses, duplicate account |
| 410 | The original file was never stored |
| 422 | Invalid verdict, missing edited wording, nothing to accept, wrong file type for export, invalid role |
