"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { API_BASE_URL, ROLE_META, homeForRole } from "@/lib/constants";
import { cn } from "@/lib/utils";

const OVERSIGHT_NAV = [
  { href: "/dashboard", label: "Command centre" },
  { href: "/dashboard#pipeline", label: "Pipeline" },
  { href: "/dashboard#escalations", label: "Escalations" },
  { href: "/dashboard#lease-watch", label: "Lease watch" },
  { href: "/workspace", label: "Oversight desk" },
] as const;

const DESK_NAV = [{ href: "/workspace", label: "My desk" }] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const { officer, status, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper">
        <div className="text-center" role="status">
          <p className="font-serif text-2xl tracking-tight text-ink">VERIFLOW</p>
          <p className="mt-2 text-xs text-ink-soft">Validating your session…</p>
        </div>
      </div>
    );
  }

  if (!officer) {
    return null;
  }

  const meta = ROLE_META[officer.role];
  const home = homeForRole(officer.role);
  const nav = officer.role === "regional_officer" ? OVERSIGHT_NAV : DESK_NAV;

  async function handleSignOut() {
    await logout();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:border focus:border-teal focus:bg-panel focus:px-3 focus:py-2 focus:text-sm"
      >
        Skip to content
      </a>

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[240px] flex-col border-r border-ink/10 bg-ink text-panel lg:flex">
        <div className="px-6 pt-7">
          <Link href={home} className="block focus-visible:outline-none">
            <span className="font-serif text-[1.65rem] font-medium leading-none tracking-tight">
              VERIFLOW
            </span>
            <span className="mt-2 block text-2xs leading-relaxed text-panel/55">
              AICTE approval operations
              <br />
              APH 2024–27
            </span>
          </Link>

          <p className="mt-6 border-t border-panel/10 pt-4 text-2xs uppercase tracking-[0.16em] text-panel/40">
            {meta.phase}
          </p>

          <nav className="mt-3" aria-label="Sections">
            <ul className="space-y-0.5">
              {nav.map((item) => {
                const base = item.href.split("#")[0];
                const active =
                  !item.href.includes("#") &&
                  (pathname === base || pathname.startsWith(`${base}/`));
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "relative block px-3 py-2 text-[13px] transition-colors",
                        active
                          ? "bg-panel/10 font-medium text-panel"
                          : "text-panel/65 hover:bg-panel/[0.06] hover:text-panel",
                      )}
                    >
                      {active && (
                        <span
                          aria-hidden
                          className="absolute inset-y-1.5 left-0 w-[2px] bg-panel/70"
                        />
                      )}
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        </div>

        <div className="mt-auto space-y-4 border-t border-panel/10 px-6 py-5">
          <div>
            <p className="text-[13px] font-medium leading-snug text-panel">
              {officer.full_name}
            </p>
            <p className="mt-0.5 text-2xs leading-snug text-panel/50">
              {officer.designation}
            </p>
            <p className="mt-1 break-all text-2xs text-panel/35">
              {officer.email}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void handleSignOut()}
            className="inline-flex items-center gap-1.5 text-2xs text-panel/60 underline-offset-4 hover:text-panel hover:underline"
          >
            <LogOut aria-hidden className="h-3 w-3" />
            Sign out
          </button>
          <a
            href={`${API_BASE_URL}/docs`}
            target="_blank"
            rel="noreferrer"
            className="block text-2xs text-panel/45 underline-offset-4 hover:text-panel hover:underline"
          >
            API reference
          </a>
          <p className="text-2xs text-panel/25">Demo dataset · build 0.4</p>
        </div>
      </aside>

      <header className="sticky top-0 z-20 border-b border-ink/10 bg-ink text-panel lg:hidden">
        <div className="flex items-baseline justify-between gap-3 px-5 py-3">
          <div>
            <Link href={home} className="font-serif text-xl tracking-tight">
              VERIFLOW
            </Link>
            <p className="text-2xs text-panel/45">{meta.short} desk</p>
          </div>
          <button
            type="button"
            onClick={() => void handleSignOut()}
            className="inline-flex items-center gap-1.5 text-2xs text-panel/65"
          >
            <LogOut aria-hidden className="h-3 w-3" />
            Sign out
          </button>
        </div>
        <nav aria-label="Sections" className="overflow-x-auto">
          <ul className="flex gap-1 px-3 pb-2">
            {nav.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="block whitespace-nowrap px-3 py-1.5 text-xs text-panel/70 hover:bg-panel/10 hover:text-panel"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main id="main" className="lg:pl-[240px]">
        <div className="mx-auto max-w-[1480px] px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
          {children}
        </div>
      </main>
    </div>
  );
}
