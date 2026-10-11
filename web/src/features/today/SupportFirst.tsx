import { ArrowSquareOut, HandHeart, MapPin, Phone } from "@phosphor-icons/react";
import type { SupportCard } from "../../api/client";
import { useT } from "../../i18n/useT";
import { Card } from "../../ui/Card";

export function SupportFirst({ card }: { card: SupportCard }) {
  const t = useT();
  return (
    <Card elevated className="px-5 py-5" data-testid="support-card" data-tour="support-card">
      <span className="inline-flex items-center gap-1.5 text-[13px] font-semibold uppercase tracking-[0.08em] text-scarlet-ink">
        <HandHeart size={16} aria-hidden />
        {t("today.yourStep")}
      </span>
      <h2 className="mt-2 text-[24px] font-semibold leading-[30px] tracking-tight">{card.title}</h2>
      <p className="mt-2 text-[16px] leading-6 text-ink-2">{card.message}</p>
      <ul className="mt-5 flex flex-col gap-3">
        {card.options.map(o => (
          <li key={o.name} className="rounded-2xl border border-line p-4">
            <p className="text-[17px] font-semibold leading-snug">{o.name}</p>
            {o.hours ? <p className="mt-0.5 text-[15px] text-ink-2">{o.hours}</p> : null}
            {o.address ? (
              <p className="mt-1 flex items-start gap-1.5 text-[14px] text-ink-2">
                <MapPin size={16} className="mt-0.5 shrink-0" aria-hidden />
                {o.address}
              </p>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              {o.contact ? (
                <a
                  href={`tel:${o.contact}`}
                  className="inline-flex h-11 items-center gap-2 rounded-xl bg-scarlet px-4 text-[15px] font-medium text-on-scarlet"
                >
                  <Phone size={18} aria-hidden />
                  {t("support.call")} {o.contact}
                </a>
              ) : null}
              {o.url ? (
                <a
                  href={o.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-11 items-center gap-2 rounded-xl border border-line-strong px-4 text-[15px] font-medium"
                >
                  {t("support.open")}
                  <ArrowSquareOut size={16} aria-hidden />
                </a>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
