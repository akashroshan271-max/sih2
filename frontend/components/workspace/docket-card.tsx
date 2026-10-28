"use client";

import { ArrowRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { SlaStamp } from "@/components/dashboard/sla-stamp";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  APPLICATION_TYPE_LABEL,
  EXTRACTION_META,
  INSTITUTION_TYPE_LABEL,
  LEASE_CODE_LABEL,
  PROGRAMME_LEVEL_LABEL,
  STATUS_META,
} from "@/lib/constants";
import { useAdvanceDocket } from "@/lib/queries/use-workspace";
import type {
  ApplicationStatus,
  WorkspaceDocket,
} from "@/types/api";
import { cn, dwellLabel, formatDate } from "@/lib/utils";

const ORDER: ApplicationStatus[] = [
  "scrutiny",
  "evc",
  "sac",
  "shc",
  "approved",
  "rejected",
];

export function DocketCard({ docket }: { docket: WorkspaceDocket }) {
  const [pending, setPending] = useState<{
    toStatus: ApplicationStatus;
    label: string;
  } | null>(null);
  const [remarks, setRemarks] = useState("");
  const advance = useAdvanceDocket(docket.id);

  const actions = [...docket.actions].sort(
    (left, right) => ORDER.indexOf(left.to_status) - ORDER.indexOf(right.to_status),
  );
  const forward = actions.filter((action) => !action.is_decision);
  const decisions = actions.filter((action) => action.is_decision);
  const attention = docket.documents.filter((document) =>
    ["pending", "needs_review", "failed"].includes(document.extraction_status),
  ).length;

  async function confirmMove() {
    if (!pending) return;
    try {
      const result = await advance.mutateAsync({
        toStatus: pending.toStatus,
        remarks,
      });
      toast.success(`Docket moved to ${STATUS_META[result.to_status].label}`, {
        description: `${docket.application_number} · signed into the audit chain.`,
      });
      setPending(null);
      setRemarks("");
    } catch (cause) {
      toast.error("The move was blocked", {
        description:
          cause instanceof ApiError
            ? cause.message
            : "The transition could not be completed.",
      });
    }
  }

  return (
    <li className="border border-rule bg-panel">
      <div className="flex flex-wrap items-start justify-between gap-x-5 gap-y-3 px-4 py-3.5">
        <div className="min-w-0">
          <p className="font-mono text-2xs tracking-wide text-ink-soft">
            {docket.application_number}
          </p>
          <h3 className="mt-1 font-serif text-lg leading-snug text-ink">
            {docket.institution_name}
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-ink-soft">
            {docket.state}
            {docket.district ? ` · ${docket.district}` : ""}
            <span aria-hidden> · </span>
            {INSTITUTION_TYPE_LABEL[docket.institution_type]}
            <span aria-hidden> · </span>
            {APPLICATION_TYPE_LABEL[docket.application_type]}
            <span aria-hidden> · </span>
            {PROGRAMME_LEVEL_LABEL[docket.programme_level]}
            <span aria-hidden> · </span>
            AY {docket.academic_year}
          </p>
        </div>

        <div className="flex flex-col items-start gap-1.5 sm:items-end">
          <Badge tone={STATUS_META[docket.status].tone}>
            {STATUS_META[docket.status].label}
          </Badge>
          <p className="flex items-center gap-2 text-xs text-ink-soft">
            <span className="tabular">{dwellLabel(docket.dwell_days)}</span>
            {docket.is_sla_breached ? (
              <SlaStamp days={docket.dwell_days} />
            ) : null}
          </p>
          <p
            className={cn(
              "text-2xs tabular",
              docket.is_sla_breached ? "text-seal" : "text-ink-faint",
            )}
          >
            SLA due {formatDate(docket.sla_due_at)}
          </p>
        </div>
      </div>

      <dl className="grid grid-cols-1 gap-x-6 gap-y-2.5 border-t border-rule px-4 py-3 sm:grid-cols-2">
        {docket.facts.map((fact) => (
          <div key={fact.label} className="min-w-0">
            <dt className="text-2xs uppercase tracking-[0.1em] text-ink-faint">
              {fact.label}
            </dt>
            <dd className="mt-0.5 text-xs leading-snug text-ink">
              {fact.value}
              {fact.note ? (
                <span className="mt-0.5 block text-2xs text-ink-faint">
                  {fact.note}
                </span>
              ) : null}
            </dd>
          </div>
        ))}
      </dl>

      {docket.lease ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-rule px-4 py-2.5 text-2xs">
          <Badge tone={docket.lease.compliant ? "teal" : "seal"}>
            {LEASE_CODE_LABEL[docket.lease.verdict_code] ??
              docket.lease.verdict_code}
          </Badge>
          {docket.lease.extraction_status ? (
            <span className="text-ink-soft">
              Lease {EXTRACTION_META[docket.lease.extraction_status].label.toLowerCase()}
            </span>
          ) : null}
          {docket.lease.lease_end_date ? (
            <span className="text-ink-soft">
              ends{" "}
              <span className="tabular">
                {formatDate(docket.lease.lease_end_date)}
              </span>
            </span>
          ) : null}
          {docket.lease.remaining_years !== null ? (
            <span className="tabular text-ink-soft">
              {docket.lease.remaining_years.toFixed(1)} of{" "}
              {docket.lease.required_years.toFixed(1)} yrs
            </span>
          ) : null}
          <span className="text-ink-faint">
            {docket.documents.length} document
            {docket.documents.length === 1 ? "" : "s"}
            {attention ? ` · ${attention} to read` : ""}
          </span>
        </div>
      ) : null}

      <div className="flex flex-wrap items-start gap-2 border-t border-rule bg-paper/50 px-4 py-3">
        <Button size="sm" variant="outline" asChild>
          <Link href={`/dashboard/applications/${docket.id}`}>Open docket</Link>
        </Button>

        {forward.map((action) => (
          <div key={action.to_status} className="flex flex-col gap-1">
            <Button
              size="sm"
              disabled={!action.enabled || advance.isPending}
              onClick={() => {
                setPending({ toStatus: action.to_status, label: action.label });
                setRemarks("");
              }}
              title={action.blocked_reason ?? undefined}
            >
              {action.label}
            </Button>
            {!action.enabled && action.blocked_reason ? (
              <p className="max-w-[230px] text-2xs leading-snug text-seal">
                {action.blocked_reason}
              </p>
            ) : null}
          </div>
        ))}

        {decisions.length > 0 ? (
          <Link
            href={`/dashboard/applications/${docket.id}#workflow-heading`}
            className="ml-auto inline-flex items-center gap-1.5 self-center text-xs text-teal underline-offset-4 hover:underline"
          >
            {decisions.length > 1
              ? "Approve or reject in docket"
              : decisions[0].to_status === "rejected"
                ? "Reject in docket"
                : "Approve in docket"}
            <ArrowRight aria-hidden className="h-3.5 w-3.5" />
          </Link>
        ) : null}
      </div>

      {pending ? (
        <div className="border-t border-rule bg-paper/80 px-4 py-3">
          <p className="text-xs leading-relaxed text-ink">
            Move this docket to{" "}
            <strong className="font-medium">
              {STATUS_META[pending.toStatus].label}
            </strong>
            ? The move is signed under your officer ID and restarts the SLA
            clock.
          </p>
          <label htmlFor={`note-${docket.id}`} className="sr-only">
            Decision note for {docket.application_number}
          </label>
          <textarea
            id={`note-${docket.id}`}
            rows={2}
            value={remarks}
            onChange={(event) => setRemarks(event.target.value)}
            placeholder="Optional note for the audit trail"
            className="mt-2 w-full resize-y border border-rule bg-panel px-2.5 py-2 text-xs text-ink placeholder:text-ink-faint focus:border-teal focus:outline-none"
          />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              onClick={() => void confirmMove()}
              disabled={advance.isPending}
            >
              {advance.isPending ? (
                <Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" />
              ) : null}
              {pending.label}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setPending(null)}
              disabled={advance.isPending}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : null}
    </li>
  );
}
