import os

import psycopg  # type:ignore
from dotenv import load_dotenv
from fastapi.encoders import jsonable_encoder
from psycopg.rows import dict_row  # type:ignore
from psycopg.types.json import Jsonb  # type:ignore

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]


def _connect():
    return psycopg.connect(DATABASE_URL)


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contracts(
                contract_id TEXT PRIMARY KEY,
                filename TEXT,
                status TEXT,
                stage TEXT,
                risk_level TEXT,
                state JSONB,
                created_at TIMESTAMPTZ
            )
        """)
        # migration seam (the #1 pattern): the CREATE above only fires on a
        # fresh database. When this table needs a new column later, patch
        # existing databases right here with a line like:
        # conn.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS reviewer TEXT")
        # the uploaded file itself, kept so export can rewrite it in place
        conn.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS file_bytes BYTEA")


def save_file_bytes(contract_id: str, data: bytes) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE contracts SET file_bytes=%s WHERE contract_id=%s",
            (data, contract_id),
        )


def get_file_bytes(contract_id: str) -> bytes | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT file_bytes FROM contracts WHERE contract_id=%s", (contract_id,)
        ).fetchone()
    return bytes(row[0]) if row and row[0] is not None else None


def save_pending(contract_id: str, filename: str, created_at) -> None:
    # park the contract as "processing" BEFORE the graph runs, so the
    # lawyer's upload returns instantly and the docket has a card to show
    minimal = {
        "contract_id": contract_id,
        "filename": filename,
        "status": "processing",
        "stage": "reading",
        "clauses": [],
    }
    with _connect() as conn:
        conn.execute(
            """INSERT INTO contracts (contract_id, filename, status, stage, state, created_at)
               VALUES (%s, %s, 'processing', 'reading', %s, %s)
               ON CONFLICT (contract_id) DO NOTHING""",
            (contract_id, filename, Jsonb(minimal), created_at),
        )


def save(state: dict) -> None:
    # upsert the full state blob, and copy status/stage/risk level into
    # plain columns so list_all never has to open the blob
    risk = (state.get("contract_risk") or {}).get("level")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO contracts (contract_id, filename, status, stage, risk_level, state, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, now())
               ON CONFLICT (contract_id) DO UPDATE SET
                 filename=EXCLUDED.filename, status=EXCLUDED.status, stage=EXCLUDED.stage,
                 risk_level=EXCLUDED.risk_level, state=EXCLUDED.state""",
            (
                state["contract_id"],
                state.get("filename"),
                state.get("status"),
                state.get("stage"),
                risk,
                Jsonb(jsonable_encoder(state)),
            ),
        )


def get(contract_id: str) -> dict | None:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            "SELECT state, status, stage, created_at FROM contracts WHERE contract_id = %s",
            (contract_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        state = row["state"]
        # the columns are fresher than the blob while the graph is running
        # (set_stage and set_status touch only the columns), so stamp the
        # column values back onto the state before handing it out
        state["status"] = row["status"]
        state["stage"] = row["stage"]
        state["created_at"] = row["created_at"]
        return state


def list_all() -> list[dict]:
    # light rows only: the docket polls this every 4 seconds (Task 32),
    # so it reads the label columns plus two counts, never the whole blob
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("""
            SELECT contract_id, filename, status, stage, risk_level, created_at,
                   (SELECT COUNT(*) FROM jsonb_array_elements(COALESCE(state->'clauses', '[]'::jsonb)) AS c
                     WHERE jsonb_array_length(COALESCE(c->'findings', '[]'::jsonb)) > 0)::int AS flagged,
                   (SELECT COUNT(*) FROM jsonb_array_elements(COALESCE(state->'clauses', '[]'::jsonb)) AS c
                     WHERE jsonb_array_length(COALESCE(c->'findings', '[]'::jsonb)) > 0
                       AND c->>'decision' IS NOT NULL)::int AS decided
            FROM contracts ORDER BY created_at DESC
        """)
        return cur.fetchall()


def set_status(contract_id: str, status: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("UPDATE contracts SET status = %s WHERE contract_id = %s", (status, contract_id))
        return cur.rowcount > 0


def set_stage(contract_id: str, stage: str) -> bool:
    # graph nodes call this as each stage starts; the docket polls it live
    with _connect() as conn:
        cur = conn.execute("UPDATE contracts SET stage = %s WHERE contract_id = %s", (stage, contract_id))
        return cur.rowcount > 0


def decide_clause(contract_id: str, clause_id: str, decision: str, final_text: str) -> dict | None:
    # patch ONE clause inside the blob in a single statement: find its
    # array position, overwrite its decision and final_text, return it
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            """WITH pos AS (
                 SELECT (o.ord - 1)::int AS idx
                 FROM contracts,
                      jsonb_array_elements(state->'clauses') WITH ORDINALITY AS o(clause, ord)
                 WHERE contract_id = %s AND o.clause->>'clause_id' = %s
               )
               UPDATE contracts
               SET state = jsonb_set(
                     jsonb_set(state, ARRAY['clauses', pos.idx::text, 'decision'], to_jsonb(%s::text)),
                     ARRAY['clauses', pos.idx::text, 'final_text'], to_jsonb(%s::text))
               FROM pos
               WHERE contract_id = %s
               RETURNING state->'clauses'->pos.idx AS clause""",
            (contract_id, clause_id, decision, final_text, contract_id),
        )
        row = cur.fetchone()
        return row["clause"] if row else None


def all_decided(state: dict) -> bool:
    # finish gate: every clause that carries findings must carry a decision.
    # A contract with zero flagged clauses also counts as done.
    flagged = [c for c in state.get("clauses", []) if c.get("findings")]
    return all(bool(c.get("decision")) for c in flagged)
