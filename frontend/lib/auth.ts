import type { Officer } from "@/types/api";

const STORAGE_KEY = "veriflow.session.v1";

/** Fired on the window whenever the stored session is written or cleared. */
export const SESSION_EVENT = "veriflow:session";

export interface StoredSession {
  token: string;
  officer: Officer;
}

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function decodeExpiry(token: string): number | null {
  try {
    const segment = token.split(".")[1];
    if (!segment) return null;
    const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(
      base64.length + ((4 - (base64.length % 4)) % 4),
      "=",
    );
    const payload = JSON.parse(atob(padded)) as { exp?: unknown };
    return typeof payload.exp === "number" ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

export function tokenExpired(token: string, skewMs = 30_000): boolean {
  const expiresAt = decodeExpiry(token);
  return expiresAt === null || expiresAt - skewMs <= Date.now();
}

export function readSession(): StoredSession | null {
  if (!isBrowser()) return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredSession>;
    if (
      typeof parsed.token !== "string" ||
      !parsed.officer ||
      typeof parsed.officer.email !== "string"
    ) {
      return null;
    }
    return { token: parsed.token, officer: parsed.officer };
  } catch {
    return null;
  }
}

export function writeSession(session: StoredSession): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  window.dispatchEvent(new Event(SESSION_EVENT));
}

export function clearSession(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event(SESSION_EVENT));
}

export function getToken(): string | null {
  return readSession()?.token ?? null;
}
