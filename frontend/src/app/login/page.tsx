"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { EyeIcon } from "@/lib/icons";
import { login } from "@/lib/useUser";

function PasswordField({
  value,
  onChange,
  autoComplete,
}: {
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="flex items-center border-b border-[var(--line)] focus-within:border-[var(--accent)] mb-6">
      <input
        type={show ? "text" : "password"}
        required
        minLength={8}
        value={value}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-transparent outline-none py-2"
      />
      <button
        type="button"
        aria-label={show ? "Hide password" : "Show password"}
        onClick={() => setShow(!show)}
        className="text-[var(--ink-soft)] hover:text-[var(--ink)] px-1"
      >
        <EyeIcon off={show} />
      </button>
    </div>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // one-time setup: shown only while the system has zero accounts
  const [needsSetup, setNeedsSetup] = useState(false);
  const [setupEmail, setSetupEmail] = useState("");
  const [setupUsername, setSetupUsername] = useState("");

  useEffect(() => {
    api("/auth/needs-setup")
      .then((r) => setNeedsSetup(!!r.needs_setup))
      .catch(() => {});
  }, []);

  async function afterLogin() {
    // admins land on their dashboard, lawyers on the docket
    try {
      const me = await api("/users/me");
      router.push(me.role === "admin" ? "/admin" : "/docket");
    } catch {
      router.push("/docket");
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(identifier, password);
      await afterLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function setup(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/auth/bootstrap", {
        method: "POST",
        body: JSON.stringify({ email: setupEmail, username: setupUsername, password }),
      });
      await login(setupEmail, password);
      router.push("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-[100dvh] bg-[var(--parchment)] text-[var(--ink)] flex items-center justify-center px-4">
      <form onSubmit={needsSetup ? setup : submit} className="panel w-full max-w-sm px-9 py-10">
        <div className="mb-8">
          <div className="text-[24px] font-extrabold" style={{ fontFamily: "var(--font-cabinet)" }}>
            PAPYRUS<span className="text-[var(--accent)]">.</span>
          </div>
          <h1 className="text-2xl font-bold mt-3">{needsSetup ? "First-time setup" : "Sign in"}</h1>
          <p className="text-sm text-[var(--ink-soft)] mt-1">
            {needsSetup
              ? "No accounts exist yet. Create the founding administrator; this screen never appears again."
              : "The contract review desk. No signup here: the admin creates every account."}
          </p>
        </div>

        {needsSetup ? (
          <>
            <label className="label block mb-1">Email</label>
            <input
              type="email"
              required
              value={setupEmail}
              onChange={(e) => setSetupEmail(e.target.value)}
              className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--accent)] outline-none py-2 mb-5"
            />
            <label className="label block mb-1">Username</label>
            <input
              required
              minLength={3}
              value={setupUsername}
              onChange={(e) => setSetupUsername(e.target.value)}
              className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--accent)] outline-none py-2 mb-5"
            />
          </>
        ) : (
          <>
            <label className="label block mb-1">Email or username</label>
            <input
              required
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              autoComplete="username"
              className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--accent)] outline-none py-2 mb-5"
            />
          </>
        )}
        <label className="label block mb-1">Password</label>
        <PasswordField value={password} onChange={setPassword} autoComplete={needsSetup ? "new-password" : "current-password"} />

        {error && <p className="text-sm text-[var(--rust)] mb-4">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="bg-[var(--accent)] hover:bg-[var(--accent-deep)] text-white font-semibold text-sm px-6 py-2.5 rounded-[7px] active:scale-[0.98] transition disabled:opacity-50"
        >
          {busy ? "One moment" : needsSetup ? "Create administrator" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
