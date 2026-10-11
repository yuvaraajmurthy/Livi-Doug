import { Brain, Check, Sparkle, TextAa } from "@phosphor-icons/react";
import { motion } from "motion/react";
import type { Suggestion } from "../../api/client";
import type { Key } from "../../i18n/en";
import { useT } from "../../i18n/useT";
import { Sheet } from "../../ui/Sheet";

const COMP_LABEL: Record<string, Key> = {
  dimension: "comp.dimension",
  barrier: "comp.barrier",
  window: "comp.window",
  rung: "comp.rung",
  helped_similar: "comp.helped_similar",
};

const BARRIER_WORDS: Record<string, string> = {
  no_time: "no time",
  dont_know_anyone: "don't know anyone",
  money: "money",
  coursework: "coursework",
  not_my_scene: "not my scene",
  too_far: "too far",
  low_energy: "low energy",
  not_sure_where: "not sure where",
};

function detail(name: string, text: string): string {
  if (name === "barrier") return text.split(", ").map(b => BARRIER_WORDS[b] ?? b).join(", ");
  return text;
}

export function WhySheet({ s, open, onClose }: { s: Suggestion | null; open: boolean; onClose: () => void }) {
  const t = useT();
  return (
    <Sheet open={open && !!s} onClose={onClose} title={t("why.title")}>
      {s ? (
        <div className="flex flex-col gap-6 pt-1">
          <section>
            <h3 className="mb-2 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-2">{t("why.checks")}</h3>
            <ul className="flex flex-wrap gap-2">
              {s.reasons.filters.map(f => (
                <li
                  key={f.code}
                  className="inline-flex items-center gap-1.5 rounded-full bg-green-tint px-3 py-1 text-[14px] font-medium text-green"
                >
                  <Check size={14} weight="bold" aria-hidden />
                  {f.text}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <div className="mb-3 flex items-baseline justify-between">
              <h3 className="text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-2">{t("why.ranking")}</h3>
              <span className="text-[13px] text-ink-2 tabular">
                {t("why.total")} <strong className="text-ink">{Math.round(s.reasons.total * 100)}</strong>/100
              </span>
            </div>
            <ul className="flex flex-col gap-4">
              {s.reasons.components.map((c, i) => (
                <li key={c.name}>
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-[16px] font-medium">{t(COMP_LABEL[c.name] ?? "comp.dimension")}</span>
                    <span className="shrink-0 text-[13px] text-ink-2 tabular">{Math.round(c.weight * 100)}%</span>
                  </div>
                  <div
                    className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface-2"
                    role="meter"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={Math.round(c.score * 100)}
                    aria-label={t(COMP_LABEL[c.name] ?? "comp.dimension")}
                  >
                    <motion.div
                      className="h-full rounded-full bg-ink"
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.max(2, c.score * 100)}%` }}
                      transition={{ delay: 0.1 + i * 0.06, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                    />
                  </div>
                  {c.text ? <p className="mt-1 text-[14px] text-ink-2">{detail(c.name, c.text)}</p> : null}
                </li>
              ))}
            </ul>
          </section>

          {s.reasons.memory.length ? (
            <section>
              <h3 className="mb-2 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-2">{t("why.memory")}</h3>
              <ul className="flex flex-col gap-2">
                {s.reasons.memory.map(m => (
                  <li key={m.memory_id} className="flex items-start gap-2 text-[15px]">
                    <Brain size={18} className="mt-0.5 shrink-0 text-scarlet-ink" aria-hidden />
                    <span>
                      {m.statement}{" "}
                      <span className="text-ink-2 tabular">
                        ({m.delta > 0 ? "+" : ""}
                        {Math.round(m.delta * 100)})
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="rounded-2xl bg-surface-2 p-4">
            <p className="flex items-start gap-2 text-[15px] font-medium leading-snug">
              <Sparkle size={18} className="mt-0.5 shrink-0" aria-hidden />
              {t("why.footer")}
            </p>
            <p className="mt-2 flex items-center gap-2 text-[13px] text-ink-2">
              <TextAa size={16} aria-hidden />
              {s.why_source === "ai" ? t("why.wordingAi") : t("why.wordingTemplate")}
              {s.source?.name ? <span>· {s.source.name}</span> : null}
              {s.source?.verified_on ? <span>· verified {s.source.verified_on}</span> : null}
            </p>
          </section>
        </div>
      ) : null}
    </Sheet>
  );
}
