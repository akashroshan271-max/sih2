import { cn } from "@/lib/utils";

export function SlaStamp({
  days,
  className,
}: {
  days: number;
  className?: string;
}) {
  return (
    <span
      title={`${Math.floor(days)} days in this stage — past the dwell limit`}
      className={cn(
        "inline-block shrink-0 -rotate-2 border border-seal/60 px-1.5 py-[1px] text-2xs font-semibold uppercase leading-4 tracking-[0.12em] text-seal",
        className,
      )}
    >
      SLA +{Math.floor(days)}d
    </span>
  );
}
