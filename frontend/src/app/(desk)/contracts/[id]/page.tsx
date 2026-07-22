"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { STAGE_LINES } from "@/lib/stages";

type Finding = {
  finding_id?: string;
  clause_id?: string;
  inspector?: string;
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
};

type Detail = {
  contract_id: string;
  filename: string;
  status: string;
  stage?: string;
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
      (c.findings ?? []).map(
        (f) => CHECK_NAMES[f.inspector ?? ""] ?? "a check",
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
    // scroll the matching card into the middle of the right pane
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
    return (
      <main className="py-9">
        {back}
        <h1 className="text-[24px] font-bold mt-4">{s.filename}</h1>
        <div className="flex items-center gap-2.5 mt-6 text-[var(--ink-soft)]">
          <i className="pulse" />
          {STAGE_LINES[s.stage ?? ""] ?? "Working on it…"}
        </div>
        <p className="text-[13px] text-[var(--ink-soft)] mt-3">
          This page checks for the finished review every few seconds. You can go
          back to the docket; nothing is lost.
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
        <div className="label mb-2">Final redlined document</div>
        <pre className="doc max-w-[80ch]">{doc}</pre>
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

      {(s.summary?.executive || s.contract_risk?.why) && (
        <div className="story">
          {s.summary?.executive ?? s.contract_risk?.why}
        </div>
      )}
      {failed.length > 0 && (
        <div className="attn-note mb-4">
          {failed.map((k) => CHECK_NAMES[k]).join(" and ")} did not finish on
          this contract. The findings below come from the checks that did. Treat
          the gap as unreviewed, not as clean.
        </div>
      )}
      {note && <p className="text-[13px] text-[var(--rust)] mb-3">{note}</p>}

      <div className="grid grid-cols-2 gap-6 items-start">
        {/* left: their version */}
        <div className="panel p-7 min-h-[70vh]">
          <div className="flex justify-between items-baseline mb-5 pb-3 border-b border-[var(--line)]">
            <h2 className="text-[16px] font-bold">Their version</h2>
            <span className="label">Original, as received</span>
          </div>
          {clauses.map((c) => {
            const sev = worstSeverity(c);
            const cls = [
              "clause",
              sev ? `flagged sev-${sev}` : "",
              c.decision ? "decided" : "",
              sel === c.clause_id ? "sel" : "",
            ].join(" ");
            return (
              <div
                key={c.clause_id}
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
            );
          })}
        </div>

        {/* right: your redline. NO panel class on purpose: the proposal
            cards inside are each raised, and a raised box holding raised
            cards reads as mud. */}
        <div className="pt-7 min-h-[70vh]">
          <div className="flex justify-between items-baseline mb-5 pb-3 border-b border-[var(--line)]">
            <h2 className="text-[16px] font-bold">Your redline</h2>
            <span className="label">Papyrus proposals, you decide</span>
          </div>

          {(s.missing_clauses ?? []).length > 0 && (
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
          )}

          {clauses.map((c) => {
            const sev = worstSeverity(c);
            if (!sev) {
              return (
                <div key={c.clause_id} className="rl">
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
                key={c.clause_id}
                id={`rl-${c.clause_id}`}
                className={`rl ${sel === c.clause_id ? "sel" : ""}`}
              >
                <div className="rl-head" onClick={() => select(c.clause_id)}>
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
                          onClick={() =>
                            decide(c.clause_id, "edited", editText)
                          }
                        >
                          Use my wording
                        </button>
                      </div>
                    )}

                    {c.decision === "accepted" && (
                      <div className="verdict acc">
                        In your redline. The corrected wording replaces theirs
                        in the final document.
                      </div>
                    )}
                    {c.decision === "rejected" && (
                      <div className="verdict rej">
                        Their original wording stays. Papyrus records that you
                        saw the flag and chose to keep it.
                      </div>
                    )}
                    {c.decision === "edited" && (
                      <div className="verdict acc">
                        Your wording goes into the final document: "
                        {c.final_text}"
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <AuditTrail id={id} />
    </main>
  );
}
