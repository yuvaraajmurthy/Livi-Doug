import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { api, type S } from "../../api/client";
import { signal } from "../../api/inspector";
import { LogoMark } from "../../ui/Logo";

type Item = S["InboxItem"];

/** Drops a system-style banner for every inbox item that arrives while the app is open (after skip-ahead or a
 *  clock jump). Real Web Push also fires on subscribed devices; the banner means the story never depends on it. */
export function NotificationHost() {
  const nav = useNavigate();
  const inbox = useQuery({ queryKey: ["inbox"], queryFn: api.inbox });
  const seenMax = useRef<number | null>(null);
  const [queue, setQueue] = useState<Item[]>([]);

  useEffect(() => {
    const items = inbox.data?.items;
    if (!items) return;
    const max = items.reduce((m, i) => Math.max(m, i.id), 0);
    if (seenMax.current === null) {
      seenMax.current = max; // first load: these were already there
      return;
    }
    const fresh = items.filter(i => i.id > (seenMax.current ?? 0)).sort((a, b) => a.id - b.id);
    if (fresh.length) {
      seenMax.current = max;
      // show only the newest: an older reminder is moot once its follow-up has arrived
      setQueue([fresh[fresh.length - 1]]);
      for (const f of fresh) signal("notification:shown", f);
    }
  }, [inbox.data]);

  const current = queue[0] ?? null;
  useEffect(() => {
    if (!current) return;
    const h = setTimeout(() => setQueue(q => q.slice(1)), 6500);
    return () => clearTimeout(h);
  }, [current?.id]);

  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-[55] flex justify-center px-2 pt-[max(8px,env(safe-area-inset-top))]">
      <AnimatePresence>
        {current ? (
          <motion.div
            key={current.id}
            role="status"
            aria-live="polite"
            initial={{ y: -120, opacity: 0, scale: 0.96 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: -100, opacity: 0, transition: { duration: 0.2 } }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            onDragEnd={(_, info) => {
              if (info.offset.y < -30) setQueue(q => q.slice(1));
            }}
            className="pointer-events-auto w-full max-w-[440px]"
            data-tour="banner"
          >
            <button
              type="button"
              onClick={() => {
                setQueue(q => q.slice(1));
                nav(current.deep_link);
              }}
              className="flex w-full items-start gap-3 rounded-[22px] border border-line/60 bg-surface/95 px-3.5 py-3 text-left shadow-float backdrop-blur-xl cursor-pointer"
            >
              <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-[11px] bg-bg">
                <LogoMark size={26} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center justify-between text-[12px] font-medium uppercase tracking-wide text-ink-2">
                  <span>Compass</span>
                  <span className="normal-case tracking-normal">now</span>
                </span>
                <span className="mt-0.5 block text-[15px] font-semibold leading-snug">{current.title}</span>
                <span className="block text-[14px] leading-snug text-ink-2">{current.body}</span>
              </span>
            </button>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
