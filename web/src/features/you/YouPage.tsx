import { Brain, CaretRight, Trash, BellRinging, IdentificationCard, Warning } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, type MemoryList } from "../../api/client";
import { signal } from "../../api/inspector";
import { useLang, useT } from "../../i18n/useT";
import { shortDate } from "../../lib/format";
import { enablePush, pushPermission } from "../../push/push";
import { session } from "../../session/session";
import { PageTitle, SectionTitle } from "../../ui/Card";
import { ErrorState, Skeleton } from "../../ui/States";
import { announce, toast } from "../../ui/Toast";
import { plans, usePlans } from "../plan/plans";
import { cleanTitle } from "../today/StepCard";

export function YouPage() {
  const t = useT();
  const lang = useLang();
  const qc = useQueryClient();
  const nav = useNavigate();
  const memory = useQuery({ queryKey: ["memory"], queryFn: api.memory });
  const myPlans = usePlans();
  const [push, setPush] = useState(pushPermission() === "granted");

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteMemory(id),
    onMutate: async id => {
      await qc.cancelQueries({ queryKey: ["memory"] });
      const prev = qc.getQueryData<MemoryList>(["memory"]);
      if (prev) qc.setQueryData<MemoryList>(["memory"], { ...prev, items: prev.items.filter(i => i.id !== id) });
      return { prev };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(["memory"], ctx.prev);
      toast(t("common.retry"), "amber");
    },
    onSuccess: () => {
      signal("memory:deleted");
      announce(t("you.remove"));
      void qc.invalidateQueries({ queryKey: ["next"] });
    },
  });

  const removeAll = useMutation({
    mutationFn: api.deleteAllMemory,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["memory"] });
      void qc.invalidateQueries({ queryKey: ["next"] });
      signal("memory:deleted");
    },
  });

  const forget = useMutation({
    mutationFn: api.forgetMe,
    onSuccess: () => {
      plans.clear();
      qc.clear();
      session.clear();
      nav("/", { replace: true });
    },
  });

  return (
    <div>
      <PageTitle>{t("you.title")}</PageTitle>

      <section className="mb-8">
        <SectionTitle>{t("you.plans")}</SectionTitle>
        {myPlans.length ? (
          <ul className="overflow-hidden rounded-[20px] border border-line bg-surface">
            {myPlans.map((p, i) => (
              <li key={p.commitment.commitment_id} className={i ? "border-t border-line" : ""}>
                <Link
                  to={p.status === "planned" ? `/plan/${p.commitment.commitment_id}` : `/followup/${p.commitment.commitment_id}`}
                  className="flex items-center gap-3 px-4 py-3.5 hover:bg-surface-2"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-[16px] font-medium">{cleanTitle(p.commitment.item.title)}</span>
                    <span className="block text-[14px] text-ink-2">{p.commitment.when_label}</span>
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[12px] font-semibold ${
                      p.status === "went" ? "bg-green-tint text-green" : p.status === "missed" ? "bg-surface-2 text-ink-2" : "bg-scarlet-tint text-scarlet-ink"
                    }`}
                  >
                    {p.status === "went" ? t("plan.went") : p.status === "missed" ? "—" : t("plan.title")}
                  </span>
                  <CaretRight size={16} className="text-ink-2" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[15px] text-ink-2">{t("you.plansNone")}</p>
        )}
      </section>

      <section className="mb-8" aria-labelledby="mem-h" data-tour="memory">
        <SectionTitle
          action={
            memory.data?.items.length ? (
              <button
                type="button"
                onClick={() => window.confirm(t("you.removeAllConfirm")) && removeAll.mutate()}
                className="text-[14px] font-medium text-scarlet-ink hover:underline cursor-pointer"
              >
                {t("you.removeAll")}
              </button>
            ) : null
          }
        >
          <span id="mem-h">{t("you.memory")}</span>
        </SectionTitle>
        <p className="-mt-1 mb-3 text-[15px] text-ink-2">{t("you.memoryHelp")}</p>
        {memory.isPending ? <Skeleton className="h-40" /> : null}
        {memory.isError ? <ErrorState error={memory.error} onRetry={() => memory.refetch()} /> : null}
        {memory.data ? (
          memory.data.items.length ? (
            <ul className="overflow-hidden rounded-[20px] border border-line bg-surface">
              <AnimatePresence initial={false}>
                {memory.data.items.map((m, i) => (
                  <motion.li
                    key={m.id}
                    layout
                    exit={{ opacity: 0, height: 0, transition: { duration: 0.2 } }}
                    className={`flex items-start gap-3 px-4 py-3.5 ${i ? "border-t border-line" : ""}`}
                  >
                    <Brain size={20} className="mt-0.5 shrink-0 text-scarlet-ink" aria-hidden />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[16px] font-medium leading-snug">{m.statement}</span>
                      <span className="block text-[14px] text-ink-2">
                        {m.source.label}
                        {m.source.at ? ` · ${shortDate(m.source.at, lang)}` : ""}
                      </span>
                      <span className="block text-[13px] text-ink-2">{t("you.usedFor", { x: m.used_for })}</span>
                    </span>
                    {m.deletable ? (
                      <button
                        type="button"
                        onClick={() => !remove.isPending && remove.mutate(m.id)}
                        aria-label={`${t("you.remove")}: ${m.statement}`}
                        data-tour={`forget-${m.id}`}
                        className="-mr-2 inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-ink-2 hover:bg-surface-2 hover:text-scarlet-ink cursor-pointer"
                      >
                        <Trash size={19} aria-hidden />
                      </button>
                    ) : null}
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          ) : (
            <p className="text-[15px] text-ink-2">{t("you.memoryNone")}</p>
          )
        ) : null}
      </section>

      <section className="mb-8 flex flex-col gap-2">
        <button
          type="button"
          onClick={async () => {
            const r = await enablePush();
            setPush(r === "on");
            if (r !== "on") toast(t("plan.remindersBlocked"), "amber");
          }}
          className="flex min-h-14 items-center gap-3 rounded-[20px] border border-line bg-surface px-4 py-3 text-left hover:bg-surface-2 cursor-pointer"
          data-tour="you-reminders"
        >
          <BellRinging size={22} className="shrink-0" aria-hidden />
          <span className="flex-1 text-[16px] font-medium">{t("you.notifications")}</span>
          <span className={`text-[14px] font-semibold ${push ? "text-green" : "text-ink-2"}`}>{push ? "On" : "Off"}</span>
        </button>
        <Link to="/card" className="flex min-h-14 items-center gap-3 rounded-[20px] border border-line bg-surface px-4 py-3 hover:bg-surface-2">
          <IdentificationCard size={22} className="shrink-0" aria-hidden />
          <span className="flex-1 text-[16px] font-medium">{t("you.card")}</span>
          <CaretRight size={16} className="text-ink-2" aria-hidden />
        </Link>
      </section>

      <section className="rounded-[20px] border border-scarlet/30 p-4">
        <p className="flex items-center gap-2 text-[15px] text-ink-2">
          <Warning size={18} aria-hidden />
          {t("you.forgetHelp")}
        </p>
        <button
          type="button"
          disabled={forget.isPending}
          onClick={() => window.confirm(t("you.forgetConfirm")) && forget.mutate()}
          className="mt-3 h-12 w-full rounded-xl border border-scarlet/50 text-[16px] font-medium text-scarlet-ink hover:bg-scarlet-tint cursor-pointer disabled:opacity-50"
        >
          {t("you.forget")}
        </button>
      </section>
    </div>
  );
}
