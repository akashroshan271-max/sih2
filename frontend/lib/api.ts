import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import { clearSession, getToken } from "@/lib/auth";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const http = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 45_000,
  headers: { Accept: "application/json" },
});

// Every request carries the officer's session token. The token lives in one
// place (lib/auth) so sign-in, sign-out and the 401 handler stay consistent.
http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

interface ErrorPayload {
  detail?: string;
  code?: string;
  context?: Record<string, unknown>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly context: Record<string, unknown>;

  constructor(
    message: string,
    options: { status: number; code: string; context?: Record<string, unknown> },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.context = options.context ?? {};
  }
}

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ErrorPayload>) => {
    if (error.code === "ECONNABORTED") {
      return Promise.reject(
        new ApiError("The API took too long to respond.", {
          status: 0,
          code: "timeout",
        }),
      );
    }

    const status = error.response?.status ?? 0;
    const payload = error.response?.data;
    const isLoginAttempt = error.config?.url?.includes("/auth/login") ?? false;

    if (status === 401 && !isLoginAttempt && typeof window !== "undefined") {
      clearSession();
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }

    const fallback =
      status === 0
        ? "Cannot reach the VERIFLOW API. Confirm the backend is running on port 8000."
        : "The request was rejected by the API.";

    return Promise.reject(
      new ApiError(payload?.detail ?? fallback, {
        status,
        code: payload?.code ?? "request_failed",
        context: payload?.context,
      }),
    );
  },
);

export async function getJson<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  const { data } = await http.get<T>(path, { params });
  return data;
}

export async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await http.post<T>(path, body);
  return data;
}

/** Multipart upload; the browser sets the boundary, so never set Content-Type. */
export async function postForm<T>(path: string, form: FormData): Promise<T> {
  const { data } = await http.post<T>(path, form);
  return data;
}
