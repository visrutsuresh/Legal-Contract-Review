"""Shared test setup.

app.store / app.users / app.router read their config at IMPORT time, so the
.env has to be loaded before any test module imports them. pytest imports
conftest first, which makes this the only reliable place to do it.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN = REPO_ROOT / "tests" / "golden"

# pytest puts tests/ on the path, not the repo root, so `import app` fails unless
# the runner happens to be started with the root on PYTHONPATH. The sibling
# governance repo does the same thing in its own conftest.
sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")
