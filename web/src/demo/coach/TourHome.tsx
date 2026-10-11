import { ArrowRight, ChartBar } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useState } from "react";
import { PERSONA_COPY } from "../../features/entry/personas";
import { LogoMark } from "../../ui/Logo";
import { Spinner } from "../../ui/Spinner";
import { startTour, tour } from "../tourStore";
import { TOURS } from "../tours";
import type { Persona } from "../types";

const WHAT: Record<Persona, string> = {
  andre: "The whole loop: one step, a plan, a reminder, a follow-up, what Compass learns.",
  priya: "Low sleep, and tutoring for the actual cause.",
  taylor: "When a person comes first, and how crisis words are handled.",
  sofia: "Camden, in Spanish, online and in the evening.",
  jordan: "A first-year who doesn't know anyone, and a private bring-a-friend link.",
  staff: "What ScarletWell staff see: groups only, never a person.",
};

export function TourHome() {
  const [busy, setBusy] = useState<Persona | null>(null);
  const order: Persona[] = ["andre", "priya", "taylor", "sofia", "jordan", "staff"];
  return (
    <main id="main" className="mx-auto max-w-[520px] px-5 pb-16 pt-[max(28px,env(safe-area-inset-top))]">
      <div className="flex items-center gap-2">
        <LogoMark size={28} />
        <span className="display text-[24px] leading-none">Compass</span>
      </div>
      <h1 tabIndex={-1} className="display mt-10 text-[42px] leading-[1.04] outline-none">
        Try it yourself.
      </h1>
      <p className="mt-3 text-[17px] leading-relaxed text-ink-2">
        Pick a student. A short guide shows you what to tap, about a minute each. Your copy is private: nobody else at the
        table sees your taps.
      </p>
      <ul className="mt-8 flex flex-col gap-2.5">
        {order.map((p, i) => {
          const copy = p === "staff" ? null : PERSONA_COPY[p];
          return (
            <motion.li key={p} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
              <button
                type="button"
                disabled={!!busy}
                onClick={async () => {
                  setBusy(p);
                  tour.exit();
                  await startTour(p);
                  setBusy(null);
                }}
                className="flex w-full items-center gap-4 rounded-[20px] border border-line bg-surface px-4 py-4 text-left hover:bg-surface-2 cursor-pointer disabled:cursor-wait"
              >
                <span className="display flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-surface-2 text-[24px]" aria-hidden>
                  {copy ? copy.name[0] : <ChartBar size={22} />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[17px] font-semibold">
                    {copy ? copy.name : "Staff Pulse"}{" "}
                    <span className="text-[14px] font-normal text-ink-2">· {TOURS[p].length} steps</span>
                  </span>
                  <span className="block text-[15px] leading-snug text-ink-2">{WHAT[p]}</span>
                </span>
                {busy === p ? <Spinner /> : <ArrowRight size={20} className="shrink-0 text-ink-2" aria-hidden />}
              </button>
            </motion.li>
          );
        })}
      </ul>
    </main>
  );
}
