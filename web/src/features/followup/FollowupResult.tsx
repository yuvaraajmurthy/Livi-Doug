import { Brain, CheckCircle, Medal, Stairs, Trophy } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useNavigate } from "react-router";
import type { FollowupResponse } from "../../api/client";
import { useT } from "../../i18n/useT";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { WinPrompt } from "./WinPrompt";

const line = (i: number) => ({
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { delay: 0.15 + i * 0.16, duration: 0.4, ease: [0.22, 1, 0.36, 1] as const },
});

export function FollowupResult({ r, title }: { r: FollowupResponse; title: string | null }) {
  const t = useT();
  const nav = useNavigate();
  if (r.status === "missed") {
    return (
      <div>
        <h1 tabIndex={-1} className="display text-[36px] leading-[1.08] outline-none">
          {title ?? t("followup.thanks")}
        </h1>
        <p className="mt-4 text-[17px] leading-relaxed text-ink-2">{t("followup.noProblem")}</p>
        <Button block className="mt-8" onClick={() => nav("/next")}>
          {t("tab.today")}
        </Button>
      </div>
    );
  }
  const c = r.challenge;
  const from = c ? Math.max(0, (c.progress - c.added) / c.goal) : 0;
  const to = c ? Math.min(1, c.progress / c.goal) : 0;
  let i = 0;
  return (
    <div>
      <motion.div {...line(i++)} className="flex items-center gap-3">
        <motion.span
          initial={{ scale: 0.3 }}
          animate={{ scale: 1 }}
          transition={{ type: "spring", stiffness: 420, damping: 18, delay: 0.1 }}
          className="flex h-14 w-14 items-center justify-center rounded-full bg-green text-bg"
        >
          <CheckCircle size={32} weight="fill" aria-hidden />
        </motion.span>
      </motion.div>
      <motion.h1 {...line(i++)} tabIndex={-1} className="display mt-4 text-[36px] leading-[1.08] outline-none">
        {r.progress?.message ?? t("followup.thanks")}
      </motion.h1>

      <div className="mt-6 flex flex-col gap-3">
        <motion.div {...line(i++)}>
          <Card className="flex items-center gap-3 px-4 py-3.5" data-tour="arc-credit">
            <Medal size={24} className="shrink-0 text-scarlet-ink" aria-hidden />
            <span className="text-[16px]">{r.arc.message}</span>
          </Card>
        </motion.div>

        {c ? (
          <motion.div {...line(i++)}>
            <Card className="px-4 py-4" data-tour="cup">
              <div className="flex items-start gap-3">
                <Trophy size={24} className="mt-0.5 shrink-0 text-scarlet-ink" aria-hidden />
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="text-[16px] font-medium leading-snug">{c.title}</p>
                    <span className="shrink-0 rounded-full bg-green-tint px-2 text-[14px] font-semibold text-green tabular">
                      +{c.added}
                    </span>
                  </div>
                  <div
                    className="mt-3 h-2.5 overflow-hidden rounded-full bg-surface-2"
                    role="progressbar"
                    aria-valuemin={0}
                    aria-valuemax={c.goal}
                    aria-valuenow={c.progress}
                    aria-label={c.title}
                  >
                    <motion.div
                      className="h-full rounded-full bg-scarlet"
                      initial={{ width: `${from * 100}%` }}
                      animate={{ width: `${to * 100}%` }}
                      transition={{ delay: 0.9, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
                    />
                  </div>
                  <p className="mt-1.5 text-[13px] text-ink-2 tabular">
                    {t("followup.cupLine", { n: c.progress, goal: c.goal })}
                  </p>
                </div>
              </div>
            </Card>
          </motion.div>
        ) : null}

        {r.learned.length ? (
          <motion.section {...line(i++)} aria-labelledby="learned-h" role="region" data-tour="learned">
            <Card className="px-4 py-4">
              <h2 id="learned-h" className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-2">
                <Brain size={16} aria-hidden />
                {t("followup.learned")}
              </h2>
              <ul className="mt-3 flex flex-col gap-3">
                {r.learned.map(m => (
                  <li key={m.id}>
                    <p className="text-[16px] font-medium leading-snug">{m.statement}</p>
                    <p className="text-[14px] text-ink-2">{m.source.label}</p>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-[13px] text-ink-2">{t("followup.learnedHelp")}</p>
            </Card>
          </motion.section>
        ) : null}

        {r.next_rung ? (
          <motion.div {...line(i++)}>
            <Card className="flex items-start gap-3 px-4 py-3.5">
              <Stairs size={24} className="mt-0.5 shrink-0 text-scarlet-ink" aria-hidden />
              <span className="text-[16px]">{r.next_rung.message}</span>
            </Card>
          </motion.div>
        ) : null}
      </div>

      {r.win_prompt ? (
        <motion.div {...line(i++)} className="mt-6">
          <WinPrompt dimension={r.progress?.dimension ?? null} />
        </motion.div>
      ) : null}

      <motion.div {...line(i++)}>
        <Button block variant="secondary" className="mt-6" onClick={() => nav("/next")} data-tour="followup-done">
          {t("tab.today")}
        </Button>
      </motion.div>
    </div>
  );
}
