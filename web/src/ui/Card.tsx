import type { HTMLAttributes, ReactNode } from "react";

export function Card({
  children,
  className = "",
  elevated,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { children: ReactNode; elevated?: boolean }) {
  return (
    <div
      className={`rounded-[20px] border border-line bg-surface ${elevated ? "shadow-hero" : ""} ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h2 className="text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-2">{children}</h2>
      {action}
    </div>
  );
}

export function PageTitle({ children, kicker, id }: { children: ReactNode; kicker?: ReactNode; id?: string }) {
  return (
    <header className="mb-6">
      {kicker ? <p className="mb-1 text-[15px] text-ink-2">{kicker}</p> : null}
      <h1 id={id} tabIndex={-1} className="text-[30px] font-semibold leading-[36px] tracking-tight outline-none">
        {children}
      </h1>
    </header>
  );
}
