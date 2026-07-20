"""Seed the Papyrus accounts: one admin, two lawyers. Idempotent: run any time."""
import asyncio

from dotenv import load_dotenv

load_dotenv()

import app.users as u  # noqa: E402
from app.schemas import UserCreate  # noqa: E402
from fastapi_users.exceptions import UserAlreadyExists  # noqa: E402

# dev-only passwords, fine on a laptop; rotate them before anyone else can reach this API
SEEDS = [
    ("admin@papyrus.dev", "admin-dev-password", "admin", True),
    ("priya@papyrus.dev", "lawyer-dev-password", "lawyer", False),
    ("theo@papyrus.dev", "lawyer-dev-password", "lawyer", False),
]


async def main():
    await u.create_user_table()
    async with u.session_maker() as session:
        db = u.SQLAlchemyUserDatabase(session, u.User)
        mgr = u.UserManager(db)
        for email, password, role, superuser in SEEDS:
            try:
                await mgr.create(
                    UserCreate(email=email, password=password, role=role, is_superuser=superuser)
                )
                print(f"created {email} as {role}")
            except UserAlreadyExists:
                print(f"exists  {email}")


asyncio.run(main())
