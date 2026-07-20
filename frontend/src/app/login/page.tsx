"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { login, register } from "@/lib/useUser";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "signup") await register(email, password);
      else await login(email, password);
      const me = await api("/users/me");
      router.push(me.role === "customer" ? "/" : "/workspace");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-[100dvh] bg-[var(--paper)] text-[var(--ink)] flex items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm border-t-2 border-[var(--ink)] pt-8">
        <div className="mb-8">
          <div className="w-10 h-10 bg-[var(--ox)] text-[var(--paper)] flex items-center justify-center text-xl rounded-[3px] mb-3">
            雲
          </div>
          <h1 className="text-2xl font-bold">{mode === "signin" ? "Sign in" : "Create your account"}</h1>
          <p className="text-sm text-[var(--mut)] mt-1">
            {mode === "signin" ? "Nimbus support desk" : "Track your requests in one place"}
          </p>
        </div>

        <label className="block text-[11px] tracking-widest uppercase text-[var(--mut)] mb-1">Email</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--ox)] outline-none py-2 mb-5"
        />
        <label className="block text-[11px] tracking-widest uppercase text-[var(--mut)] mb-1">Password</label>
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--ox)] outline-none py-2 mb-6"
        />

        {error && <p className="text-sm text-[var(--rust)] mb-4">{error}</p>}

        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={busy}
            className="bg-[var(--ox)] hover:bg-[var(--ox-2)] text-[var(--paper)] font-semibold text-sm px-6 py-2.5 rounded-[3px] active:scale-[0.98] transition disabled:opacity-50"
          >
            {busy ? "One moment" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
          <button
            type="button"
            onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
            className="text-sm text-[var(--ox)] underline underline-offset-4"
          >
            {mode === "signin" ? "New here? Create an account" : "Have an account? Sign in"}
          </button>
        </div>
      </form>
    </main>
  );
}
