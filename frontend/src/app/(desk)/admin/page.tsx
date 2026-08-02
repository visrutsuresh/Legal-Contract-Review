"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { EyeIcon } from "@/lib/icons";
import { useUser } from "@/lib/useUser";

type Person = { id: string; email: string; username: string | null; role: string; is_active: boolean };

export default function People() {
  const { user, loading } = useUser();
  const [people, setPeople] = useState<Person[] | null>(null);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [role, setRole] = useState("lawyer");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [formOpen, setFormOpen] = useState(false);

  const load = useCallback(() => {
    api("/users")
      .then(setPeople)
      .catch((e) => setNote(String(e)));
  }, []);

  useEffect(() => {
    if (user?.role === "admin") load();
  }, [user, load]);

  async function createAccount(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote("");
    try {
      await api("/users", {
        method: "POST",
        body: JSON.stringify({ email, username: username || null, password, role }),
      });
      setNote(`${role === "admin" ? "Administrator" : "Lawyer"} account created for ${email}.`);
      setEmail("");
      setUsername("");
      setPassword("");
      setFormOpen(false);
      load();
    } catch (err) {
      setNote(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function patch(p: Person, body: Record<string, unknown>, doneNote = "") {
    setBusy(true);
    setNote("");
    try {
      await api(`/users/${p.id}`, { method: "PATCH", body: JSON.stringify(body) });
      if (doneNote) setNote(doneNote);
      load();
    } catch (err) {
      setNote(String(err));
    } finally {
      setBusy(false);
    }
  }

  function resetPassword(p: Person) {
    const pw = window.prompt(`New password for ${p.email} (at least 8 characters):`);
    if (pw === null) return;
    if (pw.length < 8) {
      setNote("Password needs at least 8 characters.");
      return;
    }
    patch(p, { password: pw }, `Password updated for ${p.email}.`);
  }

  function setUsernameFor(p: Person) {
    const name = window.prompt(`Username for ${p.email} (they can sign in with it instead of the email):`, p.username ?? "");
    if (name === null) return;
    patch(p, { username: name.trim() || null }, name.trim() ? `Username set to ${name.trim().toLowerCase()}.` : "Username cleared.");
  }

  if (loading) return <main className="py-9" />;
  if (!user || user.role !== "admin") {
    return <main className="py-9 text-[var(--ink-soft)]">Only the admin can manage people.</main>;
  }
  return (
    <main className="py-9 pb-16 w-full">
      <div className="flex items-center justify-between rise" style={{ "--i": 0 } as React.CSSProperties}>
        <h1 className="text-[28px] font-bold">People</h1>
        <button onClick={() => setFormOpen(true)} className="act act-acc">
          Add account
        </button>
      </div>
      <p className="text-[var(--ink-soft)] mt-1.5 mb-7">
        Every account on this desk. There is no open signup: you create lawyers and other administrators here.
      </p>

      {formOpen && (
        <div
          className="fixed inset-0 z-50 bg-[var(--ink)]/20 flex items-center justify-center px-4"
          onClick={() => setFormOpen(false)}
        >
          <form
            onSubmit={createAccount}
            onClick={(e) => e.stopPropagation()}
            className="panel w-full max-w-sm p-8 shadow-[12px_12px_28px_rgba(0,0,0,0.14),-10px_-10px_24px_rgba(255,255,255,0.85)]"
          >
            <h2 className="text-[19px] font-bold mb-6">New account</h2>
            <label className="label block mb-1">Email</label>
            <input
              type="email"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--accent)] outline-none py-2 mb-5"
            />
            <label className="label block mb-1">Username</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="optional, signs in with it instead of the email"
              className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--accent)] outline-none py-2 mb-5"
            />
            <label className="label block mb-1">Password</label>
            <div className="flex items-center border-b border-[var(--line)] focus-within:border-[var(--accent)] mb-5">
              <input
                type={showPw ? "text" : "password"}
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-transparent outline-none py-2"
              />
              <button
                type="button"
                aria-label={showPw ? "Hide password" : "Show password"}
                onClick={() => setShowPw(!showPw)}
                className="text-[var(--ink-soft)] hover:text-[var(--ink)] px-1"
              >
                <EyeIcon off={showPw} />
              </button>
            </div>
            <label className="label block mb-1">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full bg-transparent border-b border-[var(--line)] outline-none py-2 mb-7"
            >
              <option value="lawyer">lawyer</option>
              <option value="admin">admin</option>
            </select>
            <div className="flex gap-3">
              <button type="submit" disabled={busy} className="act act-acc">
                Create account
              </button>
              <button type="button" onClick={() => setFormOpen(false)} className="act">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {note && <p className="text-[13px] text-[var(--accent-deep)] mb-4">{note}</p>}

      {!people ? (
        <p className="text-[var(--ink-soft)]">Loading…</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {people.map((p, i) => (
            <div key={p.id} className="panel p-5 rise" style={{ "--i": i + 1 } as React.CSSProperties}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-semibold text-[16px] truncate">
                  {p.username ?? p.email.split("@")[0]}
                </span>
                <span
                  className={`font-array text-[10.5px] px-1.5 py-0.5 rounded ${
                    p.role === "admin" ? "bg-[var(--accent)] text-white" : "bg-[var(--line)] text-[var(--ink-soft)]"
                  }`}
                >
                  {p.role.toUpperCase()}
                </span>
              </div>
              <div className="text-[12.5px] text-[var(--ink-soft)] mt-1 truncate">{p.email}</div>
              <div className="text-[12.5px] mt-0.5">
                <span className="font-array text-[10.5px] text-[var(--ink-soft)]">SIGN-IN: </span>
                {p.username ? `${p.username} or email` : "email only"}
              </div>
              <div
                className={`font-array text-[11px] mt-2 ${p.is_active ? "text-[var(--olive)]" : "text-[var(--rust)]"}`}
              >
                {p.is_active ? "ACTIVE" : "DEACTIVATED"}
                {p.id === user.id && " · YOU"}
              </div>
              <div className="flex flex-wrap gap-2 mt-4">
                <button className="act" disabled={busy} onClick={() => resetPassword(p)}>
                  Reset password
                </button>
                <button className="act" disabled={busy} onClick={() => setUsernameFor(p)}>
                  {p.username ? "Edit username" : "Set username"}
                </button>
                {p.is_active
                  ? p.id !== user.id && (
                      <button className="act act-rej" disabled={busy} onClick={() => patch(p, { is_active: false })}>
                        Deactivate
                      </button>
                    )
                  : (
                      <button className="act act-acc" disabled={busy} onClick={() => patch(p, { is_active: true })}>
                        Reactivate
                      </button>
                    )}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
