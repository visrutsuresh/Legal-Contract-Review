import os
import threading
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from pydantic import BaseModel
from sqlalchemy import select

from app import precedent, store
from app.graph import PENDING_FILES, graph, initial_state, submit
from app.schemas import UserCreate, UserUpdate
from app.users import (
    User,
    UserManager,
    auth_backend,
    create_user_table,
    current_user,
    fastapi_users,
    require_admin,
    require_lawyer,
    session_maker,
)

store.init_db()  # make sure the contracts table exists when the API boots

app = FastAPI(title="Papyrus Contract Review API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth", tags=["auth"])
# no register router on purpose: accounts exist only when an admin creates them (see the /users routes)


@app.on_event("startup")
async def _startup():
    await create_user_table()
    try:
        precedent.ensure_collection()  # label the Weaviate drawer (Task 29) on a fresh machine
    except Exception as e:
        print(f"[precedent] ensure_collection failed (Weaviate down?): {e}", flush=True)


@app.get("/")
def health():
    return {"status": "ok", "product": "papyrus"}


@app.get("/config")
def brand_config():
    return {
        "brand_name": os.getenv("BRAND_NAME", "Papyrus"),
        "brand_tagline": os.getenv("BRAND_TAGLINE", ""),
    }


@app.post("/contracts")
async def upload_contract(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(require_lawyer),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    contract_id = f"P-{uuid.uuid4().hex[:8]}"
    store.save_pending(contract_id, file.filename, datetime.now(timezone.utc))
    background.add_task(_process, contract_id, file.filename, data)
    return {"contract_id": contract_id, "status": "processing"}


PIPELINE_TIMEOUT_S = 1200  # 20 min wall clock; the per-node guards in graph.py (240s + one retry each) do the real capping


def _invoke_guarded(contract_id: str, initial: dict):
    # ONE attempt, unlike #1's two: every node already retries once inside guarded(),
    # so an outer retry would re-run the whole contract and double the Modal bill.
    print(f"[pipeline] {contract_id} start", flush=True)
    box = {}

    def work():
        try:
            box["final"] = graph.invoke(initial, {"recursion_limit": 40})
        except Exception as e:
            box["error"] = str(e)

    th = threading.Thread(target=work, daemon=True)  # daemon: a hung run is abandoned, never blocks shutdown
    th.start()
    th.join(PIPELINE_TIMEOUT_S)
    if "final" in box:
        print(f"[pipeline] {contract_id} done", flush=True)
        return box["final"]
    print(f"[pipeline] {contract_id} failed: {box.get('error', 'timeout')}", flush=True)
    return None


TERMINAL_STATUSES = ("needs_review", "reviewed", "extraction_failed", "error")


def _process(contract_id: str, filename: str, file_bytes: bytes):
    # intake runs INSIDE the graph; submit() (Task 30, app/graph.py) parks the bytes
    # on the PENDING_FILES shelf its intake_node pops from.
    submit(contract_id, file_bytes)
    initial = initial_state(contract_id, filename)
    final = _invoke_guarded(contract_id, initial)
    PENDING_FILES.pop(contract_id, None)  # tidy the shelf even if the run died before intake took them
    if final is None:
        # the silent-discard lesson from #1: a dead run must SAY it died, never strand at "processing"
        initial["status"] = "error"
        initial["error"] = "The review run crashed or timed out before finishing. Nothing was saved half-done: upload the contract again."
        store.save(initial)
        return
    if final.get("status") not in TERMINAL_STATUSES:
        final["status"] = "error"
        final["error"] = final.get("error") or "The review run ended without a verdict. Upload the contract again."
    store.save(final)


@app.get("/contracts")
def list_contracts(user: User = Depends(require_lawyer)):
    return store.list_all()


@app.get("/contracts/{contract_id}")
def get_contract(contract_id: str, user: User = Depends(require_lawyer)):
    state = store.get(contract_id)
    if state is None:
        raise HTTPException(status_code=404, detail="contract not found")
    return state

VERDICTS = ("accepted", "rejected", "edited")


class DecisionIn(BaseModel):
    verdict: str
    edited_text: str | None = None


@app.post("/contracts/{contract_id}/clauses/{clause_id}/decision")
def decide(contract_id: str, clause_id: str, payload: DecisionIn, user: User = Depends(require_lawyer)):
    if payload.verdict not in VERDICTS:
        raise HTTPException(status_code=422, detail="verdict must be accepted, rejected, or edited")
    if payload.verdict == "edited" and not (payload.edited_text or "").strip():
        raise HTTPException(status_code=422, detail="edited needs edited_text: the wording you want instead")
    state = store.get(contract_id)
    if state is None:
        raise HTTPException(status_code=404, detail="contract not found")
    if state.get("status") == "reviewed":
        raise HTTPException(status_code=409, detail="this review is already finished")
    clause = next((c for c in state.get("clauses", []) if c.get("clause_id") == clause_id), None)
    if clause is None:
        raise HTTPException(status_code=404, detail="clause not found")
    if payload.verdict == "accepted":
        new_text = (clause.get("proposal") or {}).get("new_text")
        if not new_text:
            raise HTTPException(status_code=422, detail="this clause has no proposal to accept")
        final_text = new_text
    elif payload.verdict == "rejected":
        final_text = clause.get("text", "")
    else:
        final_text = payload.edited_text.strip()
    updated = store.decide_clause(contract_id, clause_id, payload.verdict, final_text)
    if updated is None:
        raise HTTPException(status_code=404, detail="clause not found")
    return {"contract_id": contract_id, "clause": updated}

def _assemble(clauses: list) -> str:
    # the reviewed document: every clause's final wording, in order, under its numbered heading
    parts = []
    for c in clauses:
        bits = []
        if c.get("number"):
            bits.append(f"{c['number']}.")
        if c.get("heading"):
            bits.append(c["heading"])
        head = " ".join(bits)
        body = c.get("final_text") or c.get("text", "")
        parts.append((head + "\n" + body).strip())
    return "\n\n".join(parts)


@app.post("/contracts/{contract_id}/finish")
def finish_review(contract_id: str, user: User = Depends(require_lawyer)):
    state = store.get(contract_id)
    if state is None:
        raise HTTPException(status_code=404, detail="contract not found")
    if state.get("status") == "reviewed":
        raise HTTPException(status_code=409, detail="this review is already finished")
    if state.get("status") != "needs_review":
        raise HTTPException(status_code=409, detail="this contract is not ready to finish yet")
    if not store.all_decided(state):
        raise HTTPException(status_code=409, detail="decide every flagged clause first")

    clauses = state.get("clauses", [])
    document = _assemble(clauses)
    store.set_status(contract_id, "reviewed")

    decisions = [c.get("decision") for c in clauses if c.get("findings")]
    counts = {
        "clauses": len(clauses),
        "flagged": len(decisions),
        "accepted": decisions.count("accepted"),
        "rejected": decisions.count("rejected"),
        "edited": decisions.count("edited"),
    }

    # file the finished review as precedent so future contracts can cite it
    filed = True
    try:
        contract_type = (state.get("meta") or {}).get("contract_type", "unknown")
        title = f"{state.get('filename', contract_id)} ({contract_type})"
        digest = "\n".join(
            f"{c['clause_id']} {c.get('heading', '')}: {c.get('decision')}" for c in clauses if c.get("findings")
        )
        executive = (state.get("summary") or {}).get("executive", "")
        precedent.index_reviewed(title, f"{executive}\n\nDecisions:\n{digest}".strip())
    except Exception as e:
        filed = False  # Weaviate being down must never block the lawyer's finish
        print(f"[precedent] {contract_id} filing failed: {e}", flush=True)

    return {"status": "reviewed", "document": document, "counts": counts, "precedent_filed": filed}

@app.get("/users/me")
def who_am_i(user: User = Depends(current_user)):
    # any signed-in account, not admin-gated: the browser calls this to learn who is logged in (Task 32)
    return {"id": str(user.id), "email": user.email, "role": user.role, "is_active": user.is_active}


ROLES = ("lawyer", "admin")


@app.get("/users")
async def list_users(user: User = Depends(require_admin)):
    async with session_maker() as session:
        rows = (await session.execute(select(User).order_by(User.email))).scalars().all()
        return [{"id": str(x.id), "email": x.email, "role": x.role, "is_active": x.is_active} for x in rows]


@app.post("/users")
async def create_account(payload: UserCreate, user: User = Depends(require_admin)):
    if payload.role not in ROLES:
        raise HTTPException(status_code=422, detail="role must be lawyer or admin")
    async with session_maker() as session:
        db = SQLAlchemyUserDatabase(session, User)
        mgr = UserManager(db)
        try:
            created = await mgr.create(payload)
        except UserAlreadyExists:
            raise HTTPException(status_code=409, detail="an account with that email already exists")
        created = await db.update(created, {"role": payload.role})  # belt and braces: pin the role even if a schema tweak ever drops it from create
        return {"id": str(created.id), "email": created.email, "role": created.role, "is_active": created.is_active}


@app.patch("/users/{user_id}")
async def edit_account(user_id: uuid.UUID, payload: UserUpdate, user: User = Depends(require_admin)):
    role = getattr(payload, "role", None)
    if role is not None and role not in ROLES:
        raise HTTPException(status_code=422, detail="role must be lawyer or admin")
    async with session_maker() as session:
        db = SQLAlchemyUserDatabase(session, User)
        mgr = UserManager(db)
        target = await db.get(user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="user not found")
        try:
            updated = await mgr.update(payload, target, safe=False)
        except UserAlreadyExists:
            raise HTTPException(status_code=409, detail="an account with that email already exists")
        return {"id": str(updated.id), "email": updated.email, "role": updated.role, "is_active": updated.is_active}


@app.delete("/users/{user_id}")
async def deactivate_account(user_id: uuid.UUID, user: User = Depends(require_admin)):
    # deactivate, never hard-delete: the audit trail keeps pointing at a real account
    async with session_maker() as session:
        db = SQLAlchemyUserDatabase(session, User)
        target = await db.get(user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="user not found")
        if target.id == user.id:
            raise HTTPException(status_code=400, detail="you cannot deactivate your own account")
        await db.update(target, {"is_active": False})
        return {"id": str(target.id), "deactivated": True}