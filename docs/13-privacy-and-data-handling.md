# 13. Privacy and Data Handling

**Version 1, 2026-07-28.**

## 1. Position

Every contract in this system is synthetic. The design nevertheless assumes real confidential documents, because that is the only way the privacy claim is worth making: **contract text never reaches a third-party model provider, and the codebase contains no client that could send it to one.**

## 2. What data the system holds

| Data | Where |
|---|---|
| The original uploaded document, as bytes | The contracts table, kept so export can rewrite it |
| Extracted plain text and the clause list | Inside the stored state |
| Findings, proposals, negotiating positions | Inside the stored state |
| The lawyer's decisions and final wording | Inside the stored state |
| A summary of each finished review | The precedent cabinet, retrievable for later contracts |
| Account details | The accounts table, passwords hashed |

Findings and negotiation points deserve particular care: an ask, a fallback and a walk-away position are more sensitive than the contract itself, because they reveal what the client will settle for.

## 3. Where data flows

| Flow | Destination |
|---|---|
| Extraction, inspection, negotiation, summary | The self-hosted model endpoint on rented GPU infrastructure, over an authenticated connection |
| Embeddings for precedent search | Computed on the local machine; no text is sent out to be indexed |
| Storage | Local Postgres and local Weaviate, both in Docker |
| Export | Produced locally, downloaded by the lawyer |

Nothing is sent to a counterparty by the system. The corrected document is a download; a human decides what leaves.

The honest qualification: the model lane is self-hosted but not on premises. The weights and runtime are ours and no provider trains on the traffic, but contract text does travel to that endpoint.

## 4. Precedent cabinet and confidentiality

Finishing a review files a summary of it into a shared searchable cabinet, and a later contract, potentially for a different client, can retrieve it. On synthetic data that is the intended learning loop. With real client work it would be a **conflict and confidentiality problem**, and would need at minimum: anonymisation of parties before filing, and a matter or client boundary on retrieval. That is the single largest change this system would need before real use, and it is a design change rather than a bug.

## 5. Retention

Nothing is deleted. Contracts, their original bytes, their state and their precedent entries are kept indefinitely. There is no retention schedule, no deletion endpoint, and no way to remove a review from the precedent cabinet. Acceptable for synthetic material only.

## 6. Access

Two roles. A lawyer reaches every contract in the instance; an administrator additionally manages accounts. There is no per-matter or per-client boundary, which is called out in [12-security-review.md](12-security-review.md) as the first control to add.

## 7. Gaps to close before real documents

1. A matter boundary on both contracts and precedent retrieval.
2. Anonymisation of parties before a review is filed as precedent.
3. Retention and deletion, including from the vector store.
4. Encryption at rest, since the original documents are stored as bytes.
5. A record of which model version reviewed which contract, retained for audit alongside the hash chain.
