"use client";

import { SlaScanButton } from "@/components/dashboard/sla-scan-button";
import { useKpis } from "@/lib/queries/use-dashboard";
import { relativeTime } from "@/lib/utils";

export function DashboardHeader() {
  const { data } = useKpis();

  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4 border-b border-ink/15 pb-5">
      <div>
        <p className="text-xs text-ink-soft">Western region · Regional office</p>
        <h1 className="mt-1 font-serif text-3xl leading-tight text-ink sm:text-[2.2rem]">
          Approval command centre
        </h1>
        <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-ink-soft">
          Every docket in the statutory pipeline, the days it has held, and the lease
          checks keeping it there.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <p className="flex items-center gap-1.5 text-2xs text-ink-soft">
          <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-teal" />
          {data ? `Updated ${relativeTime(data.generated_at)}` : "Connecting to API"}
        </p>
        <SlaScanButton />
      </div>
    </header>
  );
}
