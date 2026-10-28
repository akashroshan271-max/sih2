"use client";

import { cn } from "@/lib/utils";

import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function DataError({
  error,
  onRetry,
  className,
  compact = false,
}: {
  error: unknown;
  onRetry?: () => void;
  className?: string;
  compact?: boolean;
}) {
  const message =
    error instanceof ApiError
      ? error.message
      : error instanceof Error
        ? error.message
        : "This data could not be loaded.";

  return (
    <div
      role="alert"
      className={cn(
        "border border-seal/30 bg-seal-soft/60 px-3 py-2.5",
        compact ? "text-xs" : "text-sm",
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="max-w-prose text-ink">{message}</p>
        {onRetry ? (
          <Button variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
      </div>
    </div>
  );
}

export function EmptyNote({
  title,
  hint,
  className,
}: {
  title: string;
  hint?: string;
  className?: string;
}) {
  return (
    <div className={cn("border border-dashed border-rule px-3 py-4", className)}>
      <p className="text-[13px] text-ink">{title}</p>
      {hint ? <p className="mt-0.5 text-2xs text-ink-soft">{hint}</p> : null}
    </div>
  );
}
