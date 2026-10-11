import { ArrowDown, ArrowSquareOut, ArrowUp, Info } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useEffect } from "react";
import { signal } from "../../api/inspector";
import type { MapResponse } from "../../api/client";
import { useLang, useT } from "../../i18n/useT";
import type { Key } from "../../i18n/en";
import { score, shortDate } from "../../lib/format";
import { PageTitle } from "../../ui/Card";
import { DimensionIcon } from "../../ui/DimensionIcon";
import { ErrorState, Skeleton } from "../../ui/States";
import { useMap } from "./useMap";

const SCALE_MIN = 1;
const SCALE_MAX = 4;
const pos = (x: number) => Math.max(0.02, Math.min(1, (x - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)));

export function MapPage() {
  const t = useT();
  const lang = useLang();
  const map = useMap();
  useEffect(() => {
    if (map.data) signal("map:shown", map.data);
  }, [map.data?.latest.take_no]);

  if (map.isError) return <ErrorState error={map.error} onRetry={() => map.refetch()} />;
  const m = map.data;
  const prevDate = m?.previous_takes.length ? m.previous_takes[m.previous_takes.length - 1].taken_on : null;

  return (
    <div>
      <PageTitle kicker={m ? t("map.from", { date: shortDate(m.latest.taken_on, lang) }) : " "}>{t("map.title")}</PageTitle>

      {!m ? (
        <Skeleton className="h-96" />
      ) : (
        <>
          <ul className="overflow-hidden rounded-[20px] border border-line bg-surface" data-tour="wellness-rows">
            {m.dimensions.map((d, i) => (
              <DimRow key={d.dimension} d={d} i={i} prevDate={prevDate} />
            ))}
          </ul>

          <p className="mt-3 flex items-start gap-2 text-[14px] leading-snug text-ink-2">
            <Info size={16} className="mt-0.5 shrink-0" aria-hidden />
            {t("map.note")}
          </p>

          {m.retake_nudge?.show ? (
            <a
              href={m.retake_nudge.url}
              target="_blank"
              rel="noreferrer"
              className="mt-5 flex items-center gap-3 rounded-[20px] border border-line bg-surface px-4 py-4 hover:bg-surface-2"
            >
              <span className="min-w-0 flex-1 text-[15px]">{m.retake_nudge.message}</span>
              <ArrowSquareOut size={18} className="shrink-0 text-ink-2" aria-hidden />
            </a>
          ) : null}
        </>
      )}
    </div>
  );
}

function DimRow({ d, i, prevDate }: { d: MapResponse["dimensions"][number]; i: number; prevDate: string | null }) {
  const t = useT();
  const lang = useLang();
  const change = d.change ?? null;
  const from = change ? d.score - change : d.score;
  return (
    <li
      data-testid="dim-row"
      data-dimension={d.dimension}
      className={`px-4 py-3.5 ${i ? "border-t border-line" : ""}`}
    >
      <div className="flex items-center gap-3">
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
            d.band === "high" ? "bg-green-tint text-green" : "bg-surface-2 text-ink"
          }`}
        >
          <DimensionIcon dimension={d.dimension} size={19} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline gap-2">
            <span className="text-[16px] font-semibold">{d.label}</span>
            <span className="text-[13px] text-ink-2">{t(`band.${d.band}` as Key)}</span>
          </span>
        </span>
        <span className="text-[20px] font-semibold tabular">{score(d.score)}</span>
      </div>
      <div className="ml-12 mt-2">
        <div className="relative h-1.5 rounded-full bg-surface-2" aria-hidden="true">
          <motion.div
            className={`absolute inset-y-0 left-0 rounded-full ${d.band === "high" ? "bg-green" : "bg-ink"}`}
            initial={{ width: `${pos(from) * 100}%` }}
            animate={{ width: `${pos(d.score) * 100}%` }}
            transition={{ delay: change ? 0.6 : 0.1 + i * 0.03, duration: change ? 1.1 : 0.5, ease: [0.22, 1, 0.36, 1] }}
          />
        </div>
        {change ? (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.2 }}
            className={`mt-1.5 flex items-center gap-1 text-[14px] font-medium ${change > 0 ? "text-green" : "text-ink-2"}`}
          >
            {change > 0 ? <ArrowUp size={14} weight="bold" aria-hidden /> : <ArrowDown size={14} weight="bold" aria-hidden />}
            {score(Math.abs(change))} {prevDate ? t("map.since", { date: shortDate(prevDate, lang) }) : ""}
          </motion.p>
        ) : (
          <p className="mt-1 text-[14px] text-ink-2">{d.blurb}</p>
        )}
      </div>
    </li>
  );
}
