"use client";
import { useEffect, useState } from "react";
import { api } from "./api";

export type User = {
  id: string;
  email: string;
  role: "lawyer" | "admin";
};

export function useUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api("/users/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);
  return { user, loading };
}

export async function login(identifier: string, password: string) {
  // login-flex accepts an email or a username in the same field
  const res = await fetch("http://localhost:8000/auth/login-flex", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: identifier, password }),
  });
  if (!res.ok) throw new Error("Wrong email/username or password");
}

export async function logout() {
  await api("/auth/logout", { method: "POST" });
}
