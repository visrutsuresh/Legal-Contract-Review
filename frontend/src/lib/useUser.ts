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

export async function login(email: string, password: string) {
  const res = await fetch("http://localhost:8000/auth/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  });
  if (!res.ok) throw new Error("Wrong email or password");
}

export async function logout() {
  await api("/auth/logout", { method: "POST" });
}
