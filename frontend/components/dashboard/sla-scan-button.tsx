"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { useSlaScan } from "@/lib/queries/use-dashboard";
import { formatNumber } from "@/lib/utils";

export function SlaScanButton() {
  const scan = useSlaScan();

  function runScan() {
    scan.mutate(undefined, {
      onSuccess: (result) => {
        if (result.escalated > 0) {
          toast.success(`${formatNumber(result.escalated)} dockets escalated`, {
            description: `${formatNumber(result.checked)} active dockets checked · ${formatNumber(result.overdue)} past the stage limit.`,
          });
        } else {
          toast("No new escalations", {
            description: `${formatNumber(result.checked)} active dockets checked · ${formatNumber(result.overdue)} already past the limit.`,
          });
        }
      },
      onError: (error) => {
        toast.error("The sweep did not run", {
          description:
            error instanceof ApiError
              ? error.message
              : "The escalation sweep could not be completed.",
        });
      },
    });
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={runScan}
      disabled={scan.isPending}
    >
      {scan.isPending ? (
        <Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <RefreshCw aria-hidden className="h-3.5 w-3.5" />
      )}
      {scan.isPending ? "Sweeping" : "Run SLA sweep"}
    </Button>
  );
}
