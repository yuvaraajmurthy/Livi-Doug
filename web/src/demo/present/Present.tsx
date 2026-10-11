import { ArrowLeft, ArrowRight, ArrowsOut, Note } from "@phosphor-icons/react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { STAGE_FRAME_NAME } from "../bridge";
import { MAIN_STORY } from "../story";
import { Close, ColdOpen, Numbers } from "./Slides";
import { Evidence } from "./Evidence";
import { useStage } from "./useStage";
import { NOTES_CHANNEL, type NotesCommand, type NotesState } from "./notesChannel";

const PHONE_W = 390;
const PHONE_H = 844;
const chapters = Array.from(new Set(MAIN_STORY.map(s => s.chapter)));
const firstOf = (ch: string) => MAIN_STORY.findIndex(s => s.chapter === ch);
const openNotes = () => window.open("/present/notes", "compass-notes", "width=560,height=760");

function useScale(ref: React.RefObject<HTMLDivElement | null>) {
  const [scale, setScale] = useState(0.8);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setScale(Math.min(1.05, Math.max(0.5, (el.clientHeight - 16) / (PHONE_H + 24)))));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return scale;
}

/** Audience screen: the phone acts, then one claim and one piece of evidence. Presenter aids live in /present/notes. */
export function Present() {
  const frame = useRef<HTMLIFrameElement>(null);
  const phoneCol = useRef<HTMLDivElement>(null);
  const scale = useScale(phoneCol);
  const st = useStage(frame);
  const [templates, setTemplates] = useState(false);
  const [offline, setOffline] = useState(false);
  const [controls, setControls] = useState(false);
  const step = st.step;
  const slide = step.slide;
  const settled = st.status === "done" || st.status === "idle" || st.status === "error";
  const channel = useRef<BroadcastChannel | null>(null);

  const toggleTemplates = () => {
    const on = !templates;
    setTemplates(on);
    void st.send([{ kind: "templates", on }]).catch(() => setTemplates(!on));
  };
  const toggleOffline = () => {
    const on = !offline;
    setOffline(on);
    void st.send([{ kind: "replay", on }]).catch(() => setOffline(!on));
  };
  const broadcast = () => {
    const msg: NotesState = {
      kind: "state",
      index: st.engine.index,
      status: st.status,
      error: st.error,
      startedAt: st.startedAt,
      calls: st.evidence.calls.slice(0, 6),
      templates,
      offline,
      token: st.token,
    };
    channel.current?.postMessage(msg);
  };

  // presenter window: commands in, state out
  useEffect(() => {
    const ch = new BroadcastChannel(NOTES_CHANNEL);
    channel.current = ch;
    ch.onmessage = (e: MessageEvent<NotesCommand>) => {
      const c = e.data;
      if (c.kind === "next") st.next();
      else if (c.kind === "back") st.back();
      else if (c.kind === "jump") st.jump(c.index);
      else if (c.kind === "templates") toggleTemplates();
      else if (c.kind === "offline") toggleOffline();
      else if (c.kind === "restart") st.restart();
      else if (c.kind === "hello") broadcast();
    };
    return () => ch.close();
  });
  useEffect(broadcast, [st.engine.index, st.status, st.evidence.calls.length, templates, offline, st.token, st.startedAt]);

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
      } else if (k === "n" || k === "N") openNotes();
      else if (k === "f" || k === "F") void (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen());
      else if (k === "a" || k === "A") toggleTemplates();
      else if (k === "o" || k === "O") toggleOffline();
      else if (k === "r" || k === "R") {
        if (window.confirm("Restart the story with fresh students?")) st.restart();
      } else if (/^[1-9]$/.test(k)) {
        const ch = chapters[Number(k) - 1];
        if (ch) st.jump(firstOf(ch));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // controls appear on mouse move and fade after 2 s
  useEffect(() => {
    let h = 0;
    const show = () => {
      setControls(true);
      window.clearTimeout(h);
      h = window.setTimeout(() => setControls(false), 2000);
    };
    window.addEventListener("mousemove", show);
    return () => {
      window.removeEventListener("mousemove", show);
      window.clearTimeout(h);
    };
  }, []);

  const progress = (st.engine.index / (MAIN_STORY.length - 1)) * 100;

  return (
    <div className="relative h-dvh overflow-hidden bg-bg">
      <div className="absolute inset-x-0 top-0 z-10 h-[3px] bg-line/60" aria-hidden>
        <motion.div className="h-full bg-scarlet" animate={{ width: `${progress}%` }} transition={{ duration: 0.4 }} />
      </div>

      {offline || templates ? (
        <p className="absolute right-6 top-4 z-10 rounded-full bg-amber-tint px-3 py-1 text-[13px] font-medium text-amber">
          {offline ? "Offline replay" : "AI off · templates"}
        </p>
      ) : null}

      <div
        className={
          slide
            ? "pointer-events-none absolute inset-0 opacity-0"
            : "grid h-full grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] items-center gap-[5vw] px-[5vw]"
        }
      >
        <div ref={phoneCol} className="flex h-full min-h-0 items-center justify-end py-[3vh]" aria-hidden={slide ? true : undefined}>
          <div style={{ width: (PHONE_W + 24) * scale, height: (PHONE_H + 24) * scale }} className="relative">
            <div
              className="absolute left-0 top-0 origin-top-left rounded-[56px] bg-[#0b0c0e] p-3 shadow-[0_40px_90px_-40px_rgba(0,0,0,0.55)]"
              style={{ transform: `scale(${scale})`, width: PHONE_W + 24, height: PHONE_H + 24 }}
            >
              <iframe
                ref={frame}
                name={STAGE_FRAME_NAME}
                title="Compass on a phone"
                src={new URLSearchParams(window.location.search).get("record") === "1" ? "/?record=1" : "/"}
                className="rounded-[44px] bg-bg"
                style={{ width: PHONE_W, height: PHONE_H }}
              />
            </div>
          </div>
        </div>

        {!slide ? (
          <section aria-live="polite" className="max-w-[620px]">
            <AnimatePresence mode="wait">
              <motion.p
                key={`k-${step.chapter}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="mb-4 text-[clamp(13px,1.9vh,16px)] font-semibold uppercase tracking-[0.14em] text-scarlet-ink"
              >
                {step.chapter}
              </motion.p>
            </AnimatePresence>
            <AnimatePresence mode="wait">
              {settled ? (
                <motion.div key={step.id} exit={{ opacity: 0, transition: { duration: 0.12 } }}>
                  <motion.h1
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                    className="display text-[clamp(40px,8.4vh,76px)] leading-[1.02]"
                  >
                    {step.claim}
                  </motion.h1>
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.18, duration: 0.4 }}
                    className="mt-[4vh]"
                  >
                    <Evidence kind={step.proof} ev={st.evidence} />
                  </motion.div>
                </motion.div>
              ) : (
                <motion.div
                  key={`wait-${step.id}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-2 text-ink-2"
                >
                  <span className="h-2 w-2 animate-pulse rounded-full bg-scarlet" aria-hidden />
                  <span className="text-[15px]">Watch the phone</span>
                </motion.div>
              )}
            </AnimatePresence>
            {st.status === "error" ? (
              <p className="mt-6 text-[15px] text-amber">
                {st.error}{" "}
                <button type="button" className="underline cursor-pointer" onClick={st.retry}>
                  Try again
                </button>
              </p>
            ) : null}
          </section>
        ) : null}
      </div>

      {slide === "cold-open" ? <ColdOpen /> : slide === "numbers" ? <Numbers /> : slide === "close" ? <Close /> : null}

      <div
        className={`absolute bottom-5 right-6 z-20 flex items-center gap-1 rounded-full border border-line bg-surface/95 p-1 shadow-float transition-opacity duration-300 ${
          controls ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <button type="button" onClick={st.back} aria-label="Back" className="inline-flex h-10 w-10 items-center justify-center rounded-full hover:bg-surface-2 cursor-pointer">
          <ArrowLeft size={18} aria-hidden />
        </button>
        <span className="px-1 text-[13px] text-ink-2 tabular">
          {st.engine.index + 1}/{MAIN_STORY.length}
        </span>
        <button
          type="button"
          onClick={st.next}
          aria-label="Next"
          className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-ink text-bg cursor-pointer"
        >
          <ArrowRight size={18} aria-hidden />
        </button>
        <button type="button" onClick={openNotes} aria-label="Presenter notes" className="inline-flex h-10 w-10 items-center justify-center rounded-full hover:bg-surface-2 cursor-pointer">
          <Note size={18} aria-hidden />
        </button>
        <button
          type="button"
          onClick={() => void document.documentElement.requestFullscreen()}
          aria-label="Full screen"
          className="inline-flex h-10 w-10 items-center justify-center rounded-full hover:bg-surface-2 cursor-pointer"
        >
          <ArrowsOut size={18} aria-hidden />
        </button>
      </div>
      <span data-stage-status={st.status} className="sr-only">
        {st.status}
      </span>
    </div>
  );
}
