import { ArrowLeft, ArrowRight, CalendarBlank, Envelope, GraduationCap, House, Receipt } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../api/client";
import { useT } from "../../i18n/useT";
import { LogoMark } from "../../ui/Logo";
import { Skeleton } from "../../ui/States";
import { cleanTitle } from "../today/StepCard";

/** A neutral portal mock (no Rutgers marks) showing where the /me/card tile would live. Clearly labelled. */
export function CardPage() {
  const t = useT();
  const card = useQuery({ queryKey: ["card"], queryFn: api.card });
  const tiles = [
    { icon: <GraduationCap size={22} aria-hidden />, label: "Courses" },
    { icon: <Receipt size={22} aria-hidden />, label: "Billing" },
    { icon: <Envelope size={22} aria-hidden />, label: "Email" },
    { icon: <House size={22} aria-hidden />, label: "Housing" },
  ];
  return (
    <div>
      <Link to="/you" className="-ml-2 mb-3 inline-flex h-11 items-center gap-1.5 rounded-full px-2 text-[15px] text-ink-2 hover:bg-surface-2">
        <ArrowLeft size={18} aria-hidden />
        {t("tab.you")}
      </Link>
      <h1 tabIndex={-1} className="text-[26px] font-semibold tracking-tight outline-none">
        {t("you.card")}
      </h1>
      <p className="mt-1 rounded-full bg-amber-tint px-3 py-1 text-[13px] font-medium text-amber">{t("card.label")}</p>

      <div className="mt-6 overflow-hidden rounded-[24px] border border-line bg-surface-2 p-3">
        <div className="mb-3 flex items-center justify-between px-1 text-[13px] font-semibold text-ink-2">
          <span>Student portal</span>
          <span>Mon</span>
        </div>
        <div className="rounded-[18px] border border-line bg-surface p-4 shadow-hero" data-tour="myrutgers-card">
          <div className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.08em] text-scarlet-ink">
            <LogoMark size={18} />
            Compass · your next step
          </div>
          {card.data ? (
            <>
              <p className="mt-2 text-[18px] font-semibold leading-snug">{cleanTitle(card.data.title)}</p>
              {card.data.when_label ? (
                <p className="mt-1 flex items-center gap-1.5 text-[14px] text-ink-2">
                  <CalendarBlank size={15} aria-hidden />
                  {card.data.when_label}
                </p>
              ) : null}
              <p className="mt-2 text-[15px] leading-snug text-ink-2">{card.data.line}</p>
              <Link
                to={card.data.deep_link}
                className="mt-3 inline-flex h-10 items-center gap-1.5 rounded-xl bg-scarlet px-3.5 text-[14px] font-medium text-on-scarlet"
              >
                {t("card.open")}
                <ArrowRight size={16} aria-hidden />
              </Link>
            </>
          ) : (
            <Skeleton className="mt-3 h-24" />
          )}
        </div>
        <div className="mt-3 grid grid-cols-4 gap-2">
          {tiles.map(x => (
            <div key={x.label} className="flex flex-col items-center gap-1 rounded-2xl bg-surface px-1 py-3 text-[12px] text-ink-2">
              {x.icon}
              {x.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
