"""The fixed Papyrus pipeline: 9 nodes, one parallel fan-out, no free routing.
The ORDER is code; the judgement lives inside each agent (bounded autonomy, D31)."""

from concurrent.futures import ThreadPoolExecutor

from langgraph.graph import END, START, StateGraph

from app import agents, intake, store
from app.state import INSPECTORS, ContractState, risk_rollup, valid_finding

# --- file handoff -----------------------------------------------------------

PENDING_FILES: dict[str, bytes] = {}


def submit(contract_id: str, file_bytes: bytes) -> None:
    """Park the uploaded bytes for intake_node. LangGraph state silently drops
    keys that are not declared channels, and raw bytes must not live in saved
    state anyway, so the file rides OUTSIDE the graph, keyed by contract id."""
    PENDING_FILES[contract_id] = file_bytes


def initial_state(contract_id: str, filename: str) -> dict:
    return {
        "contract_id": contract_id,
        "filename": filename,
        "source_format": "",
        "status": "processing",
        "stage": "reading",
        "meta": {},
        "raw_text": "",
        "clauses": [],
        "findings_raw": [],
        "inspector_reports": [],
        "missing_clauses": [],
        "contract_risk": {},
        "negotiation_points": [],
        "summary": {},
        "audit": [],
        "error": None,
    }


# --- narration --------------------------------------------------------------


def _stage(state: ContractState, stage: str) -> None:
    """Write the stage where the docket's polling can see it, mid-run."""
    try:
        store.set_stage(state["contract_id"], stage)
    except Exception:
        pass  # narration must never kill a review (demo runs have no DB row)
    print(f"[pipeline] {state['contract_id']} stage={stage}", flush=True)


# --- the guard --------------------------------------------------------------


def guarded(fn, name: str, timeout_s: int = 240):
    """Wall-clock cap plus one retry around a node. Inspectors degrade on a
    double failure; spine nodes stamp status=error. The graph never crashes."""

    def node(state: ContractState) -> dict:
        err = "unknown failure"
        for attempt in (1, 2):
            print(f"[pipeline] {state['contract_id']} {name} attempt {attempt}", flush=True)
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                out = pool.submit(fn, state).result(timeout=timeout_s)
                print(f"[pipeline] {state['contract_id']} {name} done", flush=True)
                return out
            except Exception as e:
                err = str(e) or type(e).__name__
                print(f"[pipeline] {state['contract_id']} {name} attempt {attempt} failed: {err}", flush=True)
            finally:
                pool.shutdown(wait=False)
        if name in INSPECTORS:
            return {
                "inspector_reports": [{"inspector": name, "status": "failed", "note": err}],
                "audit": [f"{name} failed: {err}"],
            }
        return {
            "status": "error",
            "error": f"The review stopped at the {name} step after two attempts: {err}",
            "audit": [f"{name} failed: {err}"],
        }

    return node


# --- spine nodes ------------------------------------------------------------


def intake_node(state: ContractState) -> dict:
    _stage(state, "reading")
    data = PENDING_FILES.pop(state["contract_id"], None)
    if data is None:
        return {
            "status": "extraction_failed",
            "error": "No file arrived for this contract.",
            "audit": ["intake failed: no file"],
        }
    try:
        parsed = intake.extract_text(state["filename"], data)
    except Exception as e:
        parsed = {"error": f"The file could not be opened: {e}"}
    if parsed.get("error") or not parsed.get("raw_text", "").strip():
        msg = parsed.get("error") or "The file opened but held no readable text (a scanned document needs a person)."
        return {"status": "extraction_failed", "error": msg, "audit": [f"intake failed: {msg}"]}
    return {
        "source_format": parsed.get("source_format", "docx"),
        "raw_text": parsed["raw_text"],
        "meta": {"pages": parsed.get("pages", 0)},
        "stage": "reading",
        "audit": [f"intake done: {parsed.get('source_format')}, {parsed.get('pages', 0)} pages"],
    }


def extraction_node(state: ContractState) -> dict:
    if state.get("status") in ("extraction_failed", "error"):
        return {"audit": ["extraction skipped: intake failed"]}
    _stage(state, "extracting")
    out = None
    for _attempt in (1, 2):  # the one repair retry (D37)
        try:
            cand = agents.extraction_agent(state["raw_text"])
            if len(cand.get("clauses", [])) >= 3:
                out = cand
                break
        except Exception as e:
            print(f"[pipeline] {state['contract_id']} extraction attempt failed: {e}", flush=True)
    if out is None:
        return {
            "status": "extraction_failed",
            "error": "The text could not be split into clauses. A person needs to look at this document.",
            "audit": ["extraction failed: could not split clauses"],
        }
    meta = {**state.get("meta", {}), **out.get("meta", {})}
    clauses = []
    for c in out["clauses"]:
        c = dict(c)
        c.setdefault("findings", [])
        c.setdefault("proposal", None)
        c.setdefault("decision", None)
        c.setdefault("final_text", c.get("text", ""))
        clauses.append(c)
    _stage(state, "inspecting")  # last writer before the parallel superstep
    return {
        "clauses": clauses,
        "meta": meta,
        "stage": "inspecting",
        "audit": [f"extraction done: {len(clauses)} clauses, type {meta.get('contract_type', '?')}"],
    }


# --- the four inspectors ----------------------------------------------------
# LangGraph runs every branch fanned out from one node in the SAME step, in
# parallel threads. Parallel writers may only touch reducer keys (findings_raw,
# inspector_reports, audit) or a key nobody else writes this step. None of them
# writes `stage`: two plain writes to one key in one step is an error.


def compliance_node(state: ContractState) -> dict:
    return agents.compliance_agent(state)


def risk_node(state: ContractState) -> dict:
    return agents.risk_agent(state)


def template_node(state: ContractState) -> dict:
    return agents.template_agent(state)


def financial_node(state: ContractState) -> dict:
    return agents.financial_agent(state)


# --- fan-in merge (plain code, not an agent) --------------------------------


def inspector_status(reports: list) -> dict:
    """Derive {"compliance": "ok"|"failed", ...} from inspector_reports."""
    status = {name: "failed" for name in INSPECTORS}  # no report = never assumed ok
    for r in reports:
        if r.get("inspector") in status:
            status[r["inspector"]] = r.get("status", "failed")
    return status


def fan_in(state: ContractState) -> dict:
    clauses, by_id = [], {}
    for c in state["clauses"]:
        c = dict(c)
        c["findings"] = []
        clauses.append(c)
        by_id[c["clause_id"]] = c
    kept = dropped = 0
    for f in state["findings_raw"]:
        target = by_id.get(f.get("clause_id")) if isinstance(f, dict) else None
        if target is None or not valid_finding(f):
            dropped += 1  # half-formed findings are never shown (D34c)
            continue
        target["findings"].append(f)
        kept += 1
    missing = [m for m in state.get("missing_clauses", []) if isinstance(m, dict) and m.get("severity") in ("high", "medium", "low")]
    checks = inspector_status(state["inspector_reports"])
    _stage(state, "negotiating")
    return {
        "clauses": clauses,
        "missing_clauses": missing,
        "contract_risk": risk_rollup(clauses, missing),
        "stage": "negotiating",
        "audit": [f"fan-in: {kept} findings pinned, {dropped} dropped, checks {checks}"],
    }


# --- negotiation and summary ------------------------------------------------


def negotiation_node(state: ContractState) -> dict:
    if state.get("status") == "error":
        return {"audit": ["negotiation skipped: upstream error"]}
    flagged = sum(1 for c in state["clauses"] if c.get("findings"))
    if flagged == 0 and not state.get("missing_clauses"):
        clauses = [{**c, "final_text": c.get("final_text") or c.get("text", "")} for c in state["clauses"]]
        _stage(state, "summarising")
        return {
            "clauses": clauses,
            "negotiation_points": [],
            "stage": "summarising",
            "audit": ["negotiation skipped: nothing flagged"],
        }
    out = agents.negotiation_agent(state["clauses"], state.get("missing_clauses", []))
    proposals = sum(1 for c in out["clauses"] if c.get("proposal"))
    _stage(state, "summarising")
    return {
        "clauses": out["clauses"],
        "negotiation_points": out["negotiation_points"],
        "stage": "summarising",
        "audit": [f"negotiation done: {proposals} proposals for {flagged} flagged clauses"],
    }


def summary_node(state: ContractState) -> dict:
    if state.get("status") == "error":
        return {"audit": ["summary skipped: upstream error"]}
    out = agents.summary_agent(
        state["meta"],
        state["clauses"],
        state.get("missing_clauses", []),
        state.get("contract_risk", {}),
        state.get("inspector_reports", []),
    )
    _stage(state, "done")
    return {"summary": out, "status": "needs_review", "stage": "done", "audit": ["summary done"]}


# --- wiring -----------------------------------------------------------------


def after_extraction(state: ContractState):
    if state.get("status") in ("extraction_failed", "error"):
        return END
    return list(INSPECTORS)  # all four names at once = the parallel fan-out


builder = StateGraph(ContractState)
builder.add_node("intake_node", guarded(intake_node, "intake_node"))
builder.add_node("extraction", guarded(extraction_node, "extraction"))
builder.add_node("compliance", guarded(compliance_node, "compliance"))
builder.add_node("risk", guarded(risk_node, "risk"))
builder.add_node("template", guarded(template_node, "template"))
builder.add_node("financial", guarded(financial_node, "financial"))
builder.add_node("fan_in", guarded(fan_in, "fan_in"))
builder.add_node("negotiation", guarded(negotiation_node, "negotiation"))
builder.add_node("summary", guarded(summary_node, "summary"))

builder.add_edge(START, "intake_node")
builder.add_edge("intake_node", "extraction")
builder.add_conditional_edges("extraction", after_extraction, list(INSPECTORS) + [END])
for _name in INSPECTORS:
    builder.add_edge(_name, "fan_in")
builder.add_edge("fan_in", "negotiation")
builder.add_edge("negotiation", "summary")
builder.add_edge("summary", END)

graph = builder.compile()
