# bench.py — Papyrus review-quality harness, scored against data/manifests/*.json
# The manifests are the labelled truth: every planted defect names the clause
# NUMBER it sits on, the inspector meant to catch it, and its severity. This
# drives the real graph over all 13 contracts, so it costs a GPU run (~30 min).
#
#   uv run python bench.py                 # all 13 contracts
#   uv run python bench.py --only kestrel  # one contract, substring match on the manifest stem
#
# Results land in bench_papyrus.json next to this file.
import json
import sys
import threading
import time
from pathlib import Path
from statistics import mean

from app.graph import PENDING_FILES, graph, initial_state, submit

HERE = Path(__file__).resolve().parent  # data paths hang off the file, not the CWD
MANIFEST_DIR = HERE / "data" / "manifests"
CONTRACT_DIR = HERE / "data" / "contracts"
OUTFILE = HERE / "bench_papyrus.json"

# --only <substring> so a single contract can be re-run for the price of one file
ONLY = None
if "--only" in sys.argv:
    i = sys.argv.index("--only")
    ONLY = sys.argv[i + 1] if len(sys.argv) > i + 1 else None
MODE = f"only={ONLY}" if ONLY else "full"

# Hard per-contract wall-clock cap. Nine nodes each with their own 240s guard and
# a retry can outlive any single node timeout, so the batch needs its own ceiling:
# a hung contract is abandoned, logged ERROR, and the remaining ones still run.
CONTRACT_TIMEOUT_S = 900


# --- pure scoring (no graph, no network — smoke-testable on a fabricated state) ---


def _num(v) -> str:
    # clause numbers are matched on, not clause_ids: ids are minted at extraction
    # and drift between runs, while "6", "6.", " 6 " all mean the same clause.
    return str(v or "").strip().rstrip(".").lower()


def _planted_split(manifest: dict) -> tuple[list, list]:
    # two kinds of ground truth share the planted list: defects sit on a numbered
    # clause, omissions carry {"missing": true} and no number/severity/inspector.
    planted = manifest.get("planted", []) or []
    return [p for p in planted if not p.get("missing")], [p for p in planted if p.get("missing")]


def score_contract(final_state: dict, manifest: dict, elapsed_s: float | None = None) -> dict:
    defects, omissions = _planted_split(manifest)
    clauses = final_state.get("clauses") or []

    # one bucket of findings per clause number; several clauses can share a number
    # if extraction stutters, so append rather than assign.
    by_number: dict[str, list] = {}
    for c in clauses:
        by_number.setdefault(_num(c.get("number")), []).extend(c.get("findings") or [])

    planted_numbers = {_num(p.get("number")) for p in defects}
    detail = []
    for p in defects:
        hits = by_number.get(_num(p.get("number")), [])
        detail.append(
            {
                "id": p.get("id"),
                "number": p.get("number"),
                "found": bool(hits),
                # attribution is judged only where the defect was found at all
                "inspector_ok": any(f.get("inspector") == p.get("inspector") for f in hits) if hits else None,
                "severity_ok": any(f.get("severity") == p.get("severity") for f in hits) if hits else None,
                "expected_inspector": p.get("inspector"),
                "got_inspectors": sorted({f.get("inspector") for f in hits if f.get("inspector")}),
                "expected_severity": p.get("severity"),
                "got_severities": sorted({f.get("severity") for f in hits if f.get("severity")}),
            }
        )

    found = [d for d in detail if d["found"]]
    # NOT called false positives: a finding on an unplanted clause may well be a
    # real defect the manifest author never wrote down. Counted, not condemned.
    unplanted = sum(len(v) for k, v in by_number.items() if k not in planted_numbers)
    total_findings = sum(len(v) for v in by_number.values())

    # omissions are matched on clause_type: the template inspector reports a type
    # and a plain sentence, never a number (the clause is absent by definition).
    reported_missing = [m for m in (final_state.get("missing_clauses") or []) if isinstance(m, dict)]
    reported_types = {str(m.get("clause_type", "")).lower() for m in reported_missing}
    expected_types = [str(m.get("clause_type", "")).lower() for m in omissions]
    missing_found = [t for t in expected_types if t in reported_types]

    status = final_state.get("status")
    return {
        "file": manifest.get("file"),
        "contract_type": manifest.get("contract_type"),
        "status": status,
        "error": final_state.get("error"),
        "extraction_ok": status not in ("extraction_failed", "error") and len(clauses) > 0,
        "clauses": len(clauses),
        "planted": len(defects),
        "found": len(found),
        "recall": (len(found) / len(defects)) if defects else None,
        "inspector_ok": sum(1 for d in found if d["inspector_ok"]),
        "inspector_rate": (sum(1 for d in found if d["inspector_ok"]) / len(found)) if found else None,
        "severity_ok": sum(1 for d in found if d["severity_ok"]),
        "severity_rate": (sum(1 for d in found if d["severity_ok"]) / len(found)) if found else None,
        "findings_total": total_findings,
        "unplanted_findings": unplanted,
        "unplanted_rate": (unplanted / total_findings) if total_findings else None,
        "missing_expected": len(omissions),
        "missing_found": len(missing_found),
        "missing_reported": len(reported_missing),
        "risk_level": (final_state.get("contract_risk") or {}).get("level"),
        "latency_s": round(elapsed_s, 1) if elapsed_s is not None else None,
        "detail": detail,
    }


def error_row(manifest: dict, msg: str, elapsed_s: float | None = None) -> dict:
    # an unscoreable run still occupies a row, so the totals stay honest about it
    defects, omissions = _planted_split(manifest)
    return {
        "file": manifest.get("file"),
        "contract_type": manifest.get("contract_type"),
        "status": "ERROR",
        "error": msg,
        "extraction_ok": False,
        "clauses": 0,
        "planted": len(defects),
        "found": 0,
        "recall": 0.0 if defects else None,
        "inspector_ok": 0,
        "inspector_rate": None,
        "severity_ok": 0,
        "severity_rate": None,
        "findings_total": 0,
        "unplanted_findings": 0,
        "unplanted_rate": None,
        "missing_expected": len(omissions),
        "missing_found": 0,
        "missing_reported": 0,
        "risk_level": None,
        "latency_s": round(elapsed_s, 1) if elapsed_s is not None else None,
        "detail": [],
    }


def aggregate(rows: list) -> dict:
    # counts are summed, never averaged over per-contract rates: five clean
    # contracts with recall=None would otherwise drag a mean around at random.
    s = lambda k: sum(r.get(k) or 0 for r in rows)  # noqa: E731
    planted, found = s("planted"), s("found")
    fnd_total, unpl = s("findings_total"), s("unplanted_findings")
    lats = [r["latency_s"] for r in rows if isinstance(r.get("latency_s"), (int, float))]
    return {
        "contracts": len(rows),
        "errors": sum(1 for r in rows if r.get("status") == "ERROR"),
        "extraction_ok": sum(1 for r in rows if r.get("extraction_ok")),
        "planted": planted,
        "found": found,
        "recall": (found / planted) if planted else None,
        "inspector_rate": (s("inspector_ok") / found) if found else None,
        "severity_rate": (s("severity_ok") / found) if found else None,
        "findings_total": fnd_total,
        "unplanted_findings": unpl,
        "unplanted_rate": (unpl / fnd_total) if fnd_total else None,
        "missing_expected": s("missing_expected"),
        "missing_found": s("missing_found"),
        "missing_reported": s("missing_reported"),
        "avg_latency_s": round(mean(lats), 1) if lats else None,
        "total_latency_s": round(sum(lats), 1) if lats else None,
    }


# --- the run (this is the part that costs money) -----------------------------


def load_manifests() -> list:
    out = []
    for p in sorted(MANIFEST_DIR.glob("*.manifest.json")):
        if ONLY and ONLY.lower() not in p.name.lower():
            continue
        m = json.loads(p.read_text(encoding="utf-8"))
        m["_stem"] = p.name.replace(".manifest.json", "")
        out.append(m)
    return out


def run_one(manifest: dict) -> dict:
    filename = manifest["file"]
    path = CONTRACT_DIR / filename
    contract_id = f"bench-{manifest['_stem']}"
    submit(contract_id, path.read_bytes())  # intake pops these bytes inside the graph
    t0 = time.perf_counter()
    box = {}

    def _work():
        try:
            box["final"] = graph.invoke(initial_state(contract_id, filename))
        except Exception as e:  # noqa: BLE001
            box["error"] = e

    th = threading.Thread(target=_work, daemon=True)  # daemon: a hung review is abandoned, never blocks exit
    th.start()
    th.join(CONTRACT_TIMEOUT_S)
    dt = time.perf_counter() - t0
    if th.is_alive():
        PENDING_FILES.pop(contract_id, None)  # the orphaned upload would otherwise leak for the process lifetime
        return error_row(manifest, f"timed out after {CONTRACT_TIMEOUT_S}s (a model call hung)", dt)
    if "error" in box:
        return error_row(manifest, str(box["error"]) or type(box["error"]).__name__, dt)
    return score_contract(box["final"], manifest, dt)


def _pct(v) -> str:
    return "  n/a" if v is None else f"{v:>5.0%}"


def main() -> None:
    manifests = load_manifests()
    if not manifests:
        print(f"no manifests matched {ONLY!r} in {MANIFEST_DIR}")
        sys.exit(1)

    rows = []
    for i, m in enumerate(manifests, start=1):
        print(f"[{i}/{len(manifests)}] {m['file']} ({m['contract_type']}, {len(m.get('planted', []))} planted) ...", flush=True)
        rows.append(run_one(m))
        r = rows[-1]
        print(f"    -> {r['status']} clauses={r['clauses']} found={r['found']}/{r['planted']} lat={r['latency_s']}s", flush=True)

    agg = aggregate(rows)
    w = 118
    print("\n" + "=" * w)
    print(f"{'contract':26} {'status':17} {'cl':>3} {'found':>7} {'recl':>5} {'insp':>5} {'sev':>5} {'unpl':>5} {'miss':>5} {'lat':>7}")
    print("-" * w)
    for r in rows:
        print(
            f"{str(r['file'])[:26]:26} {str(r['status']):17} {r['clauses']:>3} "
            f"{str(r['found']) + '/' + str(r['planted']):>7} {_pct(r['recall'])} {_pct(r['inspector_rate'])} "
            f"{_pct(r['severity_rate'])} {str(r['unplanted_findings']) + '/' + str(r['findings_total']):>5} "
            f"{str(r['missing_found']) + '/' + str(r['missing_expected']):>5} {str(r['latency_s']):>7}"
        )
    print("=" * w)
    print(f"config             : {MODE}, timeout {CONTRACT_TIMEOUT_S}s/contract")
    print(f"contracts          : {agg['contracts']}  (errors {agg['errors']}, extraction ok {agg['extraction_ok']})")
    print(f"detection recall   : {agg['found']}/{agg['planted']} = {_pct(agg['recall']).strip()}")
    print(f"inspector match    : {_pct(agg['inspector_rate']).strip()} of found defects came from the expected inspector")
    print(f"severity agreement : {_pct(agg['severity_rate']).strip()} of found defects matched the planted severity")
    print(f"unplanted findings : {agg['unplanted_findings']}/{agg['findings_total']} = {_pct(agg['unplanted_rate']).strip()}")
    print("                     (findings on clauses with nothing planted — some are real issues the manifest omits, not errors)")
    print(f"missing clauses    : {agg['missing_found']}/{agg['missing_expected']} planted omissions caught, {agg['missing_reported']} reported in total")
    print(f"latency            : avg {agg['avg_latency_s']}s, total {agg['total_latency_s']}s")

    misses = [(r["file"], d) for r in rows for d in r["detail"] if not d["found"]]
    if misses:
        print("\nmissed defects (nothing landed on that clause number):")
        for f, d in misses:
            print(f"  {f} clause {d['number']}: {d['id']}")

    wrong_insp = [(r["file"], d) for r in rows for d in r["detail"] if d["found"] and not d["inspector_ok"]]
    if wrong_insp:
        print("\nfound, but by another inspector (still a catch — attribution only):")
        for f, d in wrong_insp:
            print(f"  {f} clause {d['number']}: expected {d['expected_inspector']}, got {d['got_inspectors']}")

    out = {"config": MODE, "contract_timeout_s": CONTRACT_TIMEOUT_S, "totals": agg, "rows": rows}
    OUTFILE.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUTFILE}")


if __name__ == "__main__":
    main()
