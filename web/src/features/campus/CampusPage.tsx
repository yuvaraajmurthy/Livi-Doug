import { HandsClapping, Trophy } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { api, type PulseResponse } from "../../api/client";
import { useLang, useT } from "../../i18n/useT";
import type { Key } from "../../i18n/en";
import { shortDate } from "../../lib/format";
import { Card, PageTitle, SectionTitle } from "../../ui/Card";
import { DimensionIcon } from "../../ui/DimensionIcon";
import { ErrorState, Skeleton } from "../../ui/States";
import { AskLauncher } from "../ask/AskLauncher";

export function CampusPage() {
  const t = useT();
  const lang = useLang();
  const qc = useQueryClient();
  const pulse = useQuery({ queryKey: ["pulse"], queryFn: api.pulse });

  const same = useMutation({
    mutationFn: (id: string) => api.sameHere(id),
    onMutate: async id => {
      await qc.cancelQueries({ queryKey: ["pulse"] });
      const prev = qc.getQueryData<PulseResponse>(["pulse"]);
      if (prev)
        qc.setQueryData<PulseResponse>(["pulse"], {
          ...prev,
          wins: prev.wins.map(w => (w.id === id ? { ...w, same_here: w.same_here + 1 } : w)),
        });
      return { prev };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(["pulse"], ctx.prev);
    },
    onSuccess: r =>
      qc.setQueryData<PulseResponse>(["pulse"], p =>
        p ? { ...p, wins: p.wins.map(w => (w.id === r.win_id ? { ...w, same_here: r.same_here } : w)) } : p,
      ),
  });

  return (
    <div>
      <PageTitle>{t("campus.title")}</PageTitle>
      {pulse.isError ? <ErrorState error={pulse.error} onRetry={() => pulse.refetch()} /> : null}
      {pulse.isPending ? <Skeleton className="h-64" /> : null}
      {pulse.data ? (
        <>
          <section className="mb-8" data-tour="challenges">
            <SectionTitle>{t("campus.challenges")}</SectionTitle>
            <ul className="flex flex-col gap-3">
              {pulse.data.challenges.map(c => (
                <li key={c.id}>
                  <Card className="px-4 py-4">
                    <div className="flex items-start gap-3">
                      <Trophy size={22} className="mt-0.5 shrink-0 text-scarlet-ink" aria-hidden />
                      <div className="min-w-0 flex-1">
                        <p className="text-[16px] font-semibold leading-snug">{c.title}</p>
                        <p className="text-[14px] text-ink-2">
                          {c.scope_label} · {shortDate(c.starts_on, lang)}–{shortDate(c.ends_on, lang)}
                        </p>
                        <div
                          className="mt-3 h-2.5 overflow-hidden rounded-full bg-surface-2"
                          role="progressbar"
                          aria-label={c.title}
                          aria-valuemin={0}
                          aria-valuemax={c.goal}
                          aria-valuenow={c.progress}
                        >
                          <motion.div
                            className="h-full rounded-full bg-scarlet"
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.max(1, c.pct * 100)}%` }}
                            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
                          />
                        </div>
                        <p className="mt-1.5 text-[13px] text-ink-2 tabular">
                          {c.progress} / {c.goal}
                        </p>
                        <p className="mt-2 text-[14px] leading-snug text-ink-2">{c.rule}</p>
                      </div>
                    </div>
                  </Card>
                </li>
              ))}
            </ul>
          </section>

          <section data-tour="wins">
            <SectionTitle>{t("campus.wins")}</SectionTitle>
            <p className="-mt-1 mb-3 text-[15px] text-ink-2">{t("campus.winsHelp")}</p>
            <ul className="flex flex-col gap-2.5">
              {pulse.data.wins.map(w => (
                <li key={w.id}>
                  <Card className="px-4 py-3.5">
                    <p className="text-[16px] leading-snug">“{w.text}”</p>
                    <div className="mt-2.5 flex items-center justify-between gap-2">
                      <span className="flex items-center gap-1.5 text-[13px] text-ink-2">
                        {w.dimension ? <DimensionIcon dimension={w.dimension} size={15} /> : null}
                        {w.campus ? t(`campus.${w.campus}` as Key) : ""}
                      </span>
                      <button
                        type="button"
                        onClick={() => same.mutate(w.id)}
                        aria-label={`${t("campus.sameHere")} (${w.same_here})`}
                        className="inline-flex h-10 items-center gap-1.5 rounded-full border border-line px-3 text-[14px] font-medium hover:bg-surface-2 cursor-pointer tabular"
                      >
                        <HandsClapping size={16} aria-hidden />
                        {t("campus.sameHere")} · {w.same_here}
                      </button>
                    </div>
                  </Card>
                </li>
              ))}
            </ul>
          </section>
          <AskLauncher className="mt-8" />
        </>
      ) : null}
    </div>
  );
}
