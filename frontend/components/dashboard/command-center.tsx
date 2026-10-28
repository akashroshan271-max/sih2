"use client";

import Link from "next/link";

import { useAuth } from "@/components/auth/auth-provider";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { KpiStrip } from "@/components/dashboard/kpi-strip";
import { PipelineBoard } from "@/components/dashboard/pipeline-board";
import { EscalationRegister, LeaseRegister } from "@/components/dashboard/registers";
import { SlaHeatmap } from "@/components/dashboard/sla-heatmap";
import { StageFunnel } from "@/components/dashboard/stage-funnel";
import { Button } from "@/components/ui/button";
import { SectionHeading } from "@/components/ui/section-heading";
import { ROLE_META } from "@/lib/constants";

export function CommandCenter() {
  const { officer } = useAuth();

  if (officer && officer.role !== "regional_officer") {
    const meta = ROLE_META[officer.role];
    return (
      <section
        aria-labelledby="oversight-only"
        className="mx-auto mt-8 max-w-2xl border border-rule bg-panel px-6 py-12 text-center"
      >
        <p className="font-mono text-2xs uppercase tracking-[0.2em] text-ink-faint">
          Oversight surface
        </p>
        <h1
          id="oversight-only"
          className="mt-2 font-serif text-2xl leading-tight text-ink"
        >
          The command centre belongs to the regional office
        </h1>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-ink-soft">
          You are signed in as {meta.label} for the {meta.desk}. Your dockets,
          evidence and moves are in your own workspace.
        </p>
        <Button asChild className="mt-5">
          <Link href="/workspace">Open my desk</Link>
        </Button>
      </section>
    );
  }

  return (
    <div className="space-y-9 pb-14">
      <DashboardHeader />
      <KpiStrip />

      <section
        id="pipeline"
        aria-labelledby="pipeline-heading"
        className="scroll-mt-24"
      >
        <SectionHeading
          id="pipeline-heading"
          title="Approval pipeline"
          meta="Oldest dockets first · open a slip to act on it"
        />
        <div className="mt-3">
          <PipelineBoard />
        </div>
      </section>

      <div className="grid gap-8 lg:grid-cols-2 lg:gap-10">
        <EscalationRegister id="escalations" />
        <LeaseRegister id="lease-watch" />
      </div>

      <SlaHeatmap />
      <StageFunnel />
    </div>
  );
}
