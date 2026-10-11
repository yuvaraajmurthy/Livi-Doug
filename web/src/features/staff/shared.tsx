import { LockSimple } from "@phosphor-icons/react";
import type { ReactNode } from "react";

export const CAMPUS_LABEL: Record<string, string> = {
  new_brunswick: "New Brunswick",
  newark: "Newark",
  camden: "Camden",
  online: "Online",
  community: "Community",
};
export const cap = (s: string) => s[0].toUpperCase() + s.slice(1);

export function SuppressedRow({ children }: { children?: ReactNode }) {
  return (
    <div data-suppressed className="hatch flex items-center gap-2 rounded-xl border border-dashed border-line px-3 py-2.5 text-[14px] text-ink-2">
      <LockSimple size={16} aria-hidden />
      <span className="font-medium">Under 10</span>
      {children ? <span>· {children}</span> : null}
    </div>
  );
}

export function SuppressionNote({ n, min }: { n: number; min: number }) {
  if (!n) return null;
  return (
    <p className="mt-3 flex items-center gap-2 text-[14px] text-ink-2" data-tour="staff-suppression">
      <LockSimple size={16} aria-hidden />
      {n} groups hidden (fewer than {min} students). The database never returns them; this page can't either.
    </p>
  );
}

export function Panel({ title, sub, children, action }: { title: string; sub?: ReactNode; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="mb-8 rounded-[20px] border border-line bg-surface p-5 lg:p-6">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-[19px] font-semibold tracking-tight">{title}</h2>
          {sub ? <p className="mt-0.5 text-[14px] text-ink-2">{sub}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function HBar({ value, max, label, tone = "ink" }: { value: number; max: number; label: string; tone?: "ink" | "scarlet" | "green" }) {
  const color = tone === "scarlet" ? "bg-scarlet" : tone === "green" ? "bg-green" : "bg-ink";
  return (
    <div className="flex items-center gap-3">
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.max(1.5, (value / max) * 100)}%` }} />
      </div>
      <span className="w-16 shrink-0 text-right text-[14px] font-semibold tabular">{label}</span>
    </div>
  );
}

export function NothingToShow({ min }: { min: number }) {
  return (
    <div data-suppressed className="hatch flex items-start gap-3 rounded-2xl border border-dashed border-line px-4 py-5" data-tour="staff-empty">
      <LockSimple size={22} className="mt-0.5 shrink-0" aria-hidden />
      <div>
        <p className="text-[16px] font-semibold">No group of {min} or more matches these filters.</p>
        <p className="mt-1 text-[14px] text-ink-2">
          Smaller groups exist but are never returned. The database refuses the query, so no screen, export or question
          can show them.
        </p>
      </div>
    </div>
  );
}
