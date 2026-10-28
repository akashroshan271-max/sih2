"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Loader2, LockKeyhole } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { ApiError, getJson } from "@/lib/api";
import { ROLE_META, homeForRole } from "@/lib/constants";
import type { DemoAccountList, OfficerRole } from "@/types/api";

const PHASES: { role: OfficerRole; note: string }[] = [
  {
    role: "scrutiny_officer",
    note: "Lease, land and evidence verified before a file can move",
  },
  {
    role: "evc_member",
    note: "Expert visit recorded on site",
  },
  {
    role: "sac_member",
    note: "Standing committee decides the approval",
  },
  {
    role: "shc_member",
    note: "Hearing and decision on the record",
  },
];

export function LoginView() {
  const router = useRouter();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const demo = useQuery({
    queryKey: ["auth", "demo-accounts"],
    queryFn: () => getJson<DemoAccountList>("/auth/demo-accounts"),
    staleTime: Infinity,
    retry: 0,
  });

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const officer = await login(email, password);
      router.replace(homeForRole(officer.role));
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : "Sign-in failed. Confirm the VERIFLOW API is running.",
      );
    } finally {
      setPending(false);
    }
  }

  function applyDemoAccount(account: DemoAccountList["accounts"][number]) {
    setEmail(account.email);
    setPassword(account.password ?? demo.data?.shared_password ?? "");
    setError(null);
  }

  return (
    <div className="min-h-screen bg-paper lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,560px)]">
      {/* --- Left: the statutory ledger ---------------------------------- */}
      <aside className="relative overflow-hidden bg-ink px-6 py-10 text-panel sm:px-10 lg:px-14 lg:py-14">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 right-0 w-px bg-panel/10"
        />
        <div className="mx-auto max-w-xl">
          <p className="font-mono text-2xs uppercase tracking-[0.3em] text-panel/45">
            AICTE · approval process handbook 2024–27
          </p>
          <h1 className="mt-4 font-serif text-[2.75rem] leading-none tracking-tight sm:text-5xl">
            VERIFLOW
          </h1>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-panel/65">
            Verification flow for AICTE approvals. Every docket is a statutory
            file; every move is signed.
          </p>

          <ol className="mt-10 space-y-0 border-l border-panel/15 pl-6">
            {PHASES.map((phase, index) => {
              const meta = ROLE_META[phase.role];
              return (
                <li key={phase.role} className="relative pb-6 last:pb-0">
                  <span
                    aria-hidden
                    className="absolute -left-[27px] top-1.5 h-2 w-2 bg-panel/70"
                  />
                  <p className="font-mono text-2xs tracking-[0.16em] text-panel/45">
                    PHASE {String(index + 1).padStart(2, "0")}
                  </p>
                  <p className="mt-1 text-[15px] font-medium text-panel">
                    {meta.desk}
                  </p>
                  <p className="mt-0.5 text-xs leading-relaxed text-panel/50">
                    {phase.note}
                  </p>
                </li>
              );
            })}
            <li className="relative">
              <span
                aria-hidden
                className="absolute -left-[27px] top-1.5 h-2 w-2 border border-panel/60"
              />
              <p className="font-mono text-2xs tracking-[0.16em] text-panel/45">
                OVERSIGHT
              </p>
              <p className="mt-1 text-[15px] font-medium text-panel">
                Regional office
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-panel/50">
                Sees every desk, watches the SLA clock, verifies the audit chain
              </p>
            </li>
          </ol>

          <div className="mt-10 border-t border-panel/10 pt-5">
            <p className="text-xs leading-relaxed text-panel/50">
              AI reads lease deeds and surfaces gaps. It never approves,
              rejects or advances a docket — those are officer decisions under
              the Handbook, recorded in a tamper-evident audit chain.
            </p>
          </div>
        </div>
      </aside>

      {/* --- Right: sign-in ---------------------------------------------- */}
      <main className="flex min-h-screen items-start justify-center px-5 py-10 sm:px-10 lg:items-center lg:py-14">
        <div className="w-full max-w-md">
          <p className="font-mono text-2xs uppercase tracking-[0.22em] text-ink-faint">
            Officer sign-in
          </p>
          <h2 className="mt-2 font-serif text-[1.9rem] leading-tight text-ink">
            Your desk, your docket queue
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-soft">
            Each phase officer signs in separately and sees only the files
            waiting at their stage.
          </p>

          <form onSubmit={onSubmit} className="mt-7 space-y-4">
            <div>
              <label htmlFor="email" className="text-xs font-medium text-ink">
                Official email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="scrutiny.officer@aicte.gov.in"
                className="mt-1.5 w-full border border-rule bg-panel px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-teal focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="password" className="text-xs font-medium text-ink">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••••"
                className="mt-1.5 w-full border border-rule bg-panel px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-teal focus:outline-none"
              />
            </div>

            {error ? (
              <div
                role="alert"
                className="border border-seal/30 bg-seal-soft/70 px-3 py-2 text-xs leading-relaxed text-ink"
              >
                {error}
              </div>
            ) : null}

            <Button type="submit" disabled={pending} className="w-full">
              {pending ? (
                <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
              ) : (
                <LockKeyhole aria-hidden className="h-3.5 w-3.5" />
              )}
              {pending ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          <section className="mt-8 border-t border-rule pt-5" aria-labelledby="demo-heading">
            <div className="flex items-baseline justify-between gap-3">
              <h3
                id="demo-heading"
                className="text-xs font-medium uppercase tracking-wide text-ink-soft"
              >
                Demo officers
              </h3>
              {demo.data?.shared_password ? (
                <p className="font-mono text-2xs text-ink-faint">
                  password {demo.data.shared_password}
                </p>
              ) : null}
            </div>

            {demo.isPending ? (
              <p className="mt-3 text-xs text-ink-soft">Loading the roster…</p>
            ) : null}

            {demo.error ? (
              <p className="mt-3 text-xs leading-relaxed text-ink-soft">
                The officer roster could not be loaded. Start the API on port
                8000 and reload.
              </p>
            ) : null}

            <ul className="mt-3 divide-y divide-rule border border-rule bg-panel">
              {demo.data?.accounts.map((account) => {
                const meta = ROLE_META[account.role];
                return (
                  <li key={account.id}>
                    <button
                      type="button"
                      onClick={() => applyDemoAccount(account)}
                      className="group flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition-colors hover:bg-ink/[0.03]"
                    >
                      <span className="min-w-0">
                        <span className="block text-[13px] font-medium text-ink">
                          {account.full_name}
                          <span className="ml-2 font-mono text-2xs font-normal uppercase tracking-wide text-ink-faint">
                            {meta.short}
                          </span>
                        </span>
                        <span className="mt-0.5 block truncate text-2xs text-ink-soft">
                          {account.email}
                        </span>
                      </span>
                      <ArrowRight
                        aria-hidden
                        className="h-3.5 w-3.5 shrink-0 text-ink-faint transition-colors group-hover:text-teal"
                      />
                      <span className="sr-only">
                        Use the {meta.desk} demo account
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>

            {demo.data?.notice ? (
              <p className="mt-2 text-2xs leading-relaxed text-ink-faint">
                {demo.data.notice}
              </p>
            ) : null}
          </section>

          <p className="mt-6 text-2xs leading-relaxed text-ink-faint">
            Sessions are signed tokens valid for the configured shift. Sign out
            on a shared terminal.
          </p>
        </div>
      </main>
    </div>
  );
}
