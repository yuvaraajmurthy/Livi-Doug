import {
  ArrowClockwise,
  ArrowLeft,
  ArrowRight,
  CornersOut,
  DeviceMobile,
  Lightning,
  Note,
  WarningCircle,
} from "@phosphor-icons/react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { STAGE_FRAME_NAME } from "../bridge";
import { MAIN_STORY } from "../story";
import { LogoMark } from "../../ui/Logo";
import { Close, ColdOpen, useQr } from "./Slides";
import { Proof } from "./Proof";
import { useStage } from "./useStage";

const PHONE_W = 390;
const PHONE_H = 844;
const chapters = Array.from(new Set(MAIN_STORY.map(s => s.chapter)));
const firstOf = (ch: string) => MAIN_STORY.findIndex(s => s.chapter === ch);

function useScale(ref: React.RefObject<HTMLDivElement | null>) {
  const [scale, setScale] = useState(0.75);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const h = el.clientHeight - 24;
      setScale(Math.min(1, Math.max(0.5, h / (PHONE_H + 24))));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return scale;
}

function Clock({ startedAt }: { startedAt: number | null }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const h = setInterval(() => tick(x => x + 1), 1000);
    return () => clearInterval(h);
  }, []);
  const s = startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 0;
  const over = s > 180;
  return (
    <span className={`tabular ${over ? "text-scarlet-ink" : "text-ink-2"}`}>
      {Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")} / 3:00
    </span>
  );
}

export function Present() {
  const frame = useRef<HTMLIFrameElement>(null);
  const phoneCol = useRef<HTMLDivElement>(null);
  const scale = useScale(phoneCol);
  const st = useStage(frame);
  const [notes, setNotes] = useState(true);
  const [pair, setPair] = useState(false);
  const [templates, setTemplates] = useState(false);
  const [offline, setOffline] = useState(false);
  const step = st.step;
  const slide = step.slide;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement | null)?.closest?.("input, textarea")) return;
      const k = e.key;
      if (k === "ArrowRight" || k === "PageDown" || k === " ") {
        e.preventDefault();
        st.next();
      } else if (k === "ArrowLeft" || k === "PageUp") {
        e.preventDefault();
        st.back();
      } else if (k === "n" || k === "N") setNotes(x => !x);
      else if (k === "p" || k === "P") setPair(x => !x);
      else if (k === "f" || k === "F") void (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen());
      else if (k === "a" || k === "A") {
        const on = !templates;
        setTemplates(on);
        void st.send([{ kind: "templates", on }]).catch(() => setTemplates(!on));
      } else if (k === "o" || k === "O") {
        const on = !offline;
        setOffline(on);
        void st.send([{ kind: "replay", on }]).catch(() => setOffline(!on));
      } else if (k === "r" || k === "R") {
        if (window.confirm("Restart the story with fresh students?")) st.restart();
      } else if (/^[1-9]$/.test(k)) {
        const ch = chapters[Number(k) - 1];
        if (ch) st.jump(firstOf(ch));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [st, templates, offline]);

  const chapterIdx = chapters.indexOf(step.chapter);

  return (
    <div className="grid h-dvh grid-rows-[auto_1fr_auto] overflow-hidden bg-bg">
      <header className="flex items-center justify-between gap-4 border-b border-line px-6 py-3">
        <span className="flex items-center gap-2">
          <LogoMark size={24} />
          <span className="display text-[22px] leading-none">Compass</span>
        </span>
        <nav aria-label="Chapters" className="flex items-center gap-1.5">
          {chapters.map((c, i) => (
            <button
              key={c}
              type="button"
              onClick={() => st.jump(firstOf(c))}
              title={`${i + 1}. ${c}`}
              aria-label={`Chapter ${i + 1}: ${c}`}
              aria-current={i === chapterIdx ? "step" : undefined}
              className={`h-2 rounded-full transition-all cursor-pointer ${i === chapterIdx ? "w-8 bg-scarlet" : i < chapterIdx ? "w-2 bg-ink" : "w-2 bg-line-strong/50"}`}
            />
          ))}
        </nav>
        <div className="flex items-center gap-3 text-[13px] font-medium">
          {offline || st.evidence.calls[0]?.source === "replay" ? (
            <span className="rounded-full bg-amber-tint px-2.5 py-1 text-amber">Offline replay</span>
          ) : templates ? (
            <span className="rounded-full bg-amber-tint px-2.5 py-1 text-amber">AI off · templates</span>
          ) : (
            <span className="flex items-center gap-1 rounded-full bg-green-tint px-2.5 py-1 text-green">
              <Lightning size={13} weight="fill" aria-hidden /> Live API
            </span>
          )}
          <Clock startedAt={st.startedAt} />
        </div>
      </header>

      <div className={slide ? "relative" : "grid min-h-0 grid-cols-[auto_1fr] gap-8 px-8 py-4"}>
        <div
          ref={phoneCol}
          className={slide ? "pointer-events-none absolute inset-0 opacity-0" : "flex min-h-0 items-center justify-center"}
          aria-hidden={slide ? true : undefined}
        >
          <div style={{ width: (PHONE_W + 24) * scale, height: (PHONE_H + 24) * scale }} className="relative">
            <div
              className="absolute left-0 top-0 origin-top-left rounded-[54px] bg-[#0b0c0e] p-3 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.6)]"
              style={{ transform: `scale(${scale})`, width: PHONE_W + 24, height: PHONE_H + 24 }}
            >
              <iframe
                ref={frame}
                name={STAGE_FRAME_NAME}
                title="Compass on a phone"
                src={new URLSearchParams(window.location.search).get("record") === "1" ? "/?record=1" : "/"}
                className="h-full w-full rounded-[42px] bg-bg"
                style={{ width: PHONE_W, height: PHONE_H }}
              />
            </div>
          </div>
        </div>

        {slide === "cold-open" ? (
          <ColdOpen />
        ) : slide === "close" ? (
          <Close />
        ) : (
          <section aria-live="polite" className="flex min-h-0 flex-col overflow-y-auto py-2 pr-4">
            <div className="my-auto">
            <AnimatePresence mode="wait">
              <motion.div
                key={step.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, transition: { duration: 0.12 } }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="max-w-[640px]"
              >
                <p className="flex items-center gap-3 text-[13px] font-semibold uppercase tracking-[0.12em] text-scarlet-ink">
                  <span>
                    {chapterIdx + 1}. {step.chapter}
                  </span>
                  {step.tag ? <span className="rounded-full border border-scarlet/40 px-2 py-0.5 text-[11px]">{step.tag}</span> : null}
                </p>
                <h1 className="display mt-2 text-[clamp(28px,5.4vh,54px)] leading-[1.06]">{step.claim}</h1>
                <div className="mt-[2.2vh]">
                  <Proof kind={step.proof} ev={st.evidence} />
                </div>
                {st.status === "error" ? (
                  <p className="mt-4 flex items-center gap-2 text-[15px] text-amber">
                    <WarningCircle size={18} aria-hidden /> {st.error}{" "}
                    <button type="button" className="underline cursor-pointer" onClick={st.retry}>
                      Try again
                    </button>
                  </p>
                ) : null}
                {notes && step.note ? (
                  <p className="mt-[2.2vh] flex gap-2 border-l-2 border-line pl-3 text-[15px] leading-snug text-ink-2">
                    <Note size={18} className="mt-1 shrink-0" aria-hidden />
                    {step.note}
                  </p>
                ) : null}
              </motion.div>
            </AnimatePresence>
            <RequestLog calls={st.evidence.calls} />
            </div>
          </section>
        )}
      </div>

      <footer className="flex items-center justify-between gap-4 border-t border-line px-6 py-2.5 text-[13px] text-ink-2">
        <div className="flex items-center gap-2">
          <button type="button" onClick={st.back} aria-label="Back" className="inline-flex h-9 w-9 items-center justify-center rounded-full hover:bg-surface-2 cursor-pointer">
            <ArrowLeft size={16} aria-hidden />
          </button>
          <button
            type="button"
            onClick={st.next}
            aria-label="Next"
            data-stage-next
            className="inline-flex h-9 items-center gap-1.5 rounded-full bg-ink px-4 font-semibold text-bg cursor-pointer"
          >
            {st.status === "performing" ? "Working…" : st.status === "waiting" ? "Waiting for the app…" : "Next"}
            <ArrowRight size={14} aria-hidden />
          </button>
          <span className="ml-2 tabular">
            {st.engine.index + 1} / {MAIN_STORY.length}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span>→ next · ← back · 1–9 chapter · N notes · A AI on/off · O offline · P pair · F fullscreen</span>
          <button type="button" onClick={() => setPair(true)} className="inline-flex items-center gap-1 hover:text-ink cursor-pointer">
            <DeviceMobile size={15} aria-hidden /> Pair
          </button>
          <button type="button" onClick={() => window.confirm("Restart the story with fresh students?") && st.restart()} className="inline-flex items-center gap-1 hover:text-ink cursor-pointer">
            <ArrowClockwise size={15} aria-hidden /> Restart
          </button>
          <button type="button" onClick={() => void document.documentElement.requestFullscreen()} className="inline-flex items-center gap-1 hover:text-ink cursor-pointer">
            <CornersOut size={15} aria-hidden /> Full screen
          </button>
        </div>
      </footer>

      {pair ? <PairDialog token={st.token} onClose={() => setPair(false)} /> : null}
    </div>
  );
}

function RequestLog({ calls }: { calls: ReturnType<typeof useStage>["evidence"]["calls"] }) {
  if (!calls.length) return null;
  return (
    <div className="mt-[2.5vh] max-w-[640px]" aria-label="Live requests">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">Live requests</p>
      <ul className="flex flex-col gap-1 font-mono text-[12px]">
        {calls.slice(0, 3).map(c => (
          <motion.li key={c.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} className="flex items-center gap-3 text-ink-2">
            <span className="w-11 font-semibold text-ink">{c.method}</span>
            <span className="min-w-0 flex-1 truncate">{c.path.replace(/\?.*$/, "")}</span>
            <span className="tabular">{c.ms} ms</span>
            <span
              className={`rounded px-1.5 ${
                c.source === "replay" ? "bg-amber-tint text-amber" : c.fallback ? "bg-amber-tint text-amber" : "bg-green-tint text-green"
              }`}
            >
              {c.source === "replay" ? "replay" : c.fallback ? "fixture" : c.status}
            </span>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

function PairDialog({ token, onClose }: { token: string | null; onClose: () => void }) {
  const url = token ? `${window.location.origin}/join#t=${encodeURIComponent(token)}` : `${window.location.origin}/tour`;
  const qr = useQr(url);
  return (
    <div role="dialog" aria-modal="true" aria-label="Pair a phone" className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--scrim)]" onClick={onClose}>
      <div className="w-[420px] rounded-[28px] bg-surface p-6 text-center shadow-float" onClick={e => e.stopPropagation()}>
        <p className="text-[20px] font-semibold">Pair a phone with this story</p>
        <p className="mt-1 text-[15px] text-ink-2">
          {token
            ? "Scan, then tap “Reminders” on the phone. When the story skips ahead, the phone gets the real push."
            : "Start the story first, then pair. (This code opens the guided tours.)"}
        </p>
        {qr ? <img src={qr} alt="Pairing QR code" className="mx-auto mt-4 h-60 w-60" /> : null}
        <button type="button" onClick={onClose} className="mt-4 h-11 rounded-full bg-ink px-5 font-semibold text-bg cursor-pointer">
          Done
        </button>
      </div>
    </div>
  );
}
