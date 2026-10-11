import { ArrowRight, ChartBar, Path, PresentationChart } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import type { Persona } from "../../demo/types";
import { useT } from "../../i18n/useT";
import { startSession } from "../../session/start";
import { LogoMark } from "../../ui/Logo";
import { Spinner } from "../../ui/Spinner";
import { PERSONA_COPY, PERSONA_ORDER } from "./personas";

export function Entry() {
  const t = useT();
  const nav = useNavigate();
  const [busy, setBusy] = useState<Persona | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function pick(p: Persona) {
    if (busy) return;
    setBusy(p);
    setError(null);
    try {
      nav(await startSession(p, { sandbox: true }));
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  }

  return (
    <main id="main" className="mx-auto max-w-[560px] px-5 pb-16 pt-[max(28px,env(safe-area-inset-top))] max-[359px]:px-4">
      <div className="flex items-center gap-2 text-ink">
        <LogoMark size={30} />
        <span className="display text-[26px] leading-none">Compass</span>
      </div>

      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="mt-12"
      >
        <p className="text-[13px] font-semibold uppercase tracking-[0.1em] text-scarlet-ink">{t("entry.kicker")}</p>
        <h1 tabIndex={-1} className="display mt-3 text-[46px] leading-[1.02] outline-none sm:text-[56px]">
          {t("entry.title")}
        </h1>
        <p className="mt-5 max-w-[46ch] text-[17px] leading-[1.6] text-ink-2">{t("entry.lede")}</p>
      </motion.section>

      <section className="mt-10" aria-labelledby="pick">
        <h2 id="pick" className="mb-3 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-2">
          {t("entry.pick")}
        </h2>
        <ul className="overflow-hidden rounded-[20px] border border-line bg-surface">
          {PERSONA_ORDER.map((p, i) => {
            const c = PERSONA_COPY[p];
            return (
              <motion.li
                key={p}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 + i * 0.04, duration: 0.35 }}
                className={i ? "border-t border-line" : ""}
              >
                <button
                  type="button"
                  onClick={() => pick(p)}
                  disabled={!!busy}
                  data-tour={`persona-${p}`}
                  className="flex w-full items-center gap-4 px-4 py-4 text-left transition-colors hover:bg-surface-2 disabled:cursor-wait cursor-pointer"
                >
                  <span
                    aria-hidden="true"
                    className="display flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-surface-2 text-[24px] text-ink"
                  >
                    {c.name[0]}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-baseline gap-x-2">
                      <span className="text-[17px] font-semibold">{c.name}</span>
                      <span className="text-[14px] text-ink-2">{c.line}</span>
                    </span>
                    <span className="mt-0.5 block text-[15px] leading-snug text-ink-2">{c.story}</span>
                  </span>
                  {busy === p ? (
                    <Spinner className="text-ink-2" label={t("common.loading")} />
                  ) : (
                    <ArrowRight size={20} aria-hidden className="shrink-0 text-ink-2" />
                  )}
                </button>
              </motion.li>
            );
          })}
        </ul>
        <p className="mt-2 text-[13px] text-ink-2">{t("entry.privateCopy")}</p>
        {error ? (
          <p role="alert" className="mt-3 text-[15px] text-scarlet-ink">
            {error}
          </p>
        ) : null}
      </section>

      <nav aria-label="More" className="mt-8 grid gap-2 sm:grid-cols-3">
        <EntryLink to="/tour" icon={<Path size={20} aria-hidden />} label={t("entry.tour")} />
        <EntryLink to="/present" icon={<PresentationChart size={20} aria-hidden />} label={t("entry.present")} />
        <EntryLink
          to="#"
          onClick={() => pick("staff")}
          icon={<ChartBar size={20} aria-hidden />}
          label={t("entry.staff")}
        />
      </nav>

      <p className="mt-10 text-[13px] leading-relaxed text-ink-2">{t("entry.footer")}</p>
    </main>
  );
}

function EntryLink({ to, icon, label, onClick }: { to: string; icon: React.ReactNode; label: string; onClick?: () => void }) {
  const cls =
    "flex min-h-14 items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-3 text-[15px] font-medium hover:bg-surface-2 cursor-pointer";
  if (onClick)
    return (
      <button type="button" onClick={onClick} className={cls}>
        {icon}
        {label}
      </button>
    );
  return (
    <Link to={to} className={cls}>
      {icon}
      {label}
    </Link>
  );
}
