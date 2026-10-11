import { ArrowLeft, ArrowRight, HandTap, SkipForward, X } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { current } from "../engine";
import { runCurrent, tour, useTour } from "../tourStore";
import { TourDone } from "./TourDone";

type Rect = { top: number; left: number; width: number; height: number };

/** Tracks the target element's on-screen box every frame (it can scroll, animate or re-render). */
function useTargetRect(id: string | undefined): Rect | null {
  const [rect, setRect] = useState<Rect | null>(null);
  useEffect(() => {
    if (!id) {
      setRect(null);
      return;
    }
    let raf = 0;
    let last = "";
    let scrolled = false;
    const loop = () => {
      const el = Array.from(document.querySelectorAll<HTMLElement>(`[data-tour="${CSS.escape(id)}"]`)).find(
        e => e.getClientRects().length > 0,
      );
      const r = el?.getBoundingClientRect();
      if (el && r && !scrolled) {
        scrolled = true;
        // keep the target clear of the tab bar and the coach card
        if (r.top < 70 || r.bottom > window.innerHeight - 250) el.scrollIntoView({ block: "center", behavior: "smooth" });
      }
      const key = r ? `${r.top}|${r.left}|${r.width}|${r.height}` : "";
      if (key !== last) {
        last = key;
        setRect(r ? { top: r.top, left: r.left, width: r.width, height: r.height } : null);
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [id]);
  return rect;
}

export function CoachBar() {
  const s = useTour();
  const nav = useNavigate();
  const step = s ? current(s.engine) : null;
  const rect = useTargetRect(s && !s.done ? step?.target : undefined);
  const [vh, setVh] = useState(typeof window === "undefined" ? 800 : window.innerHeight);
  useEffect(() => {
    const f = () => setVh(window.innerHeight);
    window.addEventListener("resize", f);
    return () => window.removeEventListener("resize", f);
  }, []);

  if (!s || !step) return null;
  if (s.done) return <TourDone name={s.name} />;

  const atTop = !!rect && rect.top + rect.height > vh - 230;
  const total = s.engine.steps.length;
  const n = s.engine.index + 1;
  const hasTarget = !!step.target;
  const isSkip = step.perform?.some(a => a.kind === "skip" || a.kind === "clock");
  const primary = s.busy ? "Working…" : isSkip ? "Skip ahead" : hasTarget ? "Do it for me" : "Next";

  return (
    <>
      {rect ? (
        <div
          aria-hidden="true"
          className="pointer-events-none fixed z-[58] rounded-2xl transition-all duration-200 ease-out"
          style={{
            top: rect.top - 6,
            left: rect.left - 6,
            width: rect.width + 12,
            height: rect.height + 12,
            boxShadow: "0 0 0 3px var(--scarlet), 0 0 0 9999px rgba(15,16,18,0.32)",
          }}
        />
      ) : null}
      <motion.aside
          aria-label="Guided tour"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className={`fixed inset-x-0 z-[59] flex justify-center px-3 ${
            atTop ? "top-[max(8px,env(safe-area-inset-top))]" : "bottom-[calc(76px+env(safe-area-inset-bottom))]"
          }`}
          data-coach
        >
          <div className="w-full max-w-[460px] rounded-[22px] bg-ink p-4 text-bg shadow-float">
            <div className="flex items-center justify-between text-[12px] font-semibold uppercase tracking-[0.08em] opacity-70">
              <span className="tabular">
                Step {n} of {total}
              </span>
              <button
                type="button"
                onClick={() => {
                  tour.exit();
                  nav("/tour");
                }}
                aria-label="Exit tour"
                className="-mr-2 -mt-2 inline-flex h-10 w-10 items-center justify-center rounded-full hover:bg-white/10 cursor-pointer"
              >
                <X size={18} aria-hidden />
              </button>
            </div>
            <p className="mt-1 text-[17px] font-medium leading-snug" aria-live="polite">
              {hasTarget && !isSkip ? <HandTap size={18} className="mr-1.5 inline -mt-0.5" aria-hidden /> : null}
              {step.coach}
            </p>
            {s.error ? <p className="mt-2 text-[14px] text-amber">{s.error}</p> : null}
            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                onClick={() => tour.back()}
                disabled={!s.engine.history.length}
                aria-label="Back"
                className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-white/10 disabled:opacity-30 cursor-pointer"
              >
                <ArrowLeft size={18} aria-hidden />
              </button>
              <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/15" aria-hidden="true">
                <div className="h-full rounded-full bg-[var(--scarlet)] transition-all" style={{ width: `${(n / total) * 100}%` }} />
              </div>
              <button
                type="button"
                disabled={s.busy}
                onClick={() => (hasTarget || step.perform?.length ? runCurrent() : tour.next())}
                className="inline-flex h-11 items-center gap-1.5 rounded-full bg-bg px-4 text-[15px] font-semibold text-ink disabled:opacity-60 cursor-pointer"
                data-coach-primary
              >
                {isSkip ? <SkipForward size={16} aria-hidden /> : null}
                {primary}
                {!isSkip && !hasTarget ? <ArrowRight size={16} aria-hidden /> : null}
              </button>
            </div>
          </div>
      </motion.aside>
    </>
  );
}
