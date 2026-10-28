"use client";

import { DataError, EmptyNote } from "@/components/ui/data-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { ACTIVE_STAGES, STAGE_META } from "@/lib/constants";
import { useHeatmap } from "@/lib/queries/use-dashboard";
import type { HeatmapCell } from "@/types/api";
import { formatNumber } from "@/lib/utils";

function tint(avgDwellDays: number, thresholdDays: number): number {
  const ratio = Math.min(1, avgDwellDays / Math.max(thresholdDays * 1.6, 1));
  return 0.08 + ratio * 0.62;
}

export function SlaHeatmap() {
  const { data, isPending, error, refetch } = useHeatmap();

  if (error && !data) {
    return <DataError error={error} onRetry={() => void refetch()} />;
  }

  if (isPending || !data) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const lookup = new Map<string, HeatmapCell>();
  for (const cell of data.cells) {
    lookup.set(`${cell.state}:${cell.status}`, cell);
  }

  const states = [...data.states].sort((left, right) => {
    const breached = (state: string) =>
      data.cells
        .filter((cell) => cell.state === state)
        .reduce((total, cell) => total + cell.breached, 0);
    return breached(right) - breached(left) || left.localeCompare(right);
  });

  if (states.length === 0) {
    return (
      <EmptyNote
        title="No active dockets to map"
        hint="Dwell heat maps appear once applications enter scrutiny."
      />
    );
  }

  const stageAverage = (state: string): number | null => {
    const cells = data.cells.filter((cell) => cell.state === state);
    const count = cells.reduce((total, cell) => total + cell.count, 0);
    if (count === 0) return null;
    return (
      cells.reduce((total, cell) => total + cell.avg_dwell_days * cell.count, 0) / count
    );
  };

  return (
    <section aria-labelledby="heatmap-heading">
      <SectionHeading
        id="heatmap-heading"
        title="Dwell by state and stage"
        meta={`Average days held · breach past ${data.threshold_days} days`}
      />

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse">
          <caption className="sr-only">
            Average dwell time in days for active dockets, by state and approval stage.
            Darker cells sit longer; the stage limit is {data.threshold_days} days.
          </caption>
          <thead>
            <tr>
              <th
                scope="col"
                className="pb-2 pr-3 text-left text-2xs font-medium text-ink-soft"
              >
                State
              </th>
              {ACTIVE_STAGES.map((stage) => (
                <th
                  key={stage}
                  scope="col"
                  className="px-1 pb-2 text-right text-2xs font-medium text-ink-soft"
                  title={STAGE_META[stage].label}
                >
                  {STAGE_META[stage].short}
                </th>
              ))}
              <th
                scope="col"
                className="pb-2 pl-3 text-right text-2xs font-medium text-ink-soft"
              >
                All
              </th>
            </tr>
          </thead>
          <tbody>
            {states.map((state) => {
              const overall = stageAverage(state);
              return (
                <tr key={state} className="border-t border-rule">
                  <th
                    scope="row"
                    className="whitespace-nowrap py-1 pr-3 text-left text-xs font-normal text-ink"
                  >
                    {state}
                  </th>
                  {ACTIVE_STAGES.map((stage) => {
                    const cell = lookup.get(`${state}:${stage}`);
                    if (!cell || cell.count === 0) {
                      return (
                        <td key={stage} className="px-1 py-1">
                          <div className="flex h-11 items-center justify-center border border-rule/60 bg-panel">
                            <span className="text-2xs text-ink-faint">—</span>
                          </div>
                        </td>
                      );
                    }
                    const alpha = tint(cell.avg_dwell_days, data.threshold_days);
                    const dark = alpha > 0.4;
                    return (
                      <td key={stage} className="px-1 py-1">
                        <div
                          className="flex h-11 flex-col items-center justify-center"
                          style={{
                            backgroundColor: `rgba(163, 58, 40, ${alpha.toFixed(3)})`,
                            color: dark ? "#F7F7F1" : "#16211F",
                          }}
                          title={`${state} · ${STAGE_META[stage].label}: ${cell.count} dockets, ${cell.avg_dwell_days.toFixed(1)} days average, ${cell.breached} past SLA`}
                        >
                          <span className="text-xs font-medium leading-4 tabular">
                            {formatNumber(cell.count)}
                          </span>
                          <span className="text-[10px] leading-3 tabular opacity-85">
                            {cell.avg_dwell_days.toFixed(1)} d
                          </span>
                          <span className="sr-only">
                            {cell.breached} past SLA
                          </span>
                        </div>
                      </td>
                    );
                  })}
                  <td className="py-1 pl-3 text-right">
                    <span className="text-xs text-ink-soft tabular">
                      {overall === null ? "—" : `${overall.toFixed(1)} d`}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-2 text-2xs text-ink-soft">
        <p>Each cell shows the docket count, with average dwell beneath.</p>
        <div className="flex items-center gap-1.5">
          <span className="tabular">0 d</span>
          <span aria-hidden className="flex">
            {[0.1, 0.22, 0.34, 0.46, 0.58, 0.7].map((alpha) => (
              <span
                key={alpha}
                className="h-2 w-5"
                style={{ backgroundColor: `rgba(163, 58, 40, ${alpha})` }}
              />
            ))}
          </span>
          <span className="tabular">{data.threshold_days * 2} d+</span>
        </div>
      </div>
    </section>
  );
}
