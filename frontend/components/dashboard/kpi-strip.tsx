"use client";

import { DataError } from "@/components/ui/data-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useKpis } from "@/lib/queries/use-dashboard";
import { cn, formatNumber, formatPercent } from "@/lib/utils";

interface KpiCell {
  label: string;
  value: string;
  note: string;
  tone: "ink" | "seal" | "turmeric" | "teal";
}

const TONE_CLASS: Record<KpiCell["tone"], string> = {
  ink: "text-ink",
  seal: "text-seal",
  turmeric: "text-[#8a5f0c]",
  teal: "text-teal",
};

export function KpiStrip() {
  const { data, isPending, error, refetch } = useKpis();

  if (error && !data) {
    return <DataError error={error} onRetry={() => void refetch()} />;
  }

  if (isPending || !data) {
    return (
      <div className="grid grid-cols-2 gap-px border border-rule bg-rule md:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="bg-panel px-4 py-4">
            <Skeleton className="h-2.5 w-24" />
            <Skeleton className="mt-3 h-8 w-16" />
            <Skeleton className="mt-2 h-2.5 w-32" />
          </div>
        ))}
        <div aria-hidden className="bg-panel md:hidden" />
        <div aria-hidden className="hidden bg-panel md:block xl:hidden" />
      </div>
    );
  }

  const activeStages = data.stages.filter((stage) => stage.count > 0).length;
  const cells: KpiCell[] = [
    {
      label: "Active dockets",
      value: formatNumber(data.total_active),
      note: `${activeStages} ${activeStages === 1 ? "stage" : "stages"} in approval`,
      tone: "ink",
    },
    {
      label: "Past SLA",
      value: formatNumber(data.dwell_alerts),
      note: "Awaiting escalation action",
      tone: data.dwell_alerts > 0 ? "seal" : "teal",
    },
    {
      label: "Lease expiry",
      value: formatNumber(data.lease_expiry_warnings),
      note: "Deed ends before the course does",
      tone: data.lease_expiry_warnings > 0 ? "seal" : "teal",
    },
    {
      label: "Lease data gaps",
      value: formatNumber(data.lease_data_gaps),
      note: "No readable lease deed",
      tone: data.lease_data_gaps > 0 ? "turmeric" : "teal",
    },
    {
      label: "Approval rate",
      value: formatPercent(data.approval_rate),
      note: `${formatNumber(data.approved)} approved · ${formatNumber(data.rejected)} rejected`,
      tone: "teal",
    },
  ];

  return (
    <section aria-label="Key figures" className="border border-rule bg-rule">
      <div className="grid grid-cols-2 gap-px md:grid-cols-3 xl:grid-cols-5">
        {cells.map((cell) => (
          <dl key={cell.label} className="bg-panel px-4 py-4 sm:px-5">
            <dt className="text-2xs font-medium text-ink-soft">{cell.label}</dt>
            <dd
              className={cn(
                "mt-2 font-serif text-3xl leading-none tracking-tight tabular sm:text-[2.15rem]",
                TONE_CLASS[cell.tone],
              )}
            >
              {cell.value}
            </dd>
            <dd className="mt-2 text-2xs leading-4 text-ink-faint">{cell.note}</dd>
          </dl>
        ))}
        <div aria-hidden className="bg-panel md:hidden" />
        <div aria-hidden className="hidden bg-panel md:block xl:hidden" />
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-t border-rule bg-panel px-4 py-2 text-2xs text-ink-soft sm:px-5">
        <p>
          Rule 1 gate:{" "}
          <span className="font-medium text-ink">
            {formatNumber(data.lease_rule_blocks)} moves out of scrutiny blocked
          </span>
        </p>
        <p>
          Average stage dwell{" "}
          <span className="font-medium text-ink tabular">
            {data.avg_dwell_days === null ? "—" : `${data.avg_dwell_days.toFixed(1)} days`}
          </span>
        </p>
      </div>
    </section>
  );
}
