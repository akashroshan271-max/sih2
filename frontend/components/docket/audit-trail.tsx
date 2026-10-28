"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataError } from "@/components/ui/data-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { ACTION_LABEL, STATUS_META } from "@/lib/constants";
import { useChainVerification } from "@/lib/queries/use-applications";
import type { AuditEntry } from "@/types/api";
import { cn, formatDateTime, shortHash, titleCase } from "@/lib/utils";

export function AuditTrail({
  applicationId,
  entries,
}: {
  applicationId: string;
  entries: AuditEntry[];
}) {
  const [requested, setRequested] = useState(false);
  const verification = useChainVerification(applicationId, requested);

  const newestFirst = [...entries].sort(
    (left, right) =>
      new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime(),
  );

  return (
    <section aria-labelledby="audit-heading">
      <SectionHeading
        id="audit-heading"
        title="Audit chain"
        meta={`${entries.length} signed ${entries.length === 1 ? "entry" : "entries"}`}
      />

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setRequested(true);
            if (requested) void verification.refetch();
          }}
          disabled={verification.isFetching}
        >
          {verification.isFetching
            ? "Verifying"
            : requested
              ? "Recheck chain"
              : "Verify chain"}
        </Button>
        <p className="text-2xs text-ink-soft">Recomputes SHA-256 across every entry.</p>
      </div>

      {verification.error ? (
        <DataError
          className="mt-2"
          error={verification.error}
          onRetry={() => void verification.refetch()}
          compact
        />
      ) : null}

      {verification.data ? (
        <div
          role="status"
          className={cn(
            "mt-2 border px-2.5 py-2 text-2xs",
            verification.data.verification.valid
              ? "border-teal/30 bg-teal-soft text-teal"
              : "border-seal/40 bg-seal-soft text-seal",
          )}
        >
          {verification.data.verification.valid
            ? `Chain intact across ${verification.data.verification.checked} ${verification.data.verification.checked === 1 ? "entry" : "entries"}.`
            : `Chain broken at entry ${verification.data.verification.broken_at ?? "unknown"}. ${verification.data.verification.reason ?? ""}`}
        </div>
      ) : null}

      {newestFirst.length === 0 ? (
        <p className="mt-3 border border-dashed border-rule px-3 py-3 text-xs text-ink-soft">
          No audit entries yet.
        </p>
      ) : (
        <ol className="mt-4 space-y-4 border-l border-rule pl-4">
          {newestFirst.map((entry) => (
            <li key={entry.id} className="relative">
              <span
                aria-hidden
                className="absolute -left-[21px] top-1.5 h-[7px] w-[7px] rounded-full border border-teal bg-panel"
              />
              <p className="text-xs leading-snug text-ink">
                {ACTION_LABEL[entry.action] ?? titleCase(entry.action)}
              </p>
              <p className="mt-0.5 text-2xs text-ink-faint">
                {formatDateTime(entry.timestamp)}
                <span aria-hidden> · </span>
                {entry.actor}
                {entry.actor_role ? ` (${entry.actor_role})` : ""}
              </p>

              {entry.from_status || entry.to_status ? (
                <div className="mt-1.5 flex flex-wrap items-center gap-1 text-2xs text-ink-faint">
                  {entry.from_status ? (
                    <Badge tone={STATUS_META[entry.from_status].tone}>
                      {STATUS_META[entry.from_status].label}
                    </Badge>
                  ) : null}
                  {entry.from_status && entry.to_status ? (
                    <span aria-hidden>→</span>
                  ) : null}
                  {entry.to_status ? (
                    <Badge tone={STATUS_META[entry.to_status].tone}>
                      {STATUS_META[entry.to_status].label}
                    </Badge>
                  ) : null}
                </div>
              ) : null}

              <p
                className="mt-1.5 font-mono text-[10px] leading-4 text-ink-faint"
                title={entry.sha256_hash}
              >
                {shortHash(entry.sha256_hash)}
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
