import json
from pathlib import Path

from app import precedent

TOOLS = {}  # name -> function

# anchored to this file, NOT the working directory: run_tool swallows every
# exception into an "ERROR: ..." string the agent reads as a normal observation,
# so a bad relative path would not crash, it would quietly tell all four
# inspectors the rules pack and the templates do not exist
REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "data" / "templates"
RULES_FILE = REPO_ROOT / "policy_rules.md"


def tool(fn):
    # Register a function so an agent can call it by name
    TOOLS[fn.__name__] = fn
    return fn


def run_tool(name: str, args: dict) -> str:
    # Dial a tool by name with its args; return the result as a text
    fn = TOOLS.get(name)
    if fn is None:
        return f"ERROR: unknown tool {name!r}"
    try:
        return str(fn(**args))
    except Exception as e:
        return f"ERROR: {e}"


@tool
def template_fetch(contract_type: str) -> dict:
    # The firm's standard contract of this type: clause list with required flags
    path = TEMPLATE_DIR / f"{contract_type.lower().strip()}.json"
    if not path.exists():
        known = sorted(p.stem for p in TEMPLATE_DIR.glob("*.json"))
        return {"error": f"no template for {contract_type!r}", "known_types": known}
    return json.loads(path.read_text())


@tool
def rules_read(contract_type: str) -> str:
    # the firm's compliance rules pack (small markdown file, returned whole)
    return RULES_FILE.read_text()


@tool
def precedent_search(query: str) -> list:
    # Past reviewed contracts that read like the query, best match first
    return precedent.search(query)
