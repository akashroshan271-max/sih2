"use client";

import Link from "next/link";

import { SlaStamp } from "@/components/dashboard/sla-stamp";
import { DataError } from "@/components/ui/data-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ACTIVE_STAGES,
  APPLICATION_TYPE_LABEL,
  PROGRAMME_LEVEL_LABEL,
  STAGE_META,
} from "@/lib/constants";
import { useKpis, usePipeline } from "@/lib/queries/use-dashboard";
import type { ApplicationSummary } from "@/types/api";
import { cn, dwellLabel, formatNumber } from "@/lib/utils";

function DocketSlip({ application }: { application: ApplicationSummary }) {
  const meta = STAGE_META[application.status as keyof typeof STAGE_META];

  return (
    <Link
      href={`/dashboard/applications/${application.id}`}
      title={application.institution.name}
      className="block border border-rule border-l-2 bg-panel px-2.5 py-2 transition-colors hover:border-ink/25 hover:bg-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal focus-visible:ring-offset-1 focus-visible:ring-offset-paper"
      style={{ borderLeftColor: meta?.accent ?? "#16211F" }}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 truncate text-[13px] font-medium leading-tight text-ink">
          {application.institution.name}
        </p>
        {application.is_sla_breached ? (
          <SlaStamp days={application.dwell_days} />
        ) : null}
      </div>
      <p className="mt-1 truncate font-mono text-2xs text-ink-faint">
        {application.application_number}
      </p>
      <div className="mt-2 flex items-baseline justify-between gap-2 text-2xs text-ink-soft">
        <span className="truncate">
          {APPLICATION_TYPE_LABEL[application.application_type]} ·{" "}
          {PROGRAMME_LEVEL_LABEL[application.programme_level]}
        </span>
        <span
          className={cn(
            "shrink-0 tabular",
            application.is_sla_breached && "font-medium text-seal",
          )}
        >
          {dwellLabel(application.dwell_days)}
        </span>
      </div>
    </Link>
  );
}

export function PipelineBoard() {
  const { data, isPending, error, refetch } = usePipeline(6);
  const { data: kpis } = useKpis();

  if (error && !data) {
    return <DataError error={error} onRetry={() => void refetch()} />;
  }

  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {ACTIVE_STAGES.map((stage) => {
        const meta = STAGE_META[stage];
        const column = data?.columns.find((entry) => entry.status === stage);
        const stat = kpis?.stages.find((entry) => entry.status === stage);
        const applications = column?.applications ?? [];
        const hidden = column ? Math.max(0, column.count - applications.length) : 0;

        return (
          <section
            key={stage}
            aria-labelledby={`stage-${stage}`}
            className="flex min-w-[248px] flex-1 flex-col border border-rule bg-[#E8EAE2]"
          >
            <header
              className="border-b border-rule px-3 py-2.5"
              style={{ backgroundColor: meta.tint }}
            >
              <div className="flex items-baseline justify-between gap-2">
                <h3
                  id={`stage-${stage}`}
                  className="text-[13px] font-semibold leading-tight text-ink"
                >
                  {meta.label}
                </h3>
                <span className="font-serif text-xl leading-none tabular text-ink">
                  {column ? formatNumber(column.count) : "—"}
                </span>
              </div>
              <p className="mt-1 text-2xs text-ink-soft">{meta.note}</p>
              {stat ? (
                <p className="mt-1 text-2xs text-ink-soft">
                  <span
                    className={cn(
                      "tabular",
                      stat.breached > 0 && "font-medium text-seal",
                    )}
                  >
                    {formatNumber(stat.breached)} past SLA
                  </span>
                  <span aria-hidden> · </span>
                  <span className="tabular">{stat.avg_dwell_days.toFixed(1)} d avg</span>
                </p>
              ) : null}
            </header>

            <div className="flex-1 space-y-2 p-2">
              {isPending && !data
                ? Array.from({ length: 3 }).map((_, index) => (
                    <div key={index} className="space-y-2 border border-rule bg-panel p-3">
                      <Skeleton className="h-3 w-4/5" />
                      <Skeleton className="h-2.5 w-3/5" />
                      <Skeleton className="h-2.5 w-2/5" />
                    </div>
                  ))
                : null}

              {!isPending && applications.length === 0 ? (
                <p className="px-1 py-4 text-center text-2xs text-ink-faint">
                  No dockets waiting
                </p>
              ) : null}

              {applications.map((application) => (
                <DocketSlip key={application.id} application={application} />
              ))}

              {hidden > 0 ? (
                <p className="px-1 pt-1 text-2xs text-ink-faint">
                  {formatNumber(hidden)} more in this stage
                </p>
              ) : null}
            </div>
          </section>
        );
      })}
    </div>
  );
}
