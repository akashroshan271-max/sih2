"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { getJson, postJson } from "@/lib/api";
import {
  SESSION_EVENT,
  clearSession,
  readSession,
  tokenExpired,
  writeSession,
} from "@/lib/auth";
import type { LoginResponse, Officer } from "@/types/api";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  officer: Officer | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<Officer>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [officer, setOfficer] = useState<Officer | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let cancelled = false;

    async function hydrate() {
      const session = readSession();
      if (!session || tokenExpired(session.token)) {
        if (session) clearSession();
        if (!cancelled) {
          setOfficer(null);
          setStatus("anonymous");
        }
        return;
      }

      try {
        const fresh = await getJson<Officer>("/auth/me");
        if (cancelled) return;
        writeSession({ token: session.token, officer: fresh });
        setOfficer(fresh);
        setStatus("authenticated");
      } catch {
        if (cancelled) return;
        clearSession();
        setOfficer(null);
        setStatus("anonymous");
      }
    }

    void hydrate();

    function sync() {
      const session = readSession();
      setOfficer(session?.officer ?? null);
      setStatus(session ? "authenticated" : "anonymous");
    }

    window.addEventListener(SESSION_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      cancelled = true;
      window.removeEventListener(SESSION_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await postJson<LoginResponse>("/auth/login", {
      email: email.trim(),
      password,
    });
    writeSession({ token: response.access_token, officer: response.officer });
    setOfficer(response.officer);
    setStatus("authenticated");
    return response.officer;
  }, []);

  const logout = useCallback(async () => {
    try {
      await postJson("/auth/logout");
    } catch {
      // A dead session is still a signed-out session.
    }
    clearSession();
    setOfficer(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ officer, status, login, logout }),
    [officer, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used inside <AuthProvider>.");
  }
  return context;
}
