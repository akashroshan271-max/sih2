"use client";

import { ArrowRight, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { DocketCard } from "@/components/workspace/docket-card";
import { Badge } from "@/components/ui/badge";
import { DataError } from "@/components/ui/data-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { SLA_LEVEL_META, STATUS_META } from "@/lib/constants";
import { useWorkspace } from "@/lib/queries/use-workspace";
import type { KpiTone, WorkspaceKpi } from "@/types/api";
import { cn, formatDate, formatNumber } from "@/lib/utils";

const KPI_ACCENT: Record<KpiTone, string> = {
  neutral: "border-t-ink/20",
  teal: "border-t-teal",
  turmeric: "border-t-turmeric",
  seal: "border-t-seal",
};

const KPI_VALUE: Record<KpiTone, string> = {
  neutral: "text-ink",
  teal: "text-teal",
  turmeric: "text-turmeric",
  seal: "text-seal",
};

function DeskKpis({ kpis }: { kpis: WorkspaceKpi[] }) {
  return (
    <div className="grid grid-cols-2 gap-px border border-rule bg-rule sm:grid-cols-3 xl:grid-cols-4">
      {kpis.map((kpi) => (
        <div
          key={kpi.key}
          className={cn(
            "border-t-2 bg-panel px-3.5 py-3",
            KPI_ACCENT[kpi.tone],
          )}
        >
          <p className="text-2xs uppercase tracking-[0.12em] text-ink-soft">
            {kpi.label}
          </p>
          <p
            className={cn(
              "mt-1.5 font-serif text-[1.55rem] leading-none tabular",
              KPI_VALUE[kpi.tone],
            )}
          >
            {formatNumber(kpi.value)}
            {kpi.unit ? (
              <span className="ml-1 font-sans text-2xs text-ink-soft">
                {kpi.unit}
              </span>
            ) : null}
          </p>
          {kpi.hint ? (
            <p className="mt-1.5 text-2xs leading-snug text-ink-faint">
              {kpi.hint}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function WorkspaceDesk() {
  const { data, isPending, error, refetch } = useWorkspace();

  if (error && !data) {
    return (
      <div className="space-y-4 pb-14">
        <p className="font-mono text-2xs uppercase tracking-[0.2em] text-ink-faint">
          Officer workspace
        </p>
        <DataError error={error} onRetry={() => void refetch()} />
      </div>
    );
  }

  if (isPending || !data) {
    return (
      <div className="space-y-7 pb-14">
        <div className="space-y-2 border-b border-rule pb-5">
          <Skeleton className="h-2.5 w-32" />
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-3 w-2/3" />
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full" />
          ))}
        </div>
        <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_minmax(0,340px)]">
          <div className="space-y-3">
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-44 w-full" />
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  const { desk, officer, kpis, queue, queue_total, escalations } = data;
  const stageMeta = desk.stage ? STATUS_META[desk.stage] : null;
  const isOversight = desk.stage === null;

  return (
    <div className="space-y-8 pb-14">
      <header className="border-b border-ink/15 pb-5">
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-mono text-2xs uppercase tracking-[0.2em] text-ink-faint">
                Officer workspace
              </p>
              <Badge tone={stageMeta?.tone ?? "neutral"}>
                {desk.stage_label}
              </Badge>
            </div>
            <h1 className="mt-1.5 font-serif text-[1.9rem] leading-tight text-ink sm:text-[2.15rem]">
              {desk.label}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft">
              {desk.mandate}
            </p>
          </div>

          <div className="sm:text-right">
            <p className="text-[13px] font-medium text-ink">{officer.full_name}</p>
            <p className="mt-0.5 text-2xs text-ink-soft">{officer.designation}</p>
            <p className="mt-1 text-2xs text-ink-faint">
              {officer.email}
              {officer.region_state ? ` · ${officer.region_state}` : ""}
            </p>
            <p className="mt-1 text-2xs text-ink-faint">
              Queue as at {formatDate(data.generated_at)}
            </p>
          </div>
        </div>

        {data.notice ? (
          <p className="mt-4 border-l-2 border-turmeric bg-turmeric-soft/50 px-3 py-2 text-xs leading-relaxed text-ink-soft">
            {data.notice}
          </p>
        ) : null}
      </header>

      <DeskKpis kpis={kpis} />

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_minmax(0,340px)] xl:items-start xl:gap-10">
        <section id="queue" aria-labelledby="queue-heading">
          <SectionHeading
            id="queue-heading"
            title={isOversight ? "Dockets in flight" : "Waiting at your desk"}
            meta={`${formatNumber(queue_total)} docket${queue_total === 1 ? "" : "s"} · oldest first`}
          />

          {queue.length === 0 ? (
            <div className="mt-3 border border-dashed border-rule bg-panel px-5 py-10 text-center">
              <p className="font-serif text-lg text-ink">
                Nothing waiting at this desk
              </p>
              <p className="mx-auto mt-1.5 max-w-md text-xs leading-relaxed text-ink-soft">
                {isOversight
                  ? "No active dockets in the region right now."
                  : "Dockets arrive here when the previous phase forwards them. The queue refreshes every minute."}
              </p>
            </div>
          ) : (
            <ul className="mt-3 space-y-4">
              {queue.map((docket) => (
                <DocketCard key={docket.id} docket={docket} />
              ))}
            </ul>
          )}

          {queue.length < queue_total ? (
            <p className="mt-3 text-2xs text-ink-faint">
              Showing the {queue.length} oldest of {formatNumber(queue_total)}{" "}
              dockets. Clear these first; the queue is ordered by dwell time.
            </p>
          ) : null}
        </section>

        <aside className="space-y-8">
          <section aria-labelledby="mandate-heading">
            <SectionHeading
              id="mandate-heading"
              title="What this desk must verify"
              meta={desk.stage_label}
            />
            <div className="mt-3 border-l-2 border-teal bg-panel px-4 py-4">
              <ul className="space-y-2.5">
                {desk.checklist.map((item) => (
                  <li key={item} className="flex gap-2.5">
                    <span
                      aria-hidden
                      className="mt-[6px] h-1.5 w-1.5 shrink-0 bg-teal/70"
                    />
                    <span className="text-xs leading-relaxed text-ink-soft">
                      {item}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          <section aria-labelledby="authority-heading">
            <SectionHeading id="authority-heading" title="Your authority" />
            <div className="mt-3 border border-rule bg-panel px-4 py-4">
              <p className="text-2xs uppercase tracking-[0.12em] text-ink-faint">
                Next step
              </p>
              <p className="mt-1 text-xs leading-relaxed text-ink-soft">
                {desk.next_step}
              </p>
              <p className="mt-3 border-t border-rule pt-3 text-2xs uppercase tracking-[0.12em] text-ink-faint">
                Scope
              </p>
              <p className="mt-1 text-xs leading-relaxed text-ink-soft">
                {desk.authority}
              </p>
              <p className="mt-3 flex gap-2 border-t border-rule pt-3 text-2xs leading-relaxed text-ink-faint">
                <ShieldCheck aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal/70" />
                AI extraction is evidence only. Every move and decision is
                signed by an officer into the audit chain.
              </p>
            </div>
          </section>

          {isOversight ? (
            <>
              <section aria-labelledby="escalation-heading">
                <SectionHeading
                  id="escalation-heading"
                  title="Dwell-time escalations"
                  meta={`${escalations.length} live`}
                />
                {escalations.length === 0 ? (
                  <p className="mt-3 border border-rule bg-panel px-4 py-3 text-xs text-ink-soft">
                    No docket is past the dwell threshold.
                  </p>
                ) : (
                  <ul className="mt-3 divide-y divide-rule border border-rule bg-panel">
                    {escalations.map((alert) => {
                      const level = SLA_LEVEL_META[alert.level];
                      return (
                        <li key={`${alert.application_id}-${alert.level}`} className="px-3.5 py-2.5">
                          <div className="flex items-center justify-between gap-2">
                            <Badge tone={level.tone}>{level.label}</Badge>
                            <span className="text-2xs tabular text-seal">
                              {Math.floor(alert.dwell_days)} days
                            </span>
                          </div>
                          <p className="mt-1 text-xs font-medium leading-snug text-ink">
                            {alert.institution_name}
                          </p>
                          <p className="mt-0.5 text-2xs text-ink-faint">
                            {alert.application_number} · {STATUS_META[alert.status].label} · {alert.escalate_to}
                          </p>
                        </li>
                      );
                    })}
                  </ul>
                )}
                <Link
                  href="/dashboard#escalations"
                  className="mt-2 inline-flex items-center gap-1.5 text-xs text-teal underline-offset-4 hover:underline"
                >
                  Open the escalation register
                  <ArrowRight aria-hidden className="h-3.5 w-3.5" />
                </Link>
              </section>

              <section aria-labelledby="region-heading">
                <SectionHeading id="region-heading" title="Region at a glance" />
                <dl className="mt-3 grid grid-cols-2 gap-px border border-rule bg-rule text-xs">
                  {Object.entries(data.stage_counts).map(([status, count]) => (
                    <div key={status} className="bg-panel px-3 py-2">
                      <dt className="text-2xs text-ink-faint">
                        {STATUS_META[status as keyof typeof STATUS_META]?.label ?? status}
                      </dt>
                      <dd className="font-serif text-lg leading-none tabular text-ink">
                        {formatNumber(count)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            </>
          ) : (
            <section aria-labelledby="protocol-heading">
              <SectionHeading
                id="protocol-heading"
                title="Stage protocol"
                meta="APH 2024–27"
              />
              <div className="mt-3 border border-rule bg-panel px-4 py-4 text-xs leading-relaxed text-ink-soft">
                <p>
                  A docket that sits here longer than{" "}
                  <span className="tabular font-medium text-ink">15 days</span>{" "}
                  escalates to L1, at 30 days to the Regional Officer, and at 45
                  to the Chairman.
                </p>
                <p className="mt-2">
                  {desk.stage === "sac" || desk.stage === "shc"
                    ? "Rejections need a recorded reason. The approval decision belongs to this committee and cannot be delegated to the assistant."
                    : "Rejections need a recorded reason. This desk records its finding and forwards; approval is issued only at the committee stage."}
                </p>
              </div>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
