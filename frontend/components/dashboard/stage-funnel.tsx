"use client";

import { useEffect, useState } from "react";
import { Cell, Funnel, FunnelChart, ResponsiveContainer } from "recharts";

import { DataError } from "@/components/ui/data-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { STATUS_META } from "@/lib/constants";
import { useFunnel } from "@/lib/queries/use-dashboard";
import type { FunnelStep } from "@/types/api";
import { formatNumber, formatPercent } from "@/lib/utils";

function FunnelGraphic({ steps }: { steps: FunnelStep[] }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <div className="h-[260px] w-full" aria-hidden />;
  }

  const chartData = steps
    .filter((step) => step.count > 0)
    .map((step) => ({
      name: STATUS_META[step.status].label,
      value: step.count,
      fill: STATUS_META[step.status].accent,
    }));

  if (chartData.length === 0) {
    return (
      <div className="flex h-[260px] items-center justify-center text-xs text-ink-faint">
        No dockets recorded yet
      </div>
    );
  }

  return (
    <div role="img" aria-label="Funnel showing docket counts by approval stage" className="h-[260px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <FunnelChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <Funnel
            dataKey="value"
            data={chartData}
            isAnimationActive={false}
            stroke="#F7F7F1"
            strokeWidth={2}
          >
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={entry.fill} />
            ))}
          </Funnel>
        </FunnelChart>
      </ResponsiveContainer>
    </div>
  );
}

export function StageFunnel() {
  const { data, isPending, error, refetch } = useFunnel();

  if (error && !data) {
    return <DataError error={error} onRetry={() => void refetch()} />;
  }

  return (
    <section aria-labelledby="funnel-heading">
      <SectionHeading
        id="funnel-heading"
        title="Stage funnel"
        meta={
          data ? `All ${formatNumber(data.total)} dockets by current position` : undefined
        }
      />

      {isPending || !data ? (
        <div className="mt-4 grid gap-6 md:grid-cols-[minmax(0,300px)_minmax(0,1fr)]">
          <Skeleton className="h-[260px] w-full" />
          <div className="space-y-3 pt-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-4 w-full" />
            ))}
          </div>
        </div>
      ) : (
        <div className="mt-4 grid items-center gap-6 md:grid-cols-[minmax(0,300px)_minmax(0,1fr)]">
          <FunnelGraphic steps={data.steps} />

          <div>
            <ol className="divide-y divide-rule border-y border-rule">
              {data.steps.map((step) => {
                const meta = STATUS_META[step.status];
                return (
                  <li
                    key={step.status}
                    className="flex items-center gap-3 py-2.5 text-xs"
                  >
                    <span
                      aria-hidden
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: meta.accent }}
                    />
                    <span className="w-20 shrink-0 text-ink">{meta.label}</span>
                    <span className="w-10 shrink-0 text-right font-serif text-base leading-none tabular text-ink">
                      {formatNumber(step.count)}
                    </span>
                    <span className="ml-auto w-10 shrink-0 text-right text-2xs text-ink-soft tabular">
                      {formatPercent(step.share)}
                    </span>
                    <span aria-hidden className="hidden h-1 w-24 shrink-0 bg-ink/[0.06] sm:block">
                      <span
                        className="block h-full"
                        style={{
                          width: `${Math.min(100, step.share * 100)}%`,
                          backgroundColor: meta.accent,
                        }}
                      />
                    </span>
                  </li>
                );
              })}
            </ol>
            <p className="mt-2 text-2xs text-ink-soft">
              Counts show current positions across all dockets, not cumulative conversions.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
