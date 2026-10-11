import { AnimatePresence, motion } from "motion/react";
import { useEffect, useSyncExternalStore } from "react";

type ToastMsg = { id: number; text: string; tone?: "neutral" | "amber" };
let current: ToastMsg | null = null;
let seq = 0;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach(fn => fn());

export function toast(text: string, tone: ToastMsg["tone"] = "neutral") {
  current = { id: ++seq, text, tone };
  emit();
}

const sub = (fn: () => void) => {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
};

/** Polite, non-focus-stealing toast; auto-dismisses after 4 s. */
export function ToastHost() {
  const msg = useSyncExternalStore(sub, () => current, () => current);
  useEffect(() => {
    if (!msg) return;
    const id = msg.id;
    const h = setTimeout(() => {
      if (current?.id === id) {
        current = null;
        emit();
      }
    }, 4000);
    return () => clearTimeout(h);
  }, [msg]);
  return (
    <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-[calc(84px+env(safe-area-inset-bottom))] z-40 flex justify-center px-5">
      <AnimatePresence>
        {msg ? (
          <motion.div
            key={msg.id}
            initial={{ y: 16, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 8, opacity: 0, transition: { duration: 0.15 } }}
            className={`rounded-full px-4 py-2.5 text-[15px] font-medium shadow-float ${
              msg.tone === "amber" ? "bg-amber-tint text-amber" : "bg-ink text-bg"
            }`}
          >
            {msg.text}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

let announcement = "";
const aListeners = new Set<() => void>();
/** Screen-reader announcement for state changes that don't move focus. */
export function announce(text: string) {
  announcement = "";
  aListeners.forEach(fn => fn());
  setTimeout(() => {
    announcement = text;
    aListeners.forEach(fn => fn());
  }, 50);
}
const aSub = (fn: () => void) => {
  aListeners.add(fn);
  return () => {
    aListeners.delete(fn);
  };
};
export function LiveRegion() {
  const text = useSyncExternalStore(aSub, () => announcement, () => announcement);
  return (
    <div className="sr-only" aria-live="polite" aria-atomic="true">
      {text}
    </div>
  );
}
