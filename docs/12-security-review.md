# 12. Security Review

**Version 1, 2026-07-28.** A threat model for a single-machine demonstration system holding confidential documents.

## 1. Assets

Contract text and the original uploaded files; the findings and proposals, which reveal a negotiating position; account credentials; the model lane token; the audit chain's integrity.

## 2. Trust boundaries

| Boundary | Other side |
|---|---|
| Browser to API | Anyone who can reach the port |
| API to the model lane | An internet-reachable GPU endpoint |
| API to data stores | Local Docker containers |

There is deliberately **no third-party model provider** in this list.

## 3. Threats and controls

| # | Threat | Control today | Residual risk |
|---|---|---|---|
| 1 | An outsider creates an account and reads contracts | **No open signup.** Only an administrator creates accounts | An administrator account is a single point of trust |
| 2 | Password guessing | Hashed passwords | **No rate limiting or lockout** |
| 3 | Session theft | Signed cookie with a secret from the environment | The cookie is not marked secure, because the demonstration runs over plain HTTP locally |
| 4 | Contract text leaks to a model provider | There is no cloud client in the codebase and only one lane exists | The lane is rented infrastructure, so text does leave the machine to a self-hosted endpoint over an authenticated connection |
| 5 | The lane token is stolen and the GPU budget is spent | Shared-secret token and a hard platform spend cap | The endpoint is internet reachable; the cap is the real backstop |
| 6 | A lawyer sees another firm's contracts | Every account sees every contract in this instance | **No per-matter access control.** Acceptable for a demonstration, unacceptable for real use |
| 7 | The audit trail is edited to hide a decision | Hash chain, verified on read, tested against a forged database row | Tamper evident, not tamper proof; nothing external notarises it |
| 8 | A malicious document exploits the parser | Only two formats are accepted, and text extraction runs in-process | No sandboxing of document parsing |
| 9 | Prompt injection inside a contract, aiming to suppress a finding or plant wording | Every finding must carry a quote of the offending wording, and a lawyer decides every flagged clause | **Not systematically tested.** A crafted clause instructing the reviewer is a plausible attack on this exact product |
| 10 | An exported document contains wording the lawyer never approved | Export only writes clauses whose decision is recorded, and unlocatable clauses are named rather than guessed | Matching is by wording, so an unusual document could match the wrong paragraph |
| 11 | Secrets committed to the repository | Only blank placeholders are committed | Nothing scans commits |

## 4. What would have to change before real client documents

In priority order:

1. Per-matter access control, so an account reaches only its own files.
2. Rate limiting and lockout on sign-in.
3. HTTPS with a secure session cookie.
4. Encryption at rest for the database, since the original documents are stored as bytes.
5. A tested position on prompt injection inside contract text.
6. A retention and deletion workflow, including removal from the precedent cabinet.

## 5. Deliberate non-goals

No penetration test, no dependency vulnerability scanning, no formal access model beyond two roles. This is a demonstration system on synthetic contracts, and nothing here should be read as production readiness for legal work.
