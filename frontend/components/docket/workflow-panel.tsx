"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { SectionHeading } from "@/components/ui/section-heading";
import { ApiError } from "@/lib/api";
import { STATUS_META } from "@/lib/constants";
import { useTransitionApplication } from "@/lib/queries/use-applications";
import type { ApplicationDetail, ApplicationStatus } from "@/types/api";
import { cn, formatDate } from "@/lib/utils";

const ORDER: ApplicationStatus[] = [
  "scrutiny",
  "evc",
  "sac",
  "shc",
  "approved",
  "rejected",
];

const TRANSITION_LABEL: Record<ApplicationStatus, string> = {
  scrutiny: "Return to scrutiny",
  evc: "Send to EVC",
  sac: "Send to SAC",
  shc: "Send to SHC",
  approved: "Approve",
  rejected: "Reject",
};

export function WorkflowPanel({ application }: { application: ApplicationDetail }) {
  const [remarks, setRemarks] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const transition = useTransitionApplication(application.id);

  const terminal =
    application.status === "approved" || application.status === "rejected";

  const allowed = [...application.allowed_transitions].sort(
    (left, right) => ORDER.indexOf(left) - ORDER.indexOf(right),
  );

  async function move(toStatus: ApplicationStatus) {
    setActionError(null);
    try {
      const result = await transition.mutateAsync({ toStatus, remarks });
      setRemarks("");
      toast.success(`Docket moved to ${STATUS_META[result.to_status].label}`, {
        description: `${application.application_number} · recorded in the audit chain.`,
      });
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "The transition could not be completed.";
      setActionError(message);
      toast.error("The move was blocked", { description: message });
    }
  }

  return (
    <section aria-labelledby="workflow-heading">
      <SectionHeading
        id="workflow-heading"
        title="Move the docket"
        meta={
          terminal
            ? "Decision recorded"
            : `${allowed.length} permitted ${allowed.length === 1 ? "move" : "moves"} from ${STATUS_META[application.status].label}`
        }
      />

      {terminal ? (
        <div className="mt-3 border border-rule bg-panel px-4 py-3.5">
          <p className="text-sm text-ink">
            {STATUS_META[application.status].label}
            {application.decided_at ? ` on ${formatDate(application.decided_at)}` : ""}
          </p>
          {application.decision_remarks ? (
            <p className="mt-1.5 max-w-prose text-xs leading-relaxed text-ink-soft">
              {application.decision_remarks}
            </p>
          ) : null}
          <p className="mt-2 text-2xs text-ink-faint">
            Terminal dockets cannot move again. The audit chain is sealed.
          </p>
        </div>
      ) : (
        <div className="mt-3 space-y-3 border border-rule bg-panel px-4 py-4">
          <div>
            <label htmlFor="decision-note" className="text-xs font-medium text-ink">
              Decision note{" "}
              <span className="font-normal text-ink-faint">
                (optional, written to the audit trail)
              </span>
            </label>
            <textarea
              id="decision-note"
              rows={2}
              value={remarks}
              onChange={(event) => setRemarks(event.target.value)}
              placeholder="Reason for this move, site observations, or conditions imposed."
              className="mt-1.5 w-full resize-y border border-rule bg-paper px-2.5 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-teal focus:outline-none"
            />
          </div>

          {actionError ? (
            <div role="alert" className="border border-seal/30 bg-seal-soft/70 px-2.5 py-2 text-xs text-ink">
              {actionError}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            {allowed.length === 0 ? (
              <p className="text-xs text-ink-soft">
                No transition is available from this stage.
              </p>
            ) : null}

            {allowed.map((toStatus) => {
              const isReject = toStatus === "rejected";
              const rejectBlocked = isReject && remarks.trim().length === 0;
              const pending =
                transition.isPending && transition.variables?.toStatus === toStatus;

              return (
                <Button
                  key={toStatus}
                  variant={isReject ? "outline" : "primary"}
                  size="sm"
                  disabled={transition.isPending || rejectBlocked}
                  title={
                    rejectBlocked
                      ? "Add a decision note before rejecting the docket."
                      : undefined
                  }
                  onClick={() => void move(toStatus)}
                  className={cn(
                    isReject &&
                      "border-seal/40 text-seal hover:border-seal/60 hover:bg-seal-soft",
                  )}
                >
                  {pending ? (
                    <Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" />
                  ) : null}
                  {TRANSITION_LABEL[toStatus]}
                </Button>
              );
            })}
          </div>

          {application.status === "scrutiny" ? (
            <p className="text-2xs text-ink-soft">
              Leaving scrutiny re-runs the live-lease check; a failing lease returns a
              block with the verdict attached.
            </p>
          ) : null}
          <p className="text-2xs text-ink-faint">
            Every move is signed into the SHA-256 audit chain under your officer ID.
          </p>
        </div>
      )}
    </section>
  );
}
