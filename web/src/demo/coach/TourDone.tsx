import { ArrowRight, CheckCircle } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useNavigate } from "react-router";
import { startTour, tour } from "../tourStore";
import { TOUR_ORDER } from "../tours";
import type { Persona } from "../types";

const SUMMARY: Record<Persona, { title: string; lines: string[] }> = {
  andre: {
    title: "You just closed the loop.",
    lines: [
      "One step that fit his real week, chosen by code you can read",
      "A plan, a reminder, a two-tap follow-up",
      "Compass learned what worked, and he can delete any of it",
    ],
  },
  priya: {
    title: "You asked why.",
    lines: ["Low sleep, caused by Calc II", "So: free tutoring at Busch, not generic sleep tips", "Her words were safety-checked and never stored"],
  },
  taylor: {
    title: "Safety came first.",
    lines: ["A person before an event when scores are very low", "Crisis words caught by code before any AI", "A fixed card with real numbers; nothing stored"],
  },
  sofia: {
    title: "Camden, in Spanish.",
    lines: ["Online and in the evening, because she works full time", "Free, because money is tight", "Camden supply gaps show up for staff too"],
  },
  jordan: {
    title: "Bring a friend.",
    lines: ["A structured game night for someone new", "A private invite link, no contacts", "It counts double for the residence-hall challenge"],
  },
  staff: {
    title: "Groups, never people.",
    lines: ["Where supply is thin, campus by campus", "Groups under 10 refused by the database", "Plain-English questions with the SQL shown"],
  },
};

export function TourDone({ name }: { name: Persona }) {
  const nav = useNavigate();
  const s = SUMMARY[name];
  const nextName = TOUR_ORDER[(TOUR_ORDER.indexOf(name) + 1) % TOUR_ORDER.length];
  return (
    <motion.aside
      aria-label="Tour complete"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="fixed inset-x-0 bottom-[calc(76px+env(safe-area-inset-bottom))] z-[59] flex justify-center px-3"
    >
      <div className="w-full max-w-[460px] rounded-[22px] bg-ink p-5 text-bg shadow-float">
        <p className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.08em] opacity-70">
          <CheckCircle size={16} weight="fill" aria-hidden /> Tour complete
        </p>
        <p className="display mt-1 text-[28px] leading-tight">{s.title}</p>
        <ul className="mt-3 flex flex-col gap-1.5 text-[15px] opacity-90">
          {s.lines.map(l => (
            <li key={l} className="flex gap-2">
              <span aria-hidden>·</span>
              {l}
            </li>
          ))}
        </ul>
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={() => void startTour(nextName)}
            className="inline-flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full bg-bg px-4 text-[15px] font-semibold text-ink cursor-pointer"
          >
            Next: {nextName === "staff" ? "Staff view" : nextName[0].toUpperCase() + nextName.slice(1)}
            <ArrowRight size={16} aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => {
              tour.exit();
              nav("/tour");
            }}
            className="h-11 rounded-full bg-white/10 px-4 text-[15px] font-medium cursor-pointer"
          >
            All tours
          </button>
        </div>
      </div>
    </motion.aside>
  );
}
