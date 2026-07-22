"""Shared test setup.

app.store / app.users / app.router read their config at IMPORT time, so the
.env has to be loaded before any test module imports them. pytest imports
conftest first, which makes this the only reliable place to do it.
"""

from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN = REPO_ROOT / "tests" / "golden"

load_dotenv(REPO_ROOT / ".env")
