import { cn } from "@/lib/utils";

type BadgeTone = "teal" | "turmeric" | "indigo" | "plum" | "seal" | "neutral";

const TONE_CLASS: Record<BadgeTone, string> = {
  teal: "border-teal/25 bg-teal-soft text-teal",
  turmeric: "border-turmeric/30 bg-turmeric-soft text-[#7a5408]",
  indigo: "border-indigo/25 bg-indigo-soft text-indigo",
  plum: "border-plum/25 bg-plum-soft text-plum",
  seal: "border-seal/30 bg-seal-soft text-seal",
  neutral: "border-rule bg-ink/[0.04] text-ink-soft",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: BadgeTone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-[2px] border px-1.5 py-0.5 text-2xs font-medium leading-4",
        TONE_CLASS[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
