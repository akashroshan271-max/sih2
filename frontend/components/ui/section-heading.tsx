import { cn } from "@/lib/utils";

export function SectionHeading({
  id,
  title,
  meta,
  action,
  className,
}: {
  id?: string;
  title: string;
  meta?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-rule pb-2",
        className,
      )}
    >
      <h2 id={id} className="font-serif text-lg leading-snug text-ink">
        {title}
      </h2>
      {(meta || action) && (
        <div className="flex items-baseline gap-3">
          {meta ? <p className="text-xs text-ink-soft">{meta}</p> : null}
          {action}
        </div>
      )}
    </div>
  );
}
