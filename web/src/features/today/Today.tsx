import { ArrowRight, CalendarCheck, CaretRight } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { useMap } from "../map/useMap";
import { api, type NextResponse, type Suggestion } from "../../api/client";
import { signal } from "../../api/inspector";
import { useT, useLang } from "../../i18n/useT";
import type { Key } from "../../i18n/en";
import { dayLabel } from "../../lib/format";
import { useClock } from "../../session/clock";
import { useSession } from "../../session/session";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { Sheet } from "../../ui/Sheet";
import { ErrorState, Skeleton } from "../../ui/States";
import { announce } from "../../ui/Toast";
import { PERSONA_COPY } from "../entry/personas";
import { plans, usePlans } from "../plan/plans";
import { cleanTitle, StepCard } from "./StepCard";
import { SupportFirst } from "./SupportFirst";
import { WhySheet } from "./WhySheet";
import { AskLauncher } from "../ask/AskLauncher";

export function Today() {
  const t = useT();
  const lang = useLang();
  const nav = useNavigate();
  const qc = useQueryClient();
  const s = useSession();
  const now = useClock();
  const map = useMap();
  const next = useQuery({ queryKey: ["next"], queryFn: api.next, enabled: !!map.data?.profile.focus || map.data?.care_first });
  const [heroIdx, setHeroIdx] = useState(0);
  const [whyOpen, setWhyOpen] = useState(false);
  const [declineOpen, setDeclineOpen] = useState(false);
  const [showEvents, setShowEvents] = useState(false);
  const planList = usePlans();
  const pending = planList.find(p => p.status === "planned") ?? null;

  // once something is planned, don't offer the same thing again; keep the other options visible
  const all: Suggestion[] = (next.data ? [next.data.pick, ...next.data.alternates] : []).filter(
    x => !pending || x.item.id !== pending.commitment.item.id,
  );
  const planOnly = !!pending && !!next.data && all.length < 1 + next.data.alternates.length;
  const hero = all[heroIdx] ?? all[0] ?? null;
  const others = planOnly ? all : all.filter(x => x !== hero);

  useEffect(() => setHeroIdx(0), [next.data?.set_id]);
  useEffect(() => {
    if (hero) signal("next:shown", hero);
  }, [hero?.rec_id]);

  const commit = useMutation({
    mutationFn: (recId: number) => api.commit(recId),
    onSuccess: c => {
      plans.add(c);
      signal("commitment:created", c);
      announce(t("plan.title"));
      nav(`/plan/${c.commitment_id}`);
    },
  });

  const decline = useMutation({
    mutationFn: ({ recId, reason }: { recId: number; reason: "swap" | "not_now" }) => api.decline(recId, reason),
    onSuccess: (data: NextResponse) => {
      qc.setQueryData(["next"], data);
      setDeclineOpen(false);
      signal("decline:done");
      announce(cleanTitle(data.pick.item.title));
    },
  });

  if (map.data && !map.data.profile.focus && !map.data.care_first) return <Navigate to="/focus" replace />;

  const name = s && s.persona !== "staff" ? PERSONA_COPY[s.persona].name : "";
  const focus = map.data?.profile.focus;

  return (
    <div>
      <header className="mb-5">
        <p className="text-[15px] text-ink-2">{now ? t("today.greeting", { day: dayLabel(now, lang), name }) : " "}</p>
        <h1 tabIndex={-1} className="display mt-1 text-[38px] leading-[1.05] outline-none">
          {map.data?.care_first ? t("today.titleCare") : t("today.title")}
        </h1>
        {focus ? (
          <Link
            to="/focus"
            data-tour="focus-chip"
            className="mt-3 inline-flex h-9 items-center gap-1.5 rounded-full bg-surface-2 px-3 text-[14px] font-medium"
          >
            {t("today.growing", { area: t(`dim.${focus}` as Key) })}
            <span className="text-ink-2">· {t("today.change")}</span>
          </Link>
        ) : null}
      </header>

      {pending ? <PendingPlan rec={pending.commitment} /> : null}

      {next.isPending && (map.data?.profile.focus || map.data?.care_first) ? <TodaySkeleton /> : null}
      {next.isError ? <ErrorState error={next.error} onRetry={() => next.refetch()} /> : null}

      {next.data ? (
        next.data.care_first && next.data.support_card ? (
          <div className="flex flex-col gap-4">
            <SupportFirst card={next.data.support_card} />
            {!showEvents ? (
              <Button variant="ghost" size="md" onClick={() => setShowEvents(true)}>
                {t("support.more")}
              </Button>
            ) : (
              hero && (
                <StepCard
                  s={hero}
                  label={t("today.others")}
                  onCommit={() => commit.mutate(hero.rec_id)}
                  committing={commit.isPending}
                  onWhy={() => {
                    setWhyOpen(true);
                    signal("why:opened");
                  }}
                  onDecline={() => setDeclineOpen(true)}
                />
              )
            )}
          </div>
        ) : (
          hero && !planOnly && (
              <StepCard
                key={hero.rec_id}
                s={hero}
                onCommit={() => commit.mutate(hero.rec_id)}
                committing={commit.isPending}
                onWhy={() => {
                  setWhyOpen(true);
                  signal("why:opened");
                }}
                onDecline={() => setDeclineOpen(true)}
              />
          )
        )
      ) : null}

      {commit.isError ? (
        <p role="alert" className="mt-3 text-[15px] text-scarlet-ink">
          {(commit.error as Error).message}
        </p>
      ) : null}

      {next.data && others.length && (!next.data.care_first || showEvents) ? (
        <section className="mt-8" aria-labelledby="others">
          <h2 id="others" className="mb-3 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-2">
            {t("today.others")}
          </h2>
          <ul className="overflow-hidden rounded-[20px] border border-line bg-surface">
            {others.map((o, i) => (
              <li key={o.rec_id} className={i ? "border-t border-line" : ""}>
                <button
                  type="button"
                  onClick={() => setHeroIdx(all.indexOf(o))}
                  className="flex w-full items-center gap-3 px-4 py-3.5 text-left hover:bg-surface-2 cursor-pointer"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-[16px] font-medium leading-snug">{cleanTitle(o.item.title)}</span>
                    <span className="block text-[14px] text-ink-2">
                      {o.when_label} · {o.cost_label}
                    </span>
                  </span>
                  <CaretRight size={18} className="shrink-0 text-ink-2" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <AskLauncher className="mt-8" />

      <WhySheet s={hero} open={whyOpen} onClose={() => setWhyOpen(false)} />
      <Sheet open={declineOpen} onClose={() => setDeclineOpen(false)} title={t("decline.title")}>
        <div className="flex flex-col gap-2 pt-2">
          <Button
            variant="secondary"
            block
            loading={decline.isPending && decline.variables?.reason === "swap"}
            onClick={() => hero && decline.mutate({ recId: hero.rec_id, reason: "swap" })}
          >
            {t("decline.swap")}
          </Button>
          <Button
            variant="ghost"
            block
            loading={decline.isPending && decline.variables?.reason === "not_now"}
            onClick={() => hero && decline.mutate({ recId: hero.rec_id, reason: "not_now" })}
          >
            {t("decline.notNow")}
          </Button>
        </div>
      </Sheet>
    </div>
  );
}

function PendingPlan({ rec }: { rec: { commitment_id: number; item: { title: string }; when_label: string } }) {
  const t = useT();
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mb-5">
      <Link to={`/plan/${rec.commitment_id}`} data-tour="pending-plan">
        <Card className="flex items-center gap-3 px-4 py-3.5 hover:bg-surface-2">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-green-tint text-green">
            <CalendarCheck size={20} aria-hidden />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] font-semibold uppercase tracking-[0.06em] text-green">{t("today.planned")}</span>
            <span className="block truncate text-[16px] font-medium">{cleanTitle(rec.item.title)}</span>
            <span className="block text-[14px] text-ink-2">{rec.when_label}</span>
          </span>
          <ArrowRight size={18} className="shrink-0 text-ink-2" aria-hidden />
        </Card>
      </Link>
    </motion.div>
  );
}

function TodaySkeleton() {
  return (
    <div aria-hidden="true" className="rounded-[20px] border border-line bg-surface p-5">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="mt-4 h-7 w-4/5" />
      <div className="mt-5 flex flex-col gap-3">
        {[0, 1, 2, 3, 4].map(i => (
          <Skeleton key={i} className="h-5 w-3/4" />
        ))}
      </div>
      <Skeleton className="mt-6 h-14 w-full rounded-2xl" />
    </div>
  );
}

