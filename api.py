import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users.password import PasswordHelper
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import audit, export, precedent, store
from app.agents import counsel_agent
from app.graph import PENDING_FILES, graph, initial_state, submit
from app.schemas import UserCreate, UserUpdate
from app.users import (
    User,
    UserManager,
    auth_backend,
    create_user_table,
    current_user,
    fastapi_users,
    get_jwt_strategy,
    require_admin,
    require_lawyer,
    session_maker,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()  # tables exist when the API BOOTS, not when this module imports, so tests can drive it without a database
    await create_user_table()
    try:
        precedent.ensure_collection()  # label the Weaviate drawer (Task 29) on a fresh machine
    except Exception as e:
        print(f"[precedent] ensure_collection failed (Weaviate down?): {e}", flush=True)
    yield  # everything before the yield is startup; nothing to tear down after


app = FastAPI(title="Papyrus Contract Review API", lifespan=lifespan)

# comma-separated list, e.g. "https://papyrus.vercel.app,http://localhost:3000"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth", tags=["auth"])

_pw_helper = PasswordHelper()


async def _find_by_identifier(ident: str) -> User | None:
    # "@" means email; anything else is a username. Both compared lowercase.
    ident = ident.strip().lower()
    async with session_maker() as session:
        col = func.lower(User.email) if "@" in ident else func.lower(User.username)
        return (await session.execute(select(User).where(col == ident))).scalars().first()


@app.post("/auth/login-flex")
async def login_flex(credentials: OAuth2PasswordRequestForm = Depends()):
    # same cookie as /auth/login, but the identifier may be an email OR a username
    target = await _find_by_identifier(credentials.username)
    if target is None:
        _pw_helper.hash(credentials.password)  # burn the same time as a real check
        raise HTTPException(status_code=400, detail="LOGIN_BAD_CREDENTIALS")
    verified, _ = _pw_helper.verify_and_update(credentials.password, target.hashed_password)
    if not verified or not target.is_active:
        raise HTTPException(status_code=400, detail="LOGIN_BAD_CREDENTIALS")
    return await auth_backend.login(get_jwt_strategy(), target)


@app.get("/auth/needs-setup")
async def needs_setup():
    # the login page asks this to decide whether to show the one-time setup form
    async with session_maker() as session:
        n = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    return {"needs_setup": n == 0}


class BootstrapIn(BaseModel):
    # EmailStr, not str: UserCreate validates the address further down, and a plain
    # str would let that ValidationError escape the handler as a 500. The founding
    # admin mistyping their own address is the likeliest error on this screen, and
    # it must read as "that is not a valid address", not "Internal Server Error".
    email: EmailStr
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=200)


@app.post("/auth/bootstrap")
async def bootstrap_admin(payload: BootstrapIn):
    # first-run only: creates the founding admin while the system has ZERO
    # accounts, then this door closes forever. Single worker makes the
    # count-then-create window a non-issue in practice.
    async with session_maker() as session:
        n = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        if n:
            raise HTTPException(status_code=403, detail="setup is already complete; ask an administrator for an account")
        db = SQLAlchemyUserDatabase(session, User)
        mgr = UserManager(db)
        created = await mgr.create(UserCreate(email=payload.email, password=payload.password, role="admin"))
        created = await db.update(created, {"role": "admin", "username": payload.username.strip().lower()})
        return {"id": str(created.id), "email": created.email, "username": created.username, "role": created.role}
# no register router on purpose: accounts exist only when an admin creates them (see the /users routes)


@app.get("/")
def health():
    return {"status": "ok", "product": "papyrus"}


@app.get("/healthz")
def healthz():
    # the honest health check: touches each dependency instead of just answering.
    # / stays instant for uptime pings; this one is for humans and deploy gates.
    # Named to match the sibling systems so all three answer the same way.
    out = {"api": "ok"}
    # up/down only, no exception text: this route is unauthenticated and driver
    # errors would leak host and user strings to anyone who asks
    try:
        with store._connect() as conn:
            conn.execute("SELECT 1")
        out["postgres"] = "ok"
    except Exception:
        out["postgres"] = "down"
    try:
        precedent._client().close()
        out["weaviate"] = "ok"
    except Exception:
        out["weaviate"] = "down"
    out["status"] = "ok" if out["postgres"] == "ok" and out["weaviate"] == "ok" else "degraded"
    return out


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
    store.save_file_bytes(contract_id, data)  # kept so export can rewrite the original in place
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


@app.get("/contracts/{contract_id}/audit")
def get_audit(contract_id: str, user: User = Depends(require_lawyer)):
    # the tamper-evident trail. Every node's step was hash-chained into the
    # state by the `chain` reducer as the review ran; verify() re-walks the
    # chain and reports the FIRST entry whose hash no longer follows from the
    # one before it, which is what an edit straight into the JSONB blob looks
    # like. A legal review has to be able to prove it was not quietly altered.
    state = store.get(contract_id)
    if state is None:
        raise HTTPException(status_code=404, detail="contract not found")
    log = state.get("audit") or []
    broken_at = audit.verify(log)
    return {
        "contract_id": contract_id,
        "entries": log,
        "count": len(log),
        "intact": broken_at == -1,
        "broken_at": None if broken_at == -1 else broken_at,
    }


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


@app.post("/contracts/{contract_id}/clauses/{clause_id}/counsel")
def counsel(contract_id: str, clause_id: str, user: User = Depends(require_lawyer)):
    """Wake the counsel agent on ONE flagged clause. Unlike every other agent here
    it CHANGES the record: it escalates to senior counsel and records the ask it
    wants put to the counterparty, both hash-chained. It still cannot accept,
    reject or edit anything, so the lawyer's signature is still the only way a
    clause changes wording."""
    state = store.get(contract_id)
    if state is None:
        raise HTTPException(status_code=404, detail="contract not found")
    if state.get("status") == "reviewed":
        raise HTTPException(status_code=409, detail="this review is already finished")
    clause = next((c for c in state.get("clauses", []) if c.get("clause_id") == clause_id), None)
    if clause is None:
        raise HTTPException(status_code=404, detail="clause not found")
    if not (clause.get("findings") or []):
        raise HTTPException(status_code=422, detail="nothing was flagged on this clause, so there is nothing to counsel on")
    out = counsel_agent(contract_id, clause)
    # the agent wrote through its own tools, so re-read rather than saving our
    # stale snapshot over the top of its work
    fresh = store.get(contract_id) or state
    clause = next((c for c in fresh.get("clauses", []) if c.get("clause_id") == clause_id), clause)
    return {
        "contract_id": contract_id,
        "clause_id": clause_id,
        **out,
        "escalation": clause.get("escalated"),
        "concession_ask": clause.get("concession_ask"),
    }


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


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@app.get("/contracts/{contract_id}/export")
def export_contract(contract_id: str, user: User = Depends(require_lawyer)):
    # the corrected contract in its original file format: identical everywhere
    # except the clauses the lawyer changed
    state = store.get(contract_id)
    if state is None:
        raise HTTPException(status_code=404, detail="contract not found")
    if state.get("status") != "reviewed":
        raise HTTPException(status_code=409, detail="finish the review first")
    if state.get("source_format") != "docx":
        # ponytail: pdf export would mean re-laying-out pages; docx covers the corpus
        raise HTTPException(status_code=422, detail="export is only available for .docx uploads")
    original = store.get_file_bytes(contract_id)
    if original is None:
        raise HTTPException(status_code=410, detail="the original file was not stored (uploaded before export existed): upload it again")
    corrected, unmatched = export.export_docx(original, state.get("clauses", []))
    filename = state.get("filename") or f"{contract_id}.docx"
    return Response(
        content=corrected,
        media_type=DOCX_MIME,
        headers={
            "Content-Disposition": f'attachment; filename="reviewed-{filename}"',
            # clauses whose original wording could not be located verbatim; their
            # edits are NOT in the file, so the caller can warn instead of trusting it blindly
            "X-Unmatched-Clauses": ",".join(unmatched),
        },
    )

@app.get("/users/me")
def who_am_i(user: User = Depends(current_user)):
    # any signed-in account, not admin-gated: the browser calls this to learn who is logged in (Task 32)
    return {"id": str(user.id), "email": user.email, "username": user.username, "role": user.role, "is_active": user.is_active}


ROLES = ("lawyer", "admin")


@app.get("/users")
async def list_users(user: User = Depends(require_admin)):
    async with session_maker() as session:
        rows = (await session.execute(select(User).order_by(User.email))).scalars().all()
        return [{"id": str(x.id), "email": x.email, "username": x.username, "role": x.role, "is_active": x.is_active} for x in rows]


@app.post("/users")
async def create_account(payload: UserCreate, user: User = Depends(require_admin)):
    if payload.role not in ROLES:
        raise HTTPException(status_code=422, detail="role must be lawyer or admin")
    payload.username = (payload.username or "").strip().lower() or None
    async with session_maker() as session:
        db = SQLAlchemyUserDatabase(session, User)
        mgr = UserManager(db)
        try:
            created = await mgr.create(payload)  # username rides along in the schema, so a duplicate fails HERE at the insert
        except UserAlreadyExists:
            raise HTTPException(status_code=409, detail="an account with that email already exists")
        except IntegrityError:
            await session.rollback()  # nothing was created; the failed insert just poisons the session
            raise HTTPException(status_code=409, detail="that username is already taken")
        created = await db.update(created, {"role": payload.role})  # belt and braces: pin the role even if a schema tweak ever drops it from create
        return {"id": str(created.id), "email": created.email, "username": created.username, "role": created.role, "is_active": created.is_active}


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
        if payload.username is not None:
            payload.username = payload.username.strip().lower() or None
        try:
            updated = await mgr.update(payload, target, safe=False)
        except UserAlreadyExists:
            raise HTTPException(status_code=409, detail="an account with that email already exists")
        except IntegrityError:
            raise HTTPException(status_code=409, detail="that username is already taken")
        return {"id": str(updated.id), "email": updated.email, "username": updated.username, "role": updated.role, "is_active": updated.is_active}


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

@app.get("/contracts/{contract_id}/report")
def review_report(contract_id: str, user: User = Depends(require_lawyer)):
    # a printable one-page review report for ONE contract: executive summary,
    # the risk rollup, every clause-level finding with its plain-English fix and
    # suggested wording, and the negotiation points. All figures are read from
    # the stored assessment (report.build_report_html), never recomputed loosely,
    # so the page can never claim more than the review actually found. Returned as
    # a self-contained HTML page the lawyer prints to PDF from the browser.
    from app import report
    state = store.get(contract_id)
    if state is None:
        raise HTTPException(status_code=404, detail="contract not found")
    if state.get("status") not in ("needs_review", "reviewed"):
        raise HTTPException(status_code=409, detail="the review is not finished yet")
    html_doc = report.build_report_html(state)
    stem = (state.get("filename") or contract_id).rsplit(".", 1)[0]
    return Response(
        content=html_doc,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="review-report-{stem}.html"'},
    )
