import { SectionHeading } from "@/components/ui/section-heading";
import {
  APPLICATION_TYPE_LABEL,
  INSTITUTION_TYPE_LABEL,
  PROGRAMME_LEVEL_LABEL,
} from "@/lib/constants";
import type { ApplicationDetail } from "@/types/api";
import { cn, formatDate, formatNumber, yearsLabel } from "@/lib/utils";

export function DocketFacts({ application }: { application: ApplicationDetail }) {
  const facts: { label: string; value: string; alert?: boolean }[] = [
    {
      label: "Institution type",
      value: INSTITUTION_TYPE_LABEL[application.institution.institution_type],
    },
    { label: "State", value: application.institution.state },
    {
      label: "Docket type",
      value: APPLICATION_TYPE_LABEL[application.application_type],
    },
    {
      label: "Programme",
      value: PROGRAMME_LEVEL_LABEL[application.programme_level],
    },
    { label: "Academic year", value: application.academic_year },
    {
      label: "Proposed intake",
      value:
        application.proposed_intake === null
          ? "—"
          : `${formatNumber(application.proposed_intake)} seats`,
    },
    {
      label: "Max course duration",
      value: yearsLabel(application.max_course_duration_years),
    },
    { label: "Submitted", value: formatDate(application.submitted_at) },
    { label: "In stage since", value: formatDate(application.stage_entry_timestamp) },
    {
      label: "SLA due",
      value: formatDate(application.sla_due_at),
      alert: application.is_sla_breached,
    },
  ];

  return (
    <section aria-labelledby="facts-heading">
      <SectionHeading id="facts-heading" title="Docket record" />
      <dl className="mt-3 divide-y divide-rule/70 border-y border-rule">
        {facts.map((fact) => (
          <div
            key={fact.label}
            className="flex items-baseline justify-between gap-3 py-1.5"
          >
            <dt className="text-2xs text-ink-soft">{fact.label}</dt>
            <dd
              className={cn(
                "text-right text-xs text-ink tabular",
                fact.alert && "font-medium text-seal",
              )}
            >
              {fact.value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
