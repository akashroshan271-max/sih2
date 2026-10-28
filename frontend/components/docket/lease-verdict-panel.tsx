"use client";

import { Badge } from "@/components/ui/badge";
import { LEASE_CODE_LABEL } from "@/lib/constants";
import type { LeaseVerdict } from "@/types/api";
import { formatDate, yearsLabel } from "@/lib/utils";

export function LeaseVerdictPanel({ verdict }: { verdict: LeaseVerdict | null }) {
  if (!verdict) {
    return (
      <section aria-labelledby="lease-verdict-heading">
        <h2
          id="lease-verdict-heading"
          className="border-b border-rule pb-2 font-serif text-lg"
        >
          Live lease
        </h2>
        <p className="mt-3 text-sm text-ink-soft">
          The lease verdict has not been evaluated for this docket.
        </p>
      </section>
    );
  }

  const compliant = verdict.compliant;
  const accent = compliant ? "#0E4A45" : "#A33A28";

  return (
    <section
      aria-labelledby="lease-verdict-heading"
      className="border border-rule border-l-2 px-4 py-4"
      style={{
        borderLeftColor: accent,
        backgroundColor: compliant ? "rgba(220, 231, 225, 0.45)" : "rgba(242, 226, 220, 0.6)",
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-2xs text-ink-soft">APH 2024–27 · clause 2.1(e)</p>
          <h2
            id="lease-verdict-heading"
            className="mt-1 font-serif text-lg leading-snug text-ink"
          >
            {LEASE_CODE_LABEL[verdict.code] ?? verdict.code}
          </h2>
        </div>
        <Badge tone={compliant ? "teal" : "seal"}>
          {compliant ? "Rule 1 satisfied" : "Rule 1 blocking"}
        </Badge>
      </div>

      <p className="mt-2 max-w-prose text-sm leading-relaxed text-ink">
        {verdict.reason}
      </p>

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-ink/10 pt-3 sm:grid-cols-4">
        <div>
          <dt className="text-2xs text-ink-soft">Lease start</dt>
          <dd className="mt-0.5 text-xs text-ink tabular">
            {formatDate(verdict.lease_start_date)}
          </dd>
        </div>
        <div>
          <dt className="text-2xs text-ink-soft">Lease end</dt>
          <dd className="mt-0.5 text-xs text-ink tabular">
            {formatDate(verdict.lease_end_date)}
          </dd>
        </div>
        <div>
          <dt className="text-2xs text-ink-soft">Remaining lease</dt>
          <dd className="mt-0.5 text-xs font-medium text-ink tabular">
            {yearsLabel(verdict.remaining_lease_years)}
          </dd>
        </div>
        <div>
          <dt className="text-2xs text-ink-soft">Course requires</dt>
          <dd className="mt-0.5 text-xs text-ink tabular">
            {yearsLabel(verdict.required_years)}
          </dd>
        </div>
        <div>
          <dt className="text-2xs text-ink-soft">Evaluated</dt>
          <dd className="mt-0.5 text-xs text-ink tabular">
            {formatDate(verdict.as_of)}
          </dd>
        </div>
      </dl>

      <p className="mt-3 text-2xs text-ink-soft">
        {compliant
          ? "Remaining lease covers the maximum course duration, so scrutiny may release the docket."
          : "The docket cannot leave scrutiny until the lease position is corrected."}
      </p>
    </section>
  );
}
