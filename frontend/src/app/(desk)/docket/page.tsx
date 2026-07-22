"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { STAGE_LINES } from "@/lib/stages";

const API_BASE = "http://localhost:8000"; // same base as lib/api.ts

type Row = {
  contract_id: string;
  filename: string;
  status: string;
  stage: string | null;
  risk_level: string | null;
  flagged: number;
  decided: number;
  created_at: string | null;
};

function riskView(level: string | null): { text: string; cls: string } | null {
  const l = (level ?? "").toLowerCase();
  if (l === "high") return { text: "High risk", cls: "text-[var(--rust)]" };
  if (l === "medium")
    return { text: "Medium risk", cls: "text-[var(--amber)]" };
  if (l === "low") return { text: "Low risk", cls: "text-[var(--olive)]" };
  return null;
}

export default function Docket() {
  const router = useRouter();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const load = () =>
      api("/contracts")
        .then(setRows)
        .catch((e) => setError(String(e)));
    load();
    const i = setInterval(load, 4000);
    return () => clearInterval(i);
  }, []);

  async function upload(file: File) {
    setNote(`Uploading ${file.name}…`);
    const fd = new FormData();
    fd.append("file", file, file.name);
    try {
      const res = await fetch(`${API_BASE}/contracts`, {
        method: "POST",
        credentials: "include",
        body: fd, // no Content-Type header: the browser writes the multipart boundary itself
      });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      setNote("Contract received. Papyrus is reading it now.");
    } catch (e) {
      setNote(`Upload failed: ${String(e)}`);
    }
    if (fileRef.current) fileRef.current.value = "";
  }

  if (error) return <main className="py-9 text-[var(--rust)]">{error}</main>;

  return (
    <main className="pb-16">
      <div
        className="flex items-end justify-between mt-11 mb-2 rise"
        style={{ "--i": 0 } as React.CSSProperties}
      >
        <div>
          <h1 className="text-[34px] font-bold">The Docket</h1>
          <p className="text-[var(--ink-soft)] mt-1.5 max-w-[52ch]">
            Drop a contract in. Papyrus reads it, flags what could hurt you, and
            drafts the fix. Nothing leaves this desk without your sign-off.
          </p>
        </div>
        <label className="panel click block text-center min-w-[290px] px-7 py-5">
          <b
            className="text-[var(--accent-deep)]"
            style={{ fontFamily: "var(--font-cabinet)" }}
          >
            Upload a contract
          </b>
          <small className="block text-[var(--ink-soft)] text-[12.5px] mt-1">
            Word or PDF. It never leaves your desk.
          </small>
          <input
            ref={fileRef}
            type="file"
            accept=".docx,.pdf"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
          />
        </label>
      </div>

      {note && (
        <p className="text-[13px] text-[var(--accent-deep)] mb-2">{note}</p>
      )}
      <div className="label mt-6">Contracts under review</div>

      {!rows ? (
        <p className="py-6 text-[var(--ink-soft)]">Loading the docket…</p>
      ) : rows.length === 0 ? (
        <p className="py-6 text-[var(--ink-soft)]">
          Nothing here yet. Upload a contract to start.
        </p>
      ) : (
        <div className="mt-4">
          {rows.map((r, i) => (
            <DocketRow
              key={r.contract_id}
              r={r}
              i={i}
              onOpen={() => router.push(`/contracts/${r.contract_id}`)}
            />
          ))}
        </div>
      )}
    </main>
  );
}

function DocketRow({
  r,
  i,
  onOpen,
}: {
  r: Row;
  i: number;
  onOpen: () => void;
}) {
  const grid =
    "card-row grid grid-cols-[2.2fr_1fr_1.6fr_1fr_auto] gap-4 items-center rise";
  const style = { "--i": i } as React.CSSProperties;
  const when = r.created_at ? new Date(r.created_at).toLocaleString() : "";
  const name = (sub: string) => (
    <span>
      <b
        className="block text-[16px]"
        style={{ fontFamily: "var(--font-cabinet)" }}
      >
        {r.filename}
      </b>
      <small className="block text-[var(--ink-soft)] text-[12.5px] mt-0.5">
        {sub}
      </small>
    </span>
  );

  if (r.status === "processing") {
    return (
      <div className={grid} style={style}>
        {name(`Received ${when}`)}
        <span className="badge working">Working</span>
        <span className="flex items-center gap-2.5 text-[13.5px] text-[var(--ink-soft)]">
          <i className="pulse" />
          {STAGE_LINES[r.stage ?? ""] ?? "Working on it…"}
        </span>
        <span />
        <span />
      </div>
    );
  }

  if (r.status === "extraction_failed") {
    return (
      <div className={`${grid} grid-rows-[auto_auto]`} style={style}>
        {name("Upload could not be read")}
        <span className="badge attn">Needs a person</span>
        <span className="text-[13.5px] text-[var(--ink-soft)]">
          Could not read the text
        </span>
        <span />
        <span />
        <div className="attn-note -mt-1.5">
          We could not pull readable text out of this file, so nothing was
          reviewed. Ask for the original Word or PDF file, or open the document
          yourself.
        </div>
      </div>
    );
  }

  if (r.status === "needs_review") {
    const remaining = Math.max(0, (r.flagged ?? 0) - (r.decided ?? 0));
    const risk = riskView(r.risk_level);
    return (
      <div className={`${grid} click`} style={style} onClick={onOpen}>
        {name(`Finished reading · received ${when}`)}
        <span className="badge review">Needs your review</span>
        <span className="text-[13.5px] text-[var(--ink-soft)]">
          {remaining === 0
            ? "All decided. Open to finish the review."
            : `${remaining} clause${remaining === 1 ? "" : "s"} need${remaining === 1 ? "s" : ""} a decision`}
        </span>
        <span
          className={`text-[13.5px] font-semibold ${risk?.cls ?? "text-[var(--ink-soft)]"}`}
        >
          {risk?.text ?? ""}
        </span>
        <span
          className="text-[13px] font-bold text-[var(--accent)]"
          style={{ fontFamily: "var(--font-cabinet)" }}
        >
          Open review →
        </span>
      </div>
    );
  }

  if (r.status === "reviewed") {
    const risk = riskView(r.risk_level);
    return (
      <div className={`${grid} click`} style={style} onClick={onOpen}>
        {name(`Reviewed · received ${when}`)}
        <span className="badge done">Signed off</span>
        <span className="text-[13.5px] text-[var(--ink-soft)]">
          {r.flagged ?? 0} flagged clause{(r.flagged ?? 0) === 1 ? "" : "s"}{" "}
          decided
        </span>
        <span
          className={`text-[13.5px] font-semibold ${risk?.cls ?? "text-[var(--ink-soft)]"}`}
        >
          {risk?.text ?? ""}
        </span>
        <span
          className="text-[13px] font-bold text-[var(--accent)]"
          style={{ fontFamily: "var(--font-cabinet)" }}
        >
          Open report →
        </span>
      </div>
    );
  }

  // status "error", or anything unexpected: fail loudly, never blankly
  return (
    <div className={`${grid} grid-rows-[auto_auto]`} style={style}>
      {name(`Received ${when}`)}
      <span className="badge err">Error</span>
      <span className="text-[13.5px] text-[var(--ink-soft)]">
        The pipeline hit a wall
      </span>
      <span />
      <span />
      <div className="attn-note -mt-1.5">
        Something went wrong while reviewing this contract. Check the backend
        logs, then upload it again.
      </div>
    </div>
  );
}
