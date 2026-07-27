"""Build a printable one-page review report for a single contract.

Everything on the page is read straight from the contract's stored state
(the same blob the detail view uses): the risk rollup, every finding with its
plain-English fix, the negotiation points, and the executive summary. Nothing
is recomputed or invented here beyond simple counts of what is already stored,
so the report can never claim more than the review actually found.

The output is a self-contained HTML document (its own inline styles, no external
assets) so a lawyer can open it, read it, and use the browser's Print dialog to
save it as PDF. It satisfies Agent 8's "review reports" requirement.
"""

import html
from datetime import datetime, timezone

BRAND = "Papyrus"

INSPECTOR_LABELS = {
    "compliance": "Compliance",
    "risk": "Risk",
    "template": "Standard-terms",
    "financial": "Financial",
}

SEV_ORDER = {"high": 0, "medium": 1, "low": 2}
SEV_LABEL = {"high": "Serious", "medium": "Worth a look", "low": "Minor"}


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _all_findings(clauses: list) -> list:
    return [f for c in clauses for f in (c.get("findings") or [])]


def severity_counts(clauses: list, missing: list) -> dict:
    # findings AND missing clauses both carry a severity; the risk rollup counts
    # both, so this report does too, or the tiles would disagree with the tier.
    sevs = [f.get("severity") for f in _all_findings(clauses)] + [m.get("severity") for m in missing]
    return {"high": sevs.count("high"), "medium": sevs.count("medium"), "low": sevs.count("low")}


def inspector_counts(clauses: list, missing: list) -> dict:
    counts = {k: 0 for k in INSPECTOR_LABELS}
    for f in _all_findings(clauses):
        ins = f.get("inspector")
        if ins in counts:
            counts[ins] += 1
    for m in missing:  # missing clauses are stamped inspector="template" by the template agent
        ins = m.get("inspector", "template")
        if ins in counts:
            counts[ins] += 1
    return counts


def _tile(number: int, label: str, tone: str) -> str:
    return (
        f'<div class="tile tile-{tone}">'
        f'<div class="tile-num">{number}</div>'
        f'<div class="tile-label">{_esc(label)}</div>'
        f"</div>"
    )


def _finding_block(f: dict) -> str:
    parts = [
        f'<div class="plain">{_esc(f.get("plain"))}</div>',
        f'<div class="term">{_esc(f.get("term"))}</div>',
        '<div class="trio">',
        f'<div class="wrong"><b>What is wrong</b>{_esc(f.get("wrong"))}</div>',
        f'<div class="change"><b>What we would change it to</b>{_esc(f.get("change"))}</div>',
        f'<div class="ignore"><b>If you ignore it</b>{_esc(f.get("ignore"))}</div>',
        "</div>",
    ]
    if f.get("evidence"):
        parts.append(f'<div class="evidence">Quoted from the clause: &ldquo;{_esc(f.get("evidence"))}&rdquo;</div>')
    inspector = INSPECTOR_LABELS.get(f.get("inspector", ""), f.get("inspector", ""))
    sev = f.get("severity", "")
    parts.append(
        f'<div class="fmeta">{_esc(SEV_LABEL.get(sev, sev))} &middot; caught by the {_esc(inspector)} check</div>'
    )
    return "".join(parts)


def _decision_line(c: dict) -> str:
    d = c.get("decision")
    if d == "accepted":
        return '<div class="decision acc">Lawyer decision: accepted the suggested wording.</div>'
    if d == "rejected":
        return '<div class="decision rej">Lawyer decision: kept the original wording.</div>'
    if d == "edited":
        return f'<div class="decision acc">Lawyer decision: replaced with their own wording &mdash; &ldquo;{_esc(c.get("final_text"))}&rdquo;</div>'
    return '<div class="decision open">Not yet decided.</div>'


def build_report_html(state: dict) -> str:
    meta = state.get("meta") or {}
    clauses = state.get("clauses") or []
    missing = state.get("missing_clauses") or []
    risk = state.get("contract_risk") or {}
    summary = state.get("summary") or {}
    points = state.get("negotiation_points") or []

    filename = state.get("filename") or state.get("contract_id") or "contract"
    contract_id = state.get("contract_id") or ""
    contract_type = (meta.get("contract_type") or "unknown").upper()
    parties = ", ".join(meta.get("parties") or []) or "not stated"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    level = (risk.get("level") or "unknown").lower()
    score = risk.get("score")
    score_txt = f"{score}/100" if isinstance(score, int) else "not scored"
    why = risk.get("why") or ""

    sev = severity_counts(clauses, missing)
    ins = inspector_counts(clauses, missing)

    flagged = [c for c in clauses if c.get("findings")]

    out = []
    out.append("<!doctype html>")
    out.append('<html lang="en"><head><meta charset="utf-8">')
    out.append(f"<title>Review report &mdash; {_esc(filename)}</title>")
    out.append("<style>" + _STYLE + "</style>")
    out.append("</head><body>")

    out.append(
        '<div class="toolbar no-print">'
        '<button onclick="window.print()">Print / Save as PDF</button>'
        "</div>"
    )

    # header
    out.append('<header class="rep-head">')
    out.append(f'<div class="brand">{_esc(BRAND)} &middot; Contract Review Report</div>')
    out.append(f"<h1>{_esc(filename)}</h1>")
    out.append(
        '<div class="meta">'
        f"Contract ID {_esc(contract_id)} &middot; {_esc(contract_type)} &middot; "
        f"Parties: {_esc(parties)} &middot; Generated {_esc(generated)}"
        "</div>"
    )
    out.append("</header>")

    # risk banner
    out.append(f'<section class="risk risk-{_esc(level)}">')
    out.append(f'<div class="risk-tier">{_esc(level.upper())} RISK</div>')
    out.append(f'<div class="risk-score">Risk score {_esc(score_txt)}</div>')
    if why:
        out.append(f'<div class="risk-why">{_esc(why)}</div>')
    out.append("</section>")

    # count tiles: by severity, then by inspector
    out.append('<section class="tiles"><div class="tiles-label">Findings by severity</div><div class="tile-row">')
    out.append(_tile(sev["high"], "Serious", "high"))
    out.append(_tile(sev["medium"], "Worth a look", "med"))
    out.append(_tile(sev["low"], "Minor", "low"))
    out.append("</div></section>")

    out.append('<section class="tiles"><div class="tiles-label">Findings by check</div><div class="tile-row">')
    for key in ("compliance", "risk", "template", "financial"):
        out.append(_tile(ins[key], INSPECTOR_LABELS[key], "neutral"))
    out.append("</div></section>")

    # executive summary
    executive = summary.get("executive")
    if executive:
        out.append('<section class="block">')
        out.append("<h2>Executive summary</h2>")
        out.append(f'<p class="exec">{_esc(executive)}</p>')
        out.append("</section>")

    # clause-level findings
    out.append('<section class="block">')
    out.append(f"<h2>Clause-level findings ({len(flagged)} flagged of {len(clauses)} clauses)</h2>")
    if not flagged:
        out.append('<p class="quiet">No clause was flagged. Nothing needed a change.</p>')
    for c in flagged:
        heading = c.get("heading") or c.get("clause_type") or "Clause"
        number = f"{c.get('number')}. " if c.get("number") else ""
        out.append('<div class="clause">')
        out.append(f"<h3>{_esc(number)}{_esc(heading)}</h3>")
        for f in c.get("findings") or []:
            out.append('<div class="finding">')
            out.append(_finding_block(f))
            out.append("</div>")
        proposal = c.get("proposal") or {}
        if proposal.get("new_text"):
            out.append(
                '<div class="proposal"><b>Suggested replacement wording</b>'
                f'<div class="ptext">{_esc(proposal["new_text"])}</div></div>'
            )
        out.append(_decision_line(c))
        out.append("</div>")
    out.append("</section>")

    # missing standard clauses
    if missing:
        out.append('<section class="block">')
        out.append(f"<h2>Standard clauses missing from this contract ({len(missing)})</h2>")
        for m in missing:
            out.append('<div class="clause">')
            out.append(f'<div class="plain">{_esc(m.get("plain") or "A standard clause is missing.")}</div>')
            if m.get("term"):
                out.append(f'<div class="term">{_esc(m.get("term"))}</div>')
            if m.get("why_needed"):
                out.append(f'<div class="evidence">{_esc(m.get("why_needed"))}</div>')
            out.append("</div>")
        out.append("</section>")

    # recommendations / negotiation points
    if points:
        out.append('<section class="block">')
        out.append(f"<h2>Recommendations and negotiation points ({len(points)})</h2>")
        for p in points:
            out.append('<div class="point">')
            if p.get("ask"):
                out.append(f'<div class="ask"><b>Ask for</b>{_esc(p.get("ask"))}</div>')
            if p.get("fallback"):
                out.append(f'<div class="fallback"><b>Middle ground</b>{_esc(p.get("fallback"))}</div>')
            if p.get("walk_away"):
                out.append(f'<div class="walk"><b>Line we will not cross</b>{_esc(p.get("walk_away"))}</div>')
            out.append("</div>")
        out.append("</section>")

    out.append(
        '<footer class="rep-foot">'
        f"Generated by {_esc(BRAND)} on {_esc(generated)}. "
        "Every figure above is taken from this contract's stored review. "
        "This report is a decision aid, not legal advice."
        "</footer>"
    )

    out.append("</body></html>")
    return "".join(out)


_STYLE = """
  * { box-sizing: border-box; }
  body {
    font-family: Georgia, 'Times New Roman', serif;
    color: #2a2318; background: #eae6db;
    max-width: 820px; margin: 0 auto; padding: 32px 28px 64px;
    line-height: 1.55; font-size: 15px;
  }
  h1 { font-size: 26px; margin: 4px 0 6px; }
  h2 { font-size: 18px; margin: 0 0 12px; border-bottom: 2px solid rgba(122,113,95,0.25); padding-bottom: 6px; }
  h3 { font-size: 14px; margin: 0 0 8px; }
  .toolbar { text-align: right; margin-bottom: 18px; }
  .toolbar button {
    font-family: inherit; font-size: 13px; font-weight: bold;
    padding: 9px 18px; border: none; border-radius: 8px;
    background: #395b64; color: #fff; cursor: pointer;
  }
  .rep-head { margin-bottom: 22px; }
  .brand { font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: #78705f; }
  .meta { font-size: 12.5px; color: #78705f; }
  .risk {
    border-radius: 12px; padding: 18px 22px; margin: 0 0 22px;
    border-left: 6px solid #78705f;
  }
  .risk-tier { font-size: 20px; font-weight: bold; letter-spacing: 0.04em; }
  .risk-score { font-size: 14px; margin-top: 2px; }
  .risk-why { font-size: 13.5px; color: #4a4636; margin-top: 6px; }
  .risk-high { background: rgba(139,74,46,0.12); border-left-color: #8b4a2e; }
  .risk-high .risk-tier { color: #8b4a2e; }
  .risk-medium { background: rgba(217,179,108,0.20); border-left-color: #8a6a1b; }
  .risk-medium .risk-tier { color: #8a6a1b; }
  .risk-low { background: rgba(122,139,93,0.20); border-left-color: #4a5530; }
  .risk-low .risk-tier { color: #4a5530; }
  .risk-unknown { background: rgba(122,113,95,0.12); }
  .tiles { margin-bottom: 18px; }
  .tiles-label { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: #78705f; margin-bottom: 8px; }
  .tile-row { display: flex; gap: 12px; flex-wrap: wrap; }
  .tile {
    flex: 1; min-width: 120px; background: #f1ede3; border-radius: 10px;
    padding: 14px 16px; border: 1px solid rgba(122,113,95,0.18);
  }
  .tile-num { font-size: 28px; font-weight: bold; line-height: 1; }
  .tile-label { font-size: 12px; color: #78705f; margin-top: 4px; }
  .tile-high .tile-num { color: #8b4a2e; }
  .tile-med .tile-num { color: #8a6a1b; }
  .tile-low .tile-num { color: #4a5530; }
  .tile-neutral .tile-num { color: #395b64; }
  .block { margin-bottom: 26px; }
  .exec { font-size: 14.5px; }
  .quiet { color: #78705f; }
  .clause {
    background: #f1ede3; border-radius: 10px; padding: 16px 18px;
    margin-bottom: 14px; border: 1px solid rgba(122,113,95,0.18);
    page-break-inside: avoid;
  }
  .finding { margin-bottom: 14px; }
  .plain { font-weight: bold; font-size: 15px; margin-bottom: 3px; }
  .term { font-size: 12.5px; color: #78705f; margin-bottom: 8px; }
  .trio { display: grid; gap: 8px; margin: 8px 0; }
  .trio > div { font-size: 13px; padding: 9px 12px; border-radius: 7px; }
  .trio b { display: block; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #78705f; margin-bottom: 3px; }
  .wrong { background: rgba(139,74,46,0.10); }
  .change { background: rgba(57,91,100,0.10); }
  .ignore { background: rgba(217,179,108,0.18); }
  .evidence { font-size: 12.5px; font-style: italic; color: #4a4636; margin-top: 6px; }
  .fmeta { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: #78705f; margin-top: 6px; }
  .proposal { margin-top: 10px; }
  .proposal b { display: block; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #78705f; margin-bottom: 4px; }
  .ptext { background: #fff; border-radius: 8px; padding: 12px 14px; font-size: 13.5px; }
  .decision { font-size: 12.5px; margin-top: 10px; padding: 8px 12px; border-radius: 7px; }
  .decision.acc { background: rgba(122,139,93,0.20); color: #4a5530; }
  .decision.rej { background: rgba(57,91,100,0.10); color: #4a4636; }
  .decision.open { background: rgba(217,179,108,0.14); color: #8a6a1b; }
  .point { background: #f1ede3; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; border: 1px solid rgba(122,113,95,0.18); page-break-inside: avoid; }
  .point > div { font-size: 13px; margin-bottom: 6px; }
  .point b { display: block; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #78705f; margin-bottom: 2px; }
  .rep-foot { font-size: 11.5px; color: #78705f; border-top: 1px solid rgba(122,113,95,0.25); padding-top: 12px; margin-top: 12px; }
  @media print {
    body { background: #fff; max-width: none; padding: 0; }
    .no-print { display: none; }
    .tile, .clause, .point { background: #f7f5ef; }
  }
"""
