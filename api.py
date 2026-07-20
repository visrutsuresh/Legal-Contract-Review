import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.schemas import UserRead, UserUpdate
from app.users import (
    User,
    auth_backend,
    create_user_table,
    fastapi_users,
    require_admin,
    session_maker,
)

app = FastAPI(title="Papyrus Contract Review API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# login/logout only. NO register router: there is no open signup, the admin creates accounts.
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth", tags=["auth"])

# fastapi-users' own user routes (/users/me, /users/{id}), the whole block admin-gated
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_admin)],
)


@app.on_event("startup")
async def _startup():
    await create_user_table()


@app.get("/")
def health():
    return {"status": "ok", "product": "papyrus"}


@app.get("/config")
def brand_config():
    # the brand the frontend renders, same pattern as #1
    return {
        "brand_name": os.getenv("BRAND_NAME", "Papyrus"),
        "brand_tagline": os.getenv("BRAND_TAGLINE", ""),
    }


@app.get("/users")
async def list_users(user: User = Depends(require_admin)):
    # the admin screen's list; fastapi-users ships no list route of its own
    async with session_maker() as session:
        rows = (await session.execute(select(User))).scalars().all()
    return [
        {"id": str(r.id), "email": r.email, "role": r.role, "is_active": r.is_active}
        for r in rows
    ]
