import { WarningCircle } from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { useT } from "../i18n/useT";
import { Button } from "./Button";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-surface-2 ${className}`} aria-hidden="true" />;
}

export function LoadingBlock({ label, children }: { label?: string; children: ReactNode }) {
  const t = useT();
  return (
    <div role="status" aria-label={label ?? t("common.loading")}>
      {children}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const t = useT();
  const msg = error instanceof Error ? error.message : String(error ?? "");
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-[20px] border border-line bg-surface p-5">
      <div className="flex items-center gap-2 font-semibold">
        <WarningCircle size={20} className="text-amber" aria-hidden />
        {t("error.title")}
      </div>
      {msg ? <p className="text-[15px] text-ink-2">{msg}</p> : null}
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {t("common.retry")}
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({ icon, children, action }: { icon?: ReactNode; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-[20px] border border-dashed border-line px-6 py-8 text-center text-[15px] text-ink-2">
      {icon}
      <p>{children}</p>
      {action}
    </div>
  );
}
