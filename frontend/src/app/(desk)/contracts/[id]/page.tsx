"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, BASE } from "@/lib/api";
import { STAGE_LINES, STAGE_ORDER } from "@/lib/stages";

type Finding = {
  finding_id?: string;
  clause_id?: string;
  inspector?: string;
  also_caught_by?: string[];
  severity?: string;
  plain?: string;
  term?: string;
  wrong?: string;
  change?: string;
  ignore?: string;
  evidence?: string;
};

type Proposal = {
  clause_id?: string;
  new_text?: string;
  del_span?: string;
  ins_span?: string;
  based_on?: string[];
};

type Clause = {
  clause_id: string;
  number?: string;
  heading?: string;
  text: string;
  clause_type?: string;
  findings?: Finding[];
  proposal?: Proposal | null;
  decision?: "accepted" | "rejected" | "edited" | null;
  final_text?: string;
  escalated?: { reason: string; by: string } | null;
  concession_ask?: { ask: string; by: string } | null;
};

type Detail = {
  contract_id: string;
  filename: string;
  status: string;
  stage?: string;
  source_format?: string;
  clauses?: Clause[];
  missing_clauses?: Finding[];
  inspector_reports?: { inspector: string; status: string; note?: string }[];
  contract_risk?: { level?: string; score?: number; why?: string };
  summary?: { executive?: string; counts?: Record<string, number> };
  error?: string | null;
};

const CHECK_NAMES: Record<string, string> = {
  compliance: "the legal-standards check",
  risk: "the risk check",
  template: "the comparison against your standard template",
  financial: "the money-terms check",
};

function worstSeverity(c: Clause): string | null {
  const sevs = (c.findings ?? []).map((f) => f.severity ?? "");
  if (sevs.includes("high")) return "high";
  if (sevs.includes("medium")) return "med";
  if (sevs.length > 0) return "low";
  return null;
}

function caughtBy(c: Clause): string {
  const names = [
    ...new Set(
      (c.findings ?? []).flatMap((f) =>
        [f.inspector ?? "", ...(f.also_caught_by ?? [])].map(
          (i) => CHECK_NAMES[i] ?? "a check",
        ),
      ),
    ),
  ];
  return `Caught by ${names.join(" and ")}.`;
}

function Diff({ c }: { c: Clause }) {
  const p = c.proposal;
  if (!p) return null;
  const del = p.del_span ?? "";
  const idx = del ? c.text.indexOf(del) : -1;
  if (idx < 0) {
    // the exact span was not found in the clause text: show the swap side by side
    return (
      <div className="diff">
        <del>{del || c.text}</del> <ins>{p.ins_span ?? p.new_text ?? ""}</ins>
      </div>
    );
  }
  return (
    <div className="diff">
      {c.text.slice(0, idx)}
      <del>{del}</del> <ins>{p.ins_span ?? ""}</ins>
      {c.text.slice(idx + del.length)}
    </div>
  );
}

type Audit = {
  entries: { step: string; prev: string; hash: string }[];
  count: number;
  intact: boolean;
  broken_at: number | null;
};

// the trail is long and nobody reads it every visit, so it stays shut and
// only fetches when asked. The verdict line is the point: a lawyer needs to
// be able to show this review was not quietly edited after it was signed.
function AuditTrail({ id }: { id: string }) {
  const [open, setOpen] = useState(false);
  const [a, setA] = useState<Audit | null>(null);
  const [err, setErr] = useState("");

  function toggle() {
    setOpen((o) => !o);
    if (!a && !err)
      api(`/contracts/${id}/audit`)
        .then(setA)
        .catch((e) => setErr(String(e)));
  }

  return (
    <div className="mt-10">
      <button
        onClick={toggle}
        className="text-[13px] font-semibold text-[var(--accent)] underline underline-offset-4"
      >
        {open ? "Hide the audit trail" : "Show the audit trail"}
      </button>
      {open && (
        <div className="panel p-6 mt-3 max-w-[80ch]">
          {err && <p className="text-[var(--rust)] text-[13px]">{err}</p>}
          {!a && !err && (
            <p className="text-[var(--ink-soft)] text-[13px]">Loading…</p>
          )}
          {a && (
            <>
              <div
                className={`text-[13px] font-semibold mb-4 ${a.intact ? "text-[var(--olive)]" : "text-[var(--rust)]"}`}
              >
                {a.intact
                  ? `Verified intact · ${a.count} step${a.count === 1 ? "" : "s"}, each one hash-linked to the one before it.`
                  : `Tampered. Entry ${a.broken_at} no longer follows from the one before it; treat everything after it as unreliable.`}
              </div>
              <ol className="text-[13px]">
                {a.entries.map((e, i) => (
                  <li
                    key={i}
                    className={`flex gap-3 py-1.5 border-b border-[var(--line)] last:border-0 ${
                      a.broken_at !== null && i >= a.broken_at
                        ? "text-[var(--rust)]"
                        : ""
                    }`}
                  >
                    <span className="font-array text-[11px] text-[var(--ink-soft)] w-6 shrink-0 pt-0.5">
                      {i + 1}
                    </span>
                    <span className="flex-1">{e.step}</span>
                    <span
                      className="font-array text-[11px] text-[var(--ink-soft)] shrink-0 pt-0.5"
                      title={e.hash}
                    >
                      {e.hash.slice(0, 8)}
                    </span>
                  </li>
                ))}
              </ol>
            </>
          )}
        </div>
      )}
    </div>
  );
}

const INSPECTOR_LABELS: Record<string, string> = {
  compliance: "Compliance",
  risk: "Risk",
  template: "Standard-terms",
  financial: "Financial",
};

const SEV_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };

// The risk rail (layout B): everything a lawyer judges the contract by, in one
// sticky column sorted top-down by how much it matters: tier and score, then
// severity counts, then per-check counts, then the worst findings. Every number
// is read straight from the stored assessment, so it can never claim more than
// the review actually found.
function RiskRail({ s, onReport }: { s: Detail; onReport: () => void }) {
  const clauses = s.clauses ?? [];
  const missing = s.missing_clauses ?? [];
  const findings = clauses.flatMap((c) => c.findings ?? []);
  // missing clauses carry a severity + inspector too; the backend rollup counts
  // them, so the rail counts them as well or the tier would disagree.
  const all: Finding[] = [...findings, ...missing];
  const sevCount = (x: string) => all.filter((f) => f.severity === x).length;
  const insCount = (x: string) => all.filter((f) => f.inspector === x).length;

  const level = (s.contract_risk?.level ?? "unknown").toLowerCase();
  const score = s.contract_risk?.score;
  const why = s.contract_risk?.why ?? "";

  const headingOf: Record<string, string> = {};
  clauses.forEach((c) => {
    headingOf[c.clause_id] = c.heading ?? c.clause_type ?? c.clause_id;
  });
  const top = [...findings]
    .sort(
      (a, b) =>
        (SEV_RANK[a.severity ?? "low"] ?? 3) -
        (SEV_RANK[b.severity ?? "low"] ?? 3),
    )
    .slice(0, 3);

  const tierColor =
    level === "high"
      ? "var(--rust)"
      : level === "medium"
        ? "var(--amber)"
        : level === "low"
          ? "var(--olive)"
          : "var(--ink-soft)";
  const tierBg =
    level === "high"
      ? "var(--rust-wash)"
      : level === "medium"
        ? "var(--amber-wash)"
        : level === "low"
          ? "var(--olive-wash)"
          : "var(--accent-wash)";

  const sevRows: [string, string, string][] = [
    ["high", "Serious", "var(--rust)"],
    ["medium", "Worth a look", "var(--amber)"],
    ["low", "Minor", "var(--olive)"],
  ];

  // checks sorted biggest first; a zero stays visible but fades back
  const checks = (["compliance", "risk", "template", "financial"] as const)
    .map((k) => ({ k, n: insCount(k) }))
    .sort((a, b) => b.n - a.n);
  const maxCheck = Math.max(1, ...checks.map((c) => c.n));

  return (
    <aside className="rail panel">
      <div className="text-center pt-2">
        <span className="badge" style={{ background: tierBg, color: tierColor }}>
          {level} risk
        </span>
        {typeof score === "number" ? (
          <>
            <div
              className="font-array text-[42px] leading-none mt-4"
              style={{ color: tierColor }}
            >
              {score}
            </div>
            <div className="text-[12px] text-[var(--ink-soft)] mt-1">
              out of 100
            </div>
            <div className="meter mt-3">
              <i style={{ width: `${score}%`, background: tierColor }} />
            </div>
          </>
        ) : (
          <div className="text-[13px] text-[var(--ink-soft)] mt-3">
            not scored
          </div>
        )}
        {why && (
          <div className="text-[12px] text-[var(--ink-soft)] mt-2.5">{why}</div>
        )}
      </div>

      <div className="rail-sec">
        <div className="label mb-1.5">By severity</div>
        {sevRows.map(([key, text, color]) => (
          <div key={key} className="srow">
            <span
              className="font-array text-[10px] tracking-[0.12em] uppercase"
              style={{ color }}
            >
              {text}
            </span>
            <b className="font-array text-[16px]" style={{ color }}>
              {sevCount(key)}
            </b>
          </div>
        ))}
      </div>

      <div className="rail-sec">
        <div className="label mb-1.5">By check</div>
        {checks.map(({ k, n }) => (
          <div key={k} className={`srow ${n === 0 ? "opacity-40" : ""}`}>
            <span className="text-[13px]">{INSPECTOR_LABELS[k]}</span>
            <span className="sbar">
              <i style={{ width: `${(n / maxCheck) * 100}%` }} />
            </span>
            <b className="font-array text-[16px] text-[var(--accent)]">{n}</b>
          </div>
        ))}
      </div>

      {top.length > 0 && (
        <div className="rail-sec">
          <div className="label mb-1">Most serious findings</div>
          {top.map((f, i) => (
            <div key={f.finding_id ?? i} className="rail-find">
              <span
                className={`fmark ${f.severity === "high" ? "high" : f.severity === "medium" ? "med" : "low"}`}
                style={{ float: "none", display: "block", margin: "0 0 2px" }}
              >
                {f.severity === "high"
                  ? "Serious"
                  : f.severity === "medium"
                    ? "Worth a look"
                    : "Minor"}
              </span>
              <b>{headingOf[f.clause_id ?? ""] ?? f.clause_id}</b> · {f.plain}
            </div>
          ))}
        </div>
      )}

      <button
        className="finish ready w-full"
        onClick={onReport}
        title="Open a printable review report you can save as PDF"
      >
        Review report
      </button>
    </aside>
  );
}

export default function Review() {
  const { id } = useParams<{ id: string }>();
  const [s, setS] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [finalDoc, setFinalDoc] = useState<string | null>(null);

  const load = useCallback(() => {
    api(`/contracts/${id}`)
      .then(setS)
      .catch((e) => setError(String(e)));
  }, [id]);

  useEffect(load, [load]);

  // keep polling only while the pipeline is still working on this contract
  useEffect(() => {
    if (s?.status !== "processing") return;
    const i = setInterval(load, 4000);
    return () => clearInterval(i);
  }, [s?.status, load]);

  function select(cid: string) {
    setSel(cid);
    // scroll the matching card into the middle of the pane
    setTimeout(() => {
      document
        .getElementById(`rl-${cid}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
  }

  async function decide(cid: string, verdict: string, editedText?: string) {
    setBusy(true);
    setNote("");
    try {
      await api(`/contracts/${id}/clauses/${cid}/decision`, {
        method: "POST",
        body: JSON.stringify({ verdict, edited_text: editedText ?? null }),
      });
      setEditing(null);
      load();
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function askCounsel(cid: string) {
    setBusy(true);
    setNote("Asking counsel. This wakes the model, so give it a minute or two.");
    try {
      await api(`/contracts/${id}/clauses/${cid}/counsel`, { method: "POST" });
      setNote("");
      load();
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function downloadDocx() {
    setNote("");
    try {
      const res = await fetch(`${BASE}/contracts/${id}/export`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      const missed = res.headers.get("X-Unmatched-Clauses");
      if (missed)
        setNote(
          `Could not place the edit for ${missed} into the file; fix those clauses by hand.`,
        );
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `reviewed-${s?.filename ?? id}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setNote(String(e));
    }
  }

  async function openReport() {
    // fetch the report with the auth cookie (same pattern as the .docx export),
    // then open the returned HTML page in a new tab so the lawyer can read it
    // and use the browser's Print dialog to save it as PDF.
    setNote("");
    try {
      const res = await fetch(`${BASE}/contracts/${id}/report`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      const url = URL.createObjectURL(await res.blob());
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) {
      setNote(String(e));
    }
  }

  async function finish() {
    setBusy(true);
    setNote("");
    try {
      const r = await api(`/contracts/${id}/finish`, { method: "POST" });
      setFinalDoc(r.document);
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <main className="py-9 text-[var(--rust)]">{error}</main>;
  if (!s) return <main className="py-9 text-[var(--ink-soft)]">Loading…</main>;

  const back = (
    <Link
      href="/docket"
      className="text-[13px] font-semibold text-[var(--accent)]"
    >
      ← Docket
    </Link>
  );

  if (s.status === "processing") {
    const idx = Math.max(0, STAGE_ORDER.indexOf(s.stage ?? "reading"));
    const pct = ((idx + 1) / STAGE_ORDER.length) * 100;
    return (
      <main className="py-9">
        {back}
        <h1 className="text-[24px] font-bold mt-4">{s.filename}</h1>

        <div className="flex items-center gap-3.5 mt-6">
          <div className="pbar" style={{ width: 280 }}>
            <i style={{ width: `${pct}%` }} />
          </div>
          <span className="font-array text-[11.5px] text-[var(--ink-soft)]">
            STEP {idx + 1} OF {STAGE_ORDER.length}
          </span>
        </div>
        <div className="flex items-center gap-2.5 mt-3 text-[var(--ink-soft)]">
          <i className="pulse" />
          {STAGE_LINES[s.stage ?? ""] ?? "Working on it…"}
        </div>

        {/* a ghost of the review that is coming: two shimmering panes */}
        <div className="grid grid-cols-2 gap-6 items-start mt-8">
          {[0, 1].map((col) => (
            <div key={col} className="panel p-7">
              <div className="skel h-4 w-1/3 mb-6" />
              {[...Array(4)].map((_, i) => (
                <div key={i} className="mb-7">
                  <div className="skel h-3.5 w-1/2 mb-2.5" />
                  <div className="skel h-3 w-full mb-1.5" />
                  <div className="skel h-3 w-full mb-1.5" />
                  <div className="skel h-3 w-2/3" />
                </div>
              ))}
            </div>
          ))}
        </div>

        <p className="text-[13px] text-[var(--ink-soft)] mt-4">
          This page checks for the finished review every few seconds and will
          flip to the full redline on its own.
        </p>
      </main>
    );
  }

  if (s.status === "extraction_failed" || s.status === "error") {
    return (
      <main className="py-9">
        {back}
        <h1 className="text-[24px] font-bold mt-4">{s.filename}</h1>
        <div className="attn-note mt-6 max-w-[70ch]">
          {s.error ||
            "We could not pull readable text out of this file, so nothing was reviewed. Ask for the original Word or PDF file."}
        </div>
      </main>
    );
  }

  const clauses = s.clauses ?? [];
  const flagged = clauses.filter((c) => (c.findings ?? []).length > 0);
  const decidedCount = flagged.filter((c) => c.decision).length;
  const allDecided = decidedCount === flagged.length;

  // finished (just now, or on an earlier visit): show the assembled document
  if (finalDoc !== null || s.status === "reviewed") {
    const doc =
      finalDoc ??
      clauses
        .map((c) => {
          const head = [c.number ? `${c.number}.` : "", c.heading ?? ""]
            .filter(Boolean)
            .join(" ");
          return `${head}\n${c.final_text || c.text}`.trim();
        })
        .join("\n\n");
    return (
      <main className="py-9 pb-16">
        {back}
        <h1 className="text-[24px] font-bold mt-4 mb-4">{s.filename}</h1>
        <div className="story max-w-[80ch]">
          Review complete. The document below is their contract with your
          decisions applied. This review is filed as precedent, so future
          contracts get compared against it.
        </div>
        <div className="shell mt-6">
          <RiskRail s={s} onReport={openReport} />
          <div>
            <div className="label mb-2">Final redlined document</div>
            <pre className="doc">{doc}</pre>
            <div className="flex gap-3 mt-4">
              {s.source_format === "docx" && (
                <button className="finish ready" onClick={downloadDocx}>
                  Download corrected .docx
                </button>
              )}
              <button className="finish ready" onClick={openReport}>
                Review report
              </button>
            </div>
            {note && <div className="story mt-2">{note}</div>}
          </div>
        </div>
        <AuditTrail id={id} />
      </main>
    );
  }

  // a check with no "ok" report counts as failed, fan_in's own default
  const okChecks = new Set(
    (s.inspector_reports ?? [])
      .filter((r) => r.status === "ok")
      .map((r) => r.inspector),
  );
  const failed = Object.keys(CHECK_NAMES).filter((k) => !okChecks.has(k));

  // the right-hand cell for one clause: the quiet line for a clean clause,
  // or the full proposal card for a flagged one
  function redlineCell(c: Clause) {
    const sev = worstSeverity(c);
    if (!sev) {
      return (
        <div className="rl">
          <div className="rl-quiet">
            {c.number ? `${c.number}. ` : ""}
            {c.heading ?? "Clause"}: looks standard, no change proposed.
          </div>
        </div>
      );
    }
    const stateLabel =
      c.decision === "accepted"
        ? "Accepted"
        : c.decision === "rejected"
          ? "Kept as-is"
          : c.decision === "edited"
            ? "Your wording"
            : "Your call";
    const stateCls =
      c.decision === "accepted"
        ? "acc"
        : c.decision === "rejected"
          ? "rej"
          : c.decision === "edited"
            ? "edit"
            : "open";
    return (
      <div
        id={`rl-${c.clause_id}`}
        className={`rl ${sel === c.clause_id ? "sel" : ""}`}
      >
        <div
          className="rl-head"
          onClick={() =>
            sel === c.clause_id ? setSel(null) : select(c.clause_id)
          }
        >
          <h3>
            {c.number ? `${c.number}. ` : ""}
            {c.heading ?? "Clause"}
          </h3>
          <span className={`rl-state ${stateCls}`}>{stateLabel}</span>
        </div>
        {sel === c.clause_id && (
          <div className="rl-inner">
            {(c.findings ?? []).map((f, fi) => (
              <div key={f.finding_id ?? fi} className="mb-3.5">
                <div className="plainline">{f.plain}</div>
                <div className="termline">{f.term}</div>
                <div className="trio">
                  <div className="wrong">
                    <b>What is wrong</b>
                    {f.wrong}
                  </div>
                  <div className="change">
                    <b>What we would change it to</b>
                    {f.change}
                  </div>
                  <div className="ignore">
                    <b>If you ignore it</b>
                    {f.ignore}
                  </div>
                </div>
              </div>
            ))}
            <Diff c={c} />
            <div className="who">{caughtBy(c)}</div>

            {c.escalated && (
              <div className="mt-2 text-[12.5px]">
                <b>Escalated to senior counsel</b> by {c.escalated.by}. {c.escalated.reason}
              </div>
            )}
            {c.concession_ask && (
              <div className="mt-1 text-[12.5px]">
                <b>Ask recorded:</b> {c.concession_ask.ask}
              </div>
            )}

            {!c.decision && editing !== c.clause_id && (
              <div className="flex gap-2">
                {c.proposal?.new_text && (
                  <button
                    className="act act-acc"
                    disabled={busy}
                    onClick={() => decide(c.clause_id, "accepted")}
                  >
                    Accept fix
                  </button>
                )}
                <button
                  className="act act-rej"
                  disabled={busy}
                  onClick={() => decide(c.clause_id, "rejected")}
                >
                  Keep their wording
                </button>
                <button
                  className="act act-edit"
                  disabled={busy}
                  onClick={() => {
                    setEditing(c.clause_id);
                    setEditText(c.proposal?.new_text ?? c.text);
                  }}
                >
                  Edit
                </button>
                {c.findings?.length && !c.escalated ? (
                  <button
                    className="act act-edit"
                    disabled={busy}
                    onClick={() => askCounsel(c.clause_id)}
                  >
                    Ask counsel
                  </button>
                ) : null}
              </div>
            )}

            {!c.decision && editing === c.clause_id && (
              <div className="mt-2.5">
                <textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  className="field w-full min-h-[110px] p-3 text-[13.5px]"
                />
                <button
                  className="act act-acc mt-2"
                  disabled={busy || !editText.trim()}
                  onClick={() => decide(c.clause_id, "edited", editText)}
                >
                  Use my wording
                </button>
              </div>
            )}

            {c.decision === "accepted" && (
              <div className="verdict acc">
                In your redline. The corrected wording replaces theirs in the
                final document.
              </div>
            )}
            {c.decision === "rejected" && (
              <div className="verdict rej">
                Their original wording stays. Papyrus records that you saw the
                flag and chose to keep it.
              </div>
            )}
            {c.decision === "edited" && (
              <div className="verdict acc">
                Your wording goes into the final document: "{c.final_text}"
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <main className="py-7 pb-16">
      <div className="flex items-center gap-5 mb-4">
        {back}
        <h1 className="text-[24px] font-bold">{s.filename}</h1>
        <div className="ml-auto flex items-center gap-3.5">
          <div className="pbar">
            <i
              style={{
                width: `${flagged.length ? (decidedCount / flagged.length) * 100 : 100}%`,
              }}
            />
          </div>
          <span className="font-array text-[11.5px] text-[var(--ink-soft)]">
            {decidedCount} OF {flagged.length} DECIDED
          </span>
          <button
            className={`finish ${allDecided ? "ready" : ""}`}
            disabled={busy}
            onClick={() =>
              allDecided
                ? finish()
                : setNote("Decide every flagged clause first.")
            }
          >
            Finish review
          </button>
        </div>
      </div>

      {note && <p className="text-[13px] text-[var(--rust)] mb-3">{note}</p>}

      <div className="shell">
        <RiskRail s={s} onReport={openReport} />

        <div>
          {(s.summary?.executive || s.contract_risk?.why) && (
            <div className="story">
              {s.summary?.executive ?? s.contract_risk?.why}
            </div>
          )}
          {failed.length > 0 && (
            <div className="attn-note mb-4">
              {failed.map((k) => CHECK_NAMES[k]).join(" and ")} did not finish
              on this contract. The findings below come from the checks that
              did. Treat the gap as unreviewed, not as clean.
            </div>
          )}

          <div className="ledger-head">
            <div>
              <h2 className="text-[16px] font-bold">Their version</h2>
              <span className="label">Original, as received</span>
            </div>
            <div>
              <h2 className="text-[16px] font-bold">Your redline</h2>
              <span className="label">Papyrus proposals, you decide</span>
            </div>
          </div>

          {(s.missing_clauses ?? []).length > 0 && (
            <div className="clause-row">
              <div className="not-present">Not present in their document.</div>
              <div className="rl">
                <div className="rl-head">
                  <h3>Missing from this contract</h3>
                </div>
                <div className="rl-inner">
                  {(s.missing_clauses ?? []).map((m, i) => (
                    <div key={i} className="mb-3">
                      <div className="plainline">
                        {m.plain ?? "A standard clause is missing."}
                      </div>
                      <div className="termline">{m.term ?? ""}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {clauses.map((c) => {
            const sev = worstSeverity(c);
            const cls = [
              "clause",
              sev ? `flagged sev-${sev}` : "",
              c.decision ? "decided" : "",
              sel === c.clause_id ? "sel" : "",
            ].join(" ");
            return (
              <div key={c.clause_id} className="clause-row">
                <div
                  className={cls}
                  onClick={sev ? () => select(c.clause_id) : undefined}
                >
                  <h3>
                    {c.number ? `${c.number}. ` : ""}
                    {c.heading ?? c.clause_type ?? "Clause"}
                    {sev && (
                      <span className={`fmark ${c.decision ? "low" : sev}`}>
                        {c.decision
                          ? "Decided"
                          : sev === "high"
                            ? "Serious"
                            : sev === "med"
                              ? "Worth a look"
                              : "Minor"}
                      </span>
                    )}
                  </h3>
                  <p>{c.text}</p>
                </div>
                {redlineCell(c)}
              </div>
            );
          })}
        </div>
      </div>
      <AuditTrail id={id} />
    </main>
  );
}
