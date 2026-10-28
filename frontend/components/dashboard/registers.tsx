"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { DataError, EmptyNote } from "@/components/ui/data-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { SkeletonLines } from "@/components/ui/skeleton";
import { LEASE_CODE_LABEL, SLA_LEVEL_META } from "@/lib/constants";
import { useLeaseWarnings, useSlaAlerts } from "@/lib/queries/use-dashboard";
import { cn, formatNumber } from "@/lib/utils";

const VISIBLE_ROWS = 6;

export function EscalationRegister({ id }: { id?: string }) {
  const { data, error, refetch } = useSlaAlerts();

  const levels = data
    ? (["L1", "L2", "L3"] as const)
        .filter((level) => (data.levels[level] ?? 0) > 0)
        .map((level) => `${level} ${data.levels[level]}`)
        .join(" · ")
    : "";

  const meta = data
    ? `${data.total} past the limit${levels ? ` · ${levels}` : ""}`
    : undefined;

  const items = data?.items.slice(0, VISIBLE_ROWS) ?? [];
  const hidden = data ? Math.max(0, data.total - items.length) : 0;

  return (
    <section id={id} aria-labelledby="escalations-heading" className="scroll-mt-24">
      <SectionHeading id="escalations-heading" title="Escalations" meta={meta} />

      {error && !data ? (
        <DataError className="mt-3" error={error} onRetry={() => void refetch()} compact />
      ) : null}

      {!error && !data ? (
        <div className="mt-4 space-y-3 px-1">
          <SkeletonLines lines={5} />
        </div>
      ) : null}

      {data && items.length === 0 ? (
        <EmptyNote
          className="mt-3"
          title="No dockets past the stage limit"
          hint="The hourly sweep escalates past-limit dockets to L1, then L2 and L3."
        />
      ) : null}

      {items.length > 0 ? (
        <ol className="mt-3 divide-y divide-rule border border-rule bg-panel">
          {items.map((alert) => (
            <li key={alert.application_id}>
              <Link
                href={`/dashboard/applications/${alert.application_id}`}
                className="flex items-start justify-between gap-3 px-3 py-2.5 transition-colors hover:bg-ink/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal focus-visible:ring-inset"
              >
                <div className="flex min-w-0 items-start gap-2.5">
                  <Badge tone={SLA_LEVEL_META[alert.level].tone}>
                    {SLA_LEVEL_META[alert.level].label}
                  </Badge>
                  <div className="min-w-0">
                    <p className="truncate text-[13px] leading-tight text-ink">
                      {alert.institution_name}
                    </p>
                    <p className="mt-0.5 truncate font-mono text-2xs text-ink-faint">
                      {alert.application_number} · {alert.state}
                    </p>
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <p
                    className={cn(
                      "text-xs font-medium tabular",
                      alert.severity === "critical" ? "text-seal" : "text-[#8a5f0c]",
                    )}
                  >
                    {Math.floor(alert.dwell_days)} days
                  </p>
                  <p className="mt-0.5 text-2xs text-ink-faint">
                    {SLA_LEVEL_META[alert.level].owner}
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ol>
      ) : null}

      {hidden > 0 ? (
        <p className="mt-1.5 text-2xs text-ink-faint">
          {formatNumber(hidden)} more dockets past the limit.
        </p>
      ) : null}
    </section>
  );
}

export function LeaseRegister({ id }: { id?: string }) {
  const { data, error, refetch } = useLeaseWarnings();

  const items = data?.items.slice(0, VISIBLE_ROWS) ?? [];
  const hidden = data ? Math.max(0, data.total - items.length) : 0;

  return (
    <section id={id} aria-labelledby="lease-heading" className="scroll-mt-24">
      <SectionHeading
        id="lease-heading"
        title="Lease watch"
        meta={data ? `${formatNumber(data.total)} failing Rule 1` : undefined}
      />

      {error && !data ? (
        <DataError className="mt-3" error={error} onRetry={() => void refetch()} compact />
      ) : null}

      {!error && !data ? (
        <div className="mt-4 space-y-3 px-1">
          <SkeletonLines lines={5} />
        </div>
      ) : null}

      {data && items.length === 0 ? (
        <EmptyNote
          className="mt-3"
          title="Every lease deed satisfies the live-lease rule"
          hint="Remaining lease is at least the maximum course duration for each docket."
        />
      ) : null}

      {items.length > 0 ? (
        <ol className="mt-3 divide-y divide-rule border border-rule bg-panel">
          {items.map((warning) => (
            <li key={`${warning.application_id}-${warning.code}`}>
              <Link
                href={`/dashboard/applications/${warning.application_id}`}
                className="flex items-start justify-between gap-3 px-3 py-2.5 transition-colors hover:bg-ink/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal focus-visible:ring-inset"
              >
                <div className="min-w-0">
                  <p className="truncate text-[13px] leading-tight text-ink">
                    {warning.institution_name}
                  </p>
                  <p className="mt-0.5 truncate text-2xs text-seal">
                    {LEASE_CODE_LABEL[warning.code] ?? warning.code}
                  </p>
                  <p className="mt-0.5 truncate font-mono text-2xs text-ink-faint">
                    {warning.application_number} · {warning.state}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-xs font-medium tabular text-seal">
                    {warning.remaining_lease_years === null
                      ? "No dates"
                      : `${warning.remaining_lease_years.toFixed(1)} yr`}
                  </p>
                  <p className="mt-0.5 text-2xs text-ink-faint">
                    needs {warning.required_years.toFixed(0)} yr
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ol>
      ) : null}

      {hidden > 0 ? (
        <p className="mt-1.5 text-2xs text-ink-faint">
          {formatNumber(hidden)} more dockets need a lease correction.
        </p>
      ) : null}
    </section>
  );
}
