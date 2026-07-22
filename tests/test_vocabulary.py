"""Papyrus is a fork of #1, so #1's vocabulary can survive a rename by accident.
This fails if any of it is left in a source file, comments included.

The allowlist below is not a way to dodge the test. Two of the banned words are
also ordinary legal English, and one reference to #1 is deliberate, so a literal
grep would fail forever on lines that are correct. Each entry names the reason.
Add to it only when the word genuinely belongs in that file.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

BANNED = ("ticket", "customer", "staff", "nimbus", "enklima")
PATTERN = re.compile("|".join(BANNED), re.IGNORECASE)

SCAN_SUFFIXES = {".py", ".ts", ".tsx", ".css", ".md", ".yml"}
SKIP_DIRS = {".venv", "node_modules", ".next", "__pycache__", ".git", "data", "docs"}

# path relative to the repo root -> why the banned word is correct there
ALLOWED = {
    # the synthetic contracts talk about supplying goods to other customers,
    # which is ordinary commercial wording, not #1 vocabulary
    "make_contracts.py": "contract wording legitimately says 'customers'",
    # states what Papyrus does NOT have; the contrast is the point of the line
    "app/users.py": "comment explains there is no customer role here",
    # naming the fork's parent is deliberate provenance, not leftover branding
    "README.md": "documents that this is forked from use case #1",
    # this file lists the banned words in order to test for them
    "tests/test_vocabulary.py": "the test itself",
}


def _files():
    for p in REPO_ROOT.rglob("*"):
        if p.suffix.lower() not in SCAN_SUFFIXES or not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(REPO_ROOT).parts):
            continue
        yield p


def test_no_leftover_use_case_1_vocabulary():
    offenders = []
    for path in _files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in ALLOWED:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            if PATTERN.search(line):
                offenders.append(f"{rel}:{n}: {line.strip()[:110]}")
    assert not offenders, "#1 vocabulary left in Papyrus:\n" + "\n".join(offenders)


def test_the_allowlist_still_earns_its_place():
    # if a rename later removes the banned word from an allowed file, the entry
    # is dead and should be deleted rather than left to hide a future mistake
    stale = []
    for rel in ALLOWED:
        path = REPO_ROOT / rel
        if not path.exists():
            stale.append(f"{rel} (file is gone)")
        elif not PATTERN.search(path.read_text(encoding="utf-8", errors="ignore")):
            stale.append(f"{rel} (no banned word left, drop the entry)")
    assert not stale, "stale allowlist entries:\n" + "\n".join(stale)
