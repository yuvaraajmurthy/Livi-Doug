import { ArrowLeft, Check } from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { api, DIMENSIONS, isCrisis, type CrisisResponse, type Dimension, type MapResponse } from "../../api/client";
import { inspector, signal } from "../../api/inspector";
import { useLang, useT } from "../../i18n/useT";
import type { Key } from "../../i18n/en";
import { score, shortDate } from "../../lib/format";
import { Button } from "../../ui/Button";
import { Chip } from "../../ui/Chip";
import { DimensionIcon } from "../../ui/DimensionIcon";
import { ErrorState, Skeleton } from "../../ui/States";
import { CrisisScreen } from "../safety/CrisisScreen";

type Step = 0 | 1 | 2 | 3;
const slide = {
  initial: { opacity: 0, x: 24 },
  animate: { opacity: 1, x: 0, transition: { type: "spring" as const, stiffness: 380, damping: 36 } },
  exit: { opacity: 0, x: -16, transition: { duration: 0.14 } },
};

export function FocusFlow() {
  const t = useT();
  const nav = useNavigate();
  const map = useQuery({ queryKey: ["map"], queryFn: api.map });
  const [step, setStep] = useState<Step>(0);
  const [dimension, setDimension] = useState<Dimension | null>(null);
  const [barriers, setBarriers] = useState<string[]>([]);
  const [crisis, setCrisis] = useState<CrisisResponse | null>(null);

  useEffect(() => {
    if (map.data?.profile.focus && dimension === null) setDimension(map.data.profile.focus as Dimension);
    if (map.data?.profile.barriers.length && barriers.length === 0) setBarriers(map.data.profile.barriers);
  }, [map.data]);

  if (crisis) return <CrisisScreen crisis={crisis} onBack={() => { setCrisis(null); setStep(2); }} />;

  return (
    <div className="mx-auto flex min-h-dvh max-w-[480px] flex-col px-5 pb-[calc(24px+env(safe-area-inset-bottom))] pt-[max(12px,env(safe-area-inset-top))] max-[359px]:px-4">
      {step < 3 ? (
        <div className="flex h-14 items-center justify-between">
          <button
            type="button"
            onClick={() => (step === 0 ? nav(-1) : setStep((step - 1) as Step))}
            aria-label={t("common.back")}
            className="-ml-2 inline-flex h-11 w-11 items-center justify-center rounded-full hover:bg-surface-2 cursor-pointer"
          >
            <ArrowLeft size={22} aria-hidden />
          </button>
          <div className="flex items-center gap-1.5" aria-label={t("focus.step", { n: step + 1 })} role="img">
            {[0, 1, 2].map(i => (
              <span
                key={i}
                className={`h-1.5 rounded-full transition-all duration-300 ${i === step ? "w-6 bg-ink" : i < step ? "w-1.5 bg-ink" : "w-1.5 bg-line"}`}
              />
            ))}
          </div>
          <span className="w-11" />
        </div>
      ) : null}

      {map.isError ? <ErrorState error={map.error} onRetry={() => map.refetch()} /> : null}
      {!map.data && !map.isError ? <Skeleton className="mt-8 h-64" /> : null}

      {map.data ? (
        <AnimatePresence mode="wait">
          {step === 0 ? (
            <motion.section key="s0" {...slide} className="flex flex-1 flex-col">
              <Strengths map={map.data} onNext={() => setStep(1)} />
            </motion.section>
          ) : step === 1 ? (
            <motion.section key="s1" {...slide} className="flex flex-1 flex-col">
              <PickArea map={map.data} value={dimension} onChange={setDimension} onNext={() => setStep(2)} />
            </motion.section>
          ) : step === 2 ? (
            <motion.section key="s2" {...slide} className="flex flex-1 flex-col">
              <Barriers
                dimension={dimension!}
                value={barriers}
                onChange={setBarriers}
                onSubmitted={r => (isCrisis(r) ? setCrisis(r) : setStep(3))}
              />
            </motion.section>
          ) : (
            <motion.section key="s3" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-1 flex-col">
              <Finding onDone={() => nav("/next", { replace: true })} />
            </motion.section>
          )}
        </AnimatePresence>
      ) : null}
    </div>
  );
}

function Strengths({ map, onNext }: { map: MapResponse; onNext: () => void }) {
  const t = useT();
  const lang = useLang();
  const byDim = Object.fromEntries(map.dimensions.map(d => [d.dimension, d]));
  return (
    <>
      <p className="mt-4 text-[15px] text-ink-2">{t("focus.strengths.kicker", { date: shortDate(map.latest.taken_on, lang) })}</p>
      <h1 tabIndex={-1} className="display mt-1 text-[40px] leading-[1.05] outline-none">
        {t("focus.strengths.title")}
      </h1>
      <ul className="mt-7 flex flex-col gap-3">
        {map.strengths.map((d, i) => (
          <motion.li
            key={d}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.12 }}
            className="flex items-center gap-4 rounded-[20px] border border-line bg-surface px-4 py-4"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-green-tint text-green">
              <DimensionIcon dimension={d} size={24} />
            </span>
            <span className="flex-1">
              <span className="block text-[18px] font-semibold">{byDim[d]?.label}</span>
              <span className="block text-[15px] text-ink-2">{byDim[d]?.blurb}</span>
            </span>
            <span className="text-[22px] font-semibold tabular">{score(byDim[d]?.score ?? 0)}</span>
          </motion.li>
        ))}
      </ul>
      {map.growth_areas.length ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }} className="mt-7">
          <h2 className="mb-2 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-2">{t("focus.strengths.grow")}</h2>
          <ul className="flex flex-col">
            {map.growth_areas.map(d => (
              <li key={d} className="flex items-center gap-3 border-b border-line py-3 last:border-0">
                <DimensionIcon dimension={d} size={20} className="text-ink-2" />
                <span className="flex-1 text-[16px]">{byDim[d]?.label}</span>
                <span className="text-[16px] text-ink-2 tabular">{score(byDim[d]?.score ?? 0)}</span>
              </li>
            ))}
          </ul>
        </motion.div>
      ) : null}
      <div className="mt-auto pt-8">
        <Button block onClick={onNext} data-tour="strengths-cta">
          {t("focus.strengths.cta")}
        </Button>
      </div>
    </>
  );
}

function PickArea({
  map,
  value,
  onChange,
  onNext,
}: {
  map: MapResponse;
  value: Dimension | null;
  onChange: (d: Dimension) => void;
  onNext: () => void;
}) {
  const t = useT();
  const grow = new Set(map.growth_areas);
  return (
    <>
      <h1 tabIndex={-1} className="mt-4 text-[30px] font-semibold leading-[36px] tracking-tight outline-none">
        {t("focus.pick.title")}
      </h1>
      <p className="mt-2 text-[16px] text-ink-2">{t("focus.pick.hint")}</p>
      <div className="mt-6 grid grid-cols-2 gap-2.5">
        {DIMENSIONS.map(d => {
          const on = value === d;
          return (
            <button
              key={d}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(d)}
              data-tour={`pick-${d}`}
              className={
                "relative flex min-h-[76px] flex-col items-start justify-between gap-2 rounded-2xl border p-3.5 text-left transition-colors cursor-pointer " +
                (on
                  ? "border-ink bg-ink text-bg"
                  : grow.has(d)
                    ? "border-scarlet/40 bg-scarlet-tint hover:border-scarlet/70"
                    : "border-line bg-surface hover:bg-surface-2")
              }
            >
              <span className="flex w-full items-center justify-between">
                <DimensionIcon dimension={d} size={22} />
                {on ? <Check size={18} weight="bold" aria-hidden /> : null}
              </span>
              <span className="text-[16px] font-medium">{t(`dim.${d}` as Key)}</span>
              {grow.has(d) && !on ? (
                <span className="absolute right-3 top-3 text-[11px] font-semibold uppercase tracking-wide text-scarlet-ink">
                  {t("focus.pick.suggested")}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
      <div className="mt-auto pt-8">
        <Button block disabled={!value} onClick={onNext} data-tour="pick-continue">
          {t("common.continue")}
        </Button>
      </div>
    </>
  );
}

function Barriers({
  dimension,
  value,
  onChange,
  onSubmitted,
}: {
  dimension: Dimension;
  value: string[];
  onChange: (b: string[]) => void;
  onSubmitted: (r: Awaited<ReturnType<typeof api.focus>>) => void;
}) {
  const t = useT();
  const lang = useLang();
  const qc = useQueryClient();
  const meta = useQuery({ queryKey: ["barriers"], queryFn: api.barriers, staleTime: Infinity });
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);

  async function submit() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError(null);
    try {
      const r = await api.focus({ dimension, barriers: value as never, text: text.trim() || null });
      setText(""); // never keep what was typed
      if (!isCrisis(r)) {
        signal("focus:submitted", r);
        qc.setQueryData(["map"], (m: MapResponse | undefined) => (m ? { ...m, profile: r.profile } : m));
        void qc.invalidateQueries({ queryKey: ["next"] });
      }
      onSubmitted(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  const toggle = (id: string) => onChange(value.includes(id) ? value.filter(x => x !== id) : [...value, id]);

  return (
    <>
      <h1 tabIndex={-1} className="mt-4 text-[30px] font-semibold leading-[36px] tracking-tight outline-none">
        {t("focus.barriers.title")}
      </h1>
      <p className="mt-2 text-[16px] text-ink-2">{t("focus.barriers.hint")}</p>
      <div className="mt-6 flex flex-wrap gap-2">
        {meta.data
          ? meta.data.barriers.map(b => (
              <Chip key={b.id} selected={value.includes(b.id)} onClick={() => toggle(b.id)} data-tour={`barrier-${b.id}`}>
                {lang === "es" ? b.label_es : b.label}
              </Chip>
            ))
          : [0, 1, 2, 3, 4].map(i => <Skeleton key={i} className="h-11 w-40 rounded-full" />)}
      </div>
      <label htmlFor="own-words" className="mt-7 block text-[15px] font-medium">
        {t("focus.words.label")}
      </label>
      <textarea
        id="own-words"
        data-tour="own-words"
        value={text}
        onChange={e => setText(e.target.value.slice(0, 140))}
        rows={2}
        maxLength={140}
        aria-describedby="own-words-help"
        className="mt-2 w-full resize-none rounded-2xl border border-line-strong bg-surface px-4 py-3 text-[17px] leading-6 placeholder:text-ink-2/70"
      />
      <p id="own-words-help" className="mt-1.5 flex justify-between text-[13px] text-ink-2">
        <span>{t("focus.words.help")}</span>
        <span className="tabular">{text.length}/140</span>
      </p>
      {error ? (
        <p role="alert" className="mt-3 text-[15px] text-scarlet-ink">
          {error}
        </p>
      ) : null}
      <div className="mt-auto pt-8">
        <Button block onClick={submit} loading={busy} data-tour="focus-submit">
          {t("focus.submit")}
        </Button>
      </div>
    </>
  );
}

/** The wait, made visible: real steps tick as the real requests finish (focus already saved; ranking runs now). */
function Finding({ onDone }: { onDone: () => void }) {
  const t = useT();
  const qc = useQueryClient();
  const [done, setDone] = useState(0);
  const [count, setCount] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const off = inspector.on(e => {
      if (e.type === "call" && e.call.path === "/me/next" && e.call.trace.candidates) setCount(e.call.trace.candidates);
    });
    const t0 = performance.now();
    const tick = (n: number, at: number) => new Promise<void>(r => setTimeout(() => { if (alive) setDone(n); r(); }, at));
    (async () => {
      await tick(1, 350);
      try {
        await qc.fetchQuery({ queryKey: ["next"], queryFn: api.next, staleTime: 0 });
      } catch {
        // Today shows the error with a retry
      }
      const spent = performance.now() - t0;
      await tick(2, Math.max(0, 900 - spent));
      await tick(3, 450);
      await new Promise(r => setTimeout(r, 380));
      if (alive) onDone();
    })();
    return () => {
      alive = false;
      off();
    };
  }, []);

  const lines = [
    t("focus.finding.windows"),
    count ? t("focus.finding.rank", { n: count }) : t("focus.finding.rankGeneric"),
    t("focus.finding.free"),
  ];
  return (
    <div className="flex flex-1 flex-col justify-center pb-16" role="status" aria-live="polite">
      <h1 tabIndex={-1} className="display text-[34px] leading-[1.1] outline-none">
        {t("focus.finding.title")}
      </h1>
      <ul className="mt-8 flex flex-col gap-4">
        {lines.map((l, i) => (
          <li key={i} className="flex items-center gap-3 text-[17px]">
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full transition-colors duration-300 ${
                done > i ? "bg-green text-bg" : "border border-line-strong"
              }`}
            >
              {done > i ? (
                <motion.span initial={{ scale: 0.4 }} animate={{ scale: 1 }}>
                  <Check size={15} weight="bold" aria-hidden />
                </motion.span>
              ) : done === i ? (
                <span className="h-2 w-2 animate-pulse rounded-full bg-ink-2" />
              ) : null}
            </span>
            <span className={done >= i ? "text-ink" : "text-ink-2"}>{l}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
