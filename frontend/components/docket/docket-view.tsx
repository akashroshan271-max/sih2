"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/components/auth/auth-provider";
import { AuditTrail } from "@/components/docket/audit-trail";
import { DocketFacts } from "@/components/docket/docket-facts";
import { DocumentsPanel } from "@/components/docket/documents-panel";
import { LeaseVerdictPanel } from "@/components/docket/lease-verdict-panel";
import { WorkflowPanel } from "@/components/docket/workflow-panel";
import { SlaStamp } from "@/components/dashboard/sla-stamp";
import { Badge } from "@/components/ui/badge";
import { DataError } from "@/components/ui/data-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  APPLICATION_TYPE_LABEL,
  INSTITUTION_TYPE_LABEL,
  PROGRAMME_LEVEL_LABEL,
  STATUS_META,
  homeForRole,
} from "@/lib/constants";
import { useApplication } from "@/lib/queries/use-applications";
import { cn, dwellLabel, formatDate } from "@/lib/utils";

export function DocketView({ applicationId }: { applicationId: string }) {
  const { officer } = useAuth();
  const { data, isPending, error, refetch } = useApplication(applicationId);
  const home = officer ? homeForRole(officer.role) : "/workspace";
  const homeLabel =
    officer?.role === "regional_officer" ? "Command centre" : "My desk";

  if (error && !data) {
    return (
      <div className="space-y-4 pb-14">
        <Link
          href={home}
          className="inline-flex items-center gap-1.5 text-xs text-ink-soft hover:text-ink"
        >
          <ArrowLeft aria-hidden className="h-3.5 w-3.5" />
          {homeLabel}
        </Link>
        <DataError error={error} onRetry={() => void refetch()} />
      </div>
    );
  }

  if (isPending || !data) {
    return (
      <div className="space-y-6 pb-14">
        <Skeleton className="h-3 w-32" />
        <div className="space-y-2 border-b border-rule pb-5">
          <Skeleton className="h-3 w-40" />
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-3 w-1/2" />
        </div>
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,360px)]">
          <div className="space-y-5">
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-36 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
          <div className="space-y-5">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-56 w-full" />
          </div>
        </div>
      </div>
    );
  }

  const status = STATUS_META[data.status];
  const active = data.status !== "approved" && data.status !== "rejected";

  return (
    <div className="space-y-7 pb-14">
      <Link
        href={home}
        className="inline-flex items-center gap-1.5 text-xs text-ink-soft hover:text-ink"
      >
        <ArrowLeft aria-hidden className="h-3.5 w-3.5" />
        {homeLabel}
      </Link>

      <header className="border-b border-ink/15 pb-5">
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
          <div className="min-w-0">
            <p className="font-mono text-2xs tracking-wide text-ink-soft">
              {data.application_number}
            </p>
            <h1 className="mt-1.5 font-serif text-2xl leading-tight text-ink sm:text-[1.9rem]">
              {data.institution.name}
            </h1>
            <p className="mt-1.5 text-sm text-ink-soft">
              {data.institution.state}
              <span aria-hidden> · </span>
              {INSTITUTION_TYPE_LABEL[data.institution.institution_type]}
              <span aria-hidden> · </span>
              {APPLICATION_TYPE_LABEL[data.application_type]}
              <span aria-hidden> · </span>
              {PROGRAMME_LEVEL_LABEL[data.programme_level]}
              <span aria-hidden> · </span>
              AY {data.academic_year}
            </p>
          </div>

          <div className="flex flex-col items-start gap-2 sm:items-end">
            <Badge tone={status.tone}>{status.label}</Badge>
            <p className="flex items-center gap-2 text-xs text-ink-soft">
              <span className="tabular">{dwellLabel(data.dwell_days)}</span>
              {data.is_sla_breached ? <SlaStamp days={data.dwell_days} /> : null}
            </p>
            <p
              className={cn(
                "text-2xs tabular",
                data.is_sla_breached ? "text-seal" : "text-ink-faint",
              )}
            >
              {active
                ? `SLA due ${formatDate(data.sla_due_at)}`
                : `Decided ${formatDate(data.decided_at)}`}
            </p>
          </div>
        </div>
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,360px)] lg:items-start lg:gap-10">
        <div className="space-y-8">
          <LeaseVerdictPanel verdict={data.lease_verdict} />
          <WorkflowPanel application={data} />
          <DocumentsPanel application={data} />
        </div>

        <aside className="space-y-8">
          <DocketFacts application={data} />
          <AuditTrail applicationId={data.id} entries={data.audit_trail} />
        </aside>
      </div>
    </div>
  );
}
