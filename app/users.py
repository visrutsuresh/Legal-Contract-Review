import os
import uuid

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from sqlalchemy import Column, String
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()
SECRET = os.getenv("AUTH_SECRET", "")
if not SECRET:
    raise RuntimeError("AUTH_SECRET missing from .env")

# reuse the app's DATABASE_URL but through the async driver fastapi-users needs
ASYNC_DB_URL = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")


class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    # lawyer | admin. The first account is created by the one-time setup screen
    # (bootstrap); after that only admins create accounts. No open signup.
    role = Column(String, nullable=False, default="lawyer")
    username = Column(String, unique=True, nullable=True)  # optional sign-in alias next to the email


engine = create_async_engine(ASYNC_DB_URL)
session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_user_table():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # migration seam: create_all only fires on a fresh database; existing
        # databases get the username column patched in here
        from sqlalchemy import text

        await conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS username VARCHAR'))
        await conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS user_username_uniq ON "user"(username)'))


async def get_user_db():
    async with session_maker() as session:
        yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


# local dev: secure off, samesite lax. Deployed, where the front end and the API sit on
# different domains, set COOKIE_SECURE=true and COOKIE_SAMESITE=none, or the session
# cookie is silently dropped and login appears to do nothing. Defaults match the
# previous hardcoded behaviour, so local development is unchanged.
cookie_transport = CookieTransport(
    cookie_name="papyrus",
    cookie_max_age=60 * 60 * 24 * 7,
    cookie_secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    cookie_samesite=os.getenv("COOKIE_SAMESITE", "lax"),
)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=60 * 60 * 24 * 7)


auth_backend = AuthenticationBackend(name="cookie", transport=cookie_transport, get_strategy=get_jwt_strategy)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])
current_user = fastapi_users.current_user(active=True)


def require_lawyer(user: User = Depends(current_user)) -> User:
    if user.role not in ("lawyer", "admin"):
        raise HTTPException(status_code=403, detail="lawyers only")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    return user
