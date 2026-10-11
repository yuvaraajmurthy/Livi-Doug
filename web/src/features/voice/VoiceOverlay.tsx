import { CalendarBlank, CaretRight, Keyboard, Microphone, MicrophoneSlash, PhoneDisconnect } from "@phosphor-icons/react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { CrisisResponse } from "../../api/client";
import { useT } from "../../i18n/useT";
import type { Key } from "../../i18n/en";
import { EventSheet } from "../event/EventSheet";
import { CrisisScreen } from "../safety/CrisisScreen";
import { cleanTitle } from "../today/StepCard";
import type { EventChip } from "../chat/types";
import { MicCapture, Player } from "./audio";
import { VoiceSession, type VoiceState } from "./VoiceSession";

const STATE_KEY: Record<VoiceState, Key> = {
  connecting: "voice.connecting",
  listening: "voice.listening",
  thinking: "voice.thinking",
  speaking: "voice.speaking",
  ended: "voice.ended",
  error: "voice.error",
};

type Caption = { role: "user" | "assistant"; text: string; done: boolean };

/** Deltas extend the open line for that speaker; a final transcript replaces it and closes it. Keep two lines. */
export function mergeCaption(cs: Caption[], role: Caption["role"], text: string, final: boolean): Caption[] {
  const last = cs[cs.length - 1];
  if (last && last.role === role && !last.done) {
    return [...cs.slice(0, -1), { role, text: final ? text : last.text + text, done: final }];
  }
  return [...cs, { role, text, done: final }].slice(-2);
}

/** Full-screen voice mode: one breathing orb, one state word, two caption lines, cards when Compass shows events. */
export function VoiceOverlay({ onClose, conversationId }: { onClose: (typeInstead?: boolean) => void; conversationId?: string | null }) {
  const t = useT();
  const reduced = useReducedMotion();
  const [state, setState] = useState<VoiceState>("connecting");
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [events, setEvents] = useState<EventChip[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [crisis, setCrisis] = useState<CrisisResponse | null>(null);
  const orb = useRef<HTMLDivElement>(null);
  const mic = useRef<MicCapture | null>(null);
  const player = useRef<Player | null>(null);
  const sess = useRef<VoiceSession | null>(null);
  const micLevel = useRef(0);

  useEffect(() => {
    let alive = true;
    const p = new Player();
    player.current = p;
    const m = new MicCapture();
    mic.current = m;
    const s = new VoiceSession({
      state: st => alive && setState(st),
      audio: b64 => p.play(b64),
      bargeIn: () => p.stop(),
      caption: (role, text, final) => alive && setCaptions(cs => mergeCaption(cs, role, text, final)),
      ui: e => {
        if (!alive) return;
        if (e.type === "events") setEvents(e.items);
      },
      crisis: c => {
        if (!alive) return;
        setCrisis(c);
        m.stop();
        p.stop();
      },
      error: msg => alive && setProblem(msg),
    });
    sess.current = s;
    p.onIdle = () => s.idle();
    (async () => {
      try {
        await p.unlock();
        await m.start(b64 => s.sendAudio(b64), rms => (micLevel.current = rms));
        if (alive) s.start(conversationId ?? null);
      } catch (e) {
        if (!alive) return;
        const name = (e as Error).name;
        setState("error");
        setProblem(name === "NotAllowedError" ? t("voice.denied") : t("voice.unsupported"));
      }
    })();

    let raf = 0;
    const loop = () => {
      const lvl = Math.max(micLevel.current * 3, p.level() * 3);
      if (orb.current && !reduced) orb.current.style.transform = `scale(${1 + Math.min(0.35, lvl)})`;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      s.stop();
      m.stop();
      p.close();
    };
  }, []);

  useEffect(() => {
    if (mic.current) mic.current.muted = muted;
  }, [muted]);

  if (crisis) return createPortal(<CrisisScreen crisis={crisis} onBack={() => onClose()} />, document.body);

  const speaking = state === "speaking";
  return createPortal(
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-label={t("voice.title")}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[65] flex flex-col items-center bg-bg px-6 pb-[max(24px,env(safe-area-inset-bottom))] pt-[max(48px,env(safe-area-inset-top))]"
      data-tour="voice-overlay"
    >
      <div className="flex flex-1 flex-col items-center justify-center gap-8">
        <div className="relative flex h-56 w-56 items-center justify-center">
          <div
            ref={orb}
            aria-hidden
            className={`h-44 w-44 rounded-full transition-[background,box-shadow] duration-500 ${
              speaking
                ? "bg-[radial-gradient(circle_at_35%_30%,var(--scarlet-tint),var(--scarlet)_75%)] shadow-[0_20px_60px_-20px_var(--scarlet)]"
                : state === "thinking"
                  ? "animate-pulse bg-[radial-gradient(circle_at_35%_30%,var(--surface),var(--line-strong)_80%)]"
                  : "bg-[radial-gradient(circle_at_35%_30%,var(--surface),var(--ink-2)_85%)]"
            }`}
            style={{ transition: "transform 90ms linear" }}
          />
        </div>
        <p className="text-[15px] font-semibold uppercase tracking-[0.14em] text-ink-2" role="status" aria-live="polite">
          {t(STATE_KEY[state])}
        </p>
        <div className="flex min-h-[96px] w-full max-w-[420px] flex-col items-center gap-2 text-center" aria-live="polite">
          {problem ? <p className="text-[17px] text-ink">{problem}</p> : null}
          {!problem
            ? captions.map((c, i) => (
                <p key={i} className={`text-[17px] leading-snug ${c.role === "user" ? "text-ink-2" : "text-ink"}`}>
                  {c.text}
                </p>
              ))
            : null}
          {!problem && !captions.length && state === "listening" ? <p className="text-[17px] text-ink-2">{t("voice.hint")}</p> : null}
        </div>
      </div>

      <AnimatePresence>
        {events.length ? (
          <motion.ul
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            className="mb-5 flex w-full max-w-[440px] flex-col gap-2"
          >
            {events.map((e, i) => (
              <li key={e.id}>
                <button
                  type="button"
                  onClick={() => setOpen(e.id)}
                  data-tour={`voice-event-${i}`}
                  className="flex w-full items-center gap-3 rounded-[18px] border border-line bg-surface px-4 py-3 text-left shadow-float cursor-pointer"
                >
                  <CalendarBlank size={20} className="shrink-0 text-scarlet-ink" aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[16px] font-semibold leading-snug">{cleanTitle(e.title)}</span>
                    <span className="block text-[14px] text-ink-2">{[e.when_label, e.venue].filter(Boolean).join(" · ")}</span>
                  </span>
                  <CaretRight size={18} className="text-ink-2" aria-hidden />
                </button>
              </li>
            ))}
          </motion.ul>
        ) : null}
      </AnimatePresence>

      <div className="flex w-full max-w-[440px] items-center justify-between">
        <button
          type="button"
          onClick={() => setMuted(m => !m)}
          aria-pressed={muted}
          aria-label={muted ? t("voice.unmute") : t("voice.mute")}
          className="inline-flex h-14 w-14 items-center justify-center rounded-full border border-line bg-surface cursor-pointer"
        >
          {muted ? <MicrophoneSlash size={24} aria-hidden /> : <Microphone size={24} aria-hidden />}
        </button>
        <button
          type="button"
          onClick={() => onClose()}
          aria-label={t("voice.end")}
          data-tour="voice-end"
          className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-scarlet text-on-scarlet shadow-float cursor-pointer"
        >
          <PhoneDisconnect size={28} weight="fill" aria-hidden />
        </button>
        <button
          type="button"
          onClick={() => onClose(true)}
          aria-label={t("voice.type")}
          className="inline-flex h-14 w-14 items-center justify-center rounded-full border border-line bg-surface cursor-pointer"
        >
          <Keyboard size={24} aria-hidden />
        </button>
      </div>
      <EventSheet eventId={open} onClose={() => setOpen(null)} />
    </motion.div>,
    document.body,
  );
}
