import { Bell, Clock } from "@phosphor-icons/react";
import { Link } from "react-router";
import { useT } from "../i18n/useT";
import { useClock } from "../session/clock";
import { useDataMode } from "../session/mode";
import { clockLabel } from "../lib/format";
import { useLang } from "../i18n/useT";
import { Wordmark } from "./Logo";

export function ClockPill({ onClick }: { onClick: () => void }) {
  const t = useT();
  const lang = useLang();
  const now = useClock();
  const { mode, templates } = useDataMode();
  const flag = mode === "replay" ? "Offline" : mode === "fixture" ? t("common.demoData") : templates ? "Templates" : null;
  return (
    <button
      type="button"
      onClick={onClick}
      data-tour="clock-pill"
      aria-label={`${t("clock.open")}: ${now ? clockLabel(now, lang) : ""}`}
      className="inline-flex h-9 items-center gap-1.5 whitespace-nowrap rounded-full border border-line bg-surface px-3 text-[13px] font-medium text-ink tabular cursor-pointer hover:bg-surface-2"
    >
      <Clock size={15} aria-hidden className="text-ink-2" />
      <span>{now ? (flag ? clockLabel(now, lang).replace(/^\w+ /, "") : clockLabel(now, lang)) : "…"}</span>
      {flag ? (
        <span className="ml-0.5 rounded-full bg-amber-tint px-1.5 text-[11px] font-semibold text-amber">{flag}</span>
      ) : null}
    </button>
  );
}

export function TopBar({ unread, onOpenTime }: { unread: number; onOpenTime: () => void }) {
  const t = useT();
  return (
    <header className="sticky top-0 z-20 border-b border-line/70 bg-bg/88 backdrop-blur-md safe-top">
      <div className="mx-auto flex h-14 max-w-[480px] items-center justify-between gap-2 px-4">
        <Link to="/next" aria-label="Compass home" className="-ml-1 rounded-lg p-1">
          <Wordmark />
        </Link>
        <div className="flex items-center gap-1">
          <ClockPill onClick={onOpenTime} />
          <Link
            to="/inbox"
            data-tour="inbox"
            aria-label={unread ? `${t("inbox.open")} (${unread})` : t("inbox.open")}
            className="relative inline-flex h-11 w-11 items-center justify-center rounded-full text-ink hover:bg-surface-2"
          >
            <Bell size={22} aria-hidden />
            {unread ? (
              <span className="absolute right-1.5 top-1.5 min-w-[18px] rounded-full bg-scarlet px-1 text-center text-[11px] font-semibold leading-[18px] text-on-scarlet tabular">
                {unread}
              </span>
            ) : null}
          </Link>
        </div>
      </div>
    </header>
  );
}
