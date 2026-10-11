import { ArrowClockwise, ArrowLeft, ArrowRight, DeviceMobile } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";
import { MAIN_STORY } from "../story";
import { NOTES_CHANNEL, type NotesCommand, type NotesState } from "./notesChannel";
import { useQr } from "./Slides";

/** Presenter window (/present/notes): speaker notes, what's next, timer, live requests, mode switches, phone pairing.
 *  Synced with the audience screen through BroadcastChannel; keyboard works here too. */
export function Notes() {
  const ch = useRef<BroadcastChannel | null>(null);
  const [s, setS] = useState<NotesState | null>(null);
  const [, tick] = useState(0);
  const [pair, setPair] = useState(false);
  const send = (c: NotesCommand) => ch.current?.postMessage(c);

  useEffect(() => {
    const c = new BroadcastChannel(NOTES_CHANNEL);
    ch.current = c;
    c.onmessage = (e: MessageEvent<NotesState>) => e.data?.kind === "state" && setS(e.data);
    c.postMessage({ kind: "hello" } satisfies NotesCommand);
    const t = setInterval(() => tick(x => x + 1), 1000);
    const key = (e: KeyboardEvent) => {
      if (["ArrowRight", "PageDown", " "].includes(e.key)) {
        e.preventDefault();
        c.postMessage({ kind: "next" } satisfies NotesCommand);
      } else if (["ArrowLeft", "PageUp"].includes(e.key)) {
        e.preventDefault();
        c.postMessage({ kind: "back" } satisfies NotesCommand);
      }
    };
    window.addEventListener("keydown", key);
    return () => {
      c.close();
      clearInterval(t);
      window.removeEventListener("keydown", key);
    };
  }, []);

  const step = s ? MAIN_STORY[s.index] : null;
  const next = s ? MAIN_STORY[s.index + 1] : null;
  const secs = s?.startedAt ? Math.floor((Date.now() - s.startedAt) / 1000) : 0;
  const qr = useQr(s?.token ? `${window.location.origin}/join#t=${encodeURIComponent(s.token)}` : `${window.location.origin}/tour`);

  return (
    <main className="min-h-dvh bg-bg p-6 text-ink">
      {!s ? (
        <p className="text-ink-2">Waiting for the stage window… open /present in another window.</p>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex items-center justify-between text-[14px] text-ink-2">
            <span className="tabular">
              {s.index + 1} / {MAIN_STORY.length} · {s.status}
            </span>
            <span className={`tabular font-semibold ${secs > 180 ? "text-scarlet-ink" : "text-ink"}`}>
              {Math.floor(secs / 60)}:{String(secs % 60).padStart(2, "0")} / 3:00
            </span>
          </div>
          <section>
            <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-scarlet-ink">{step?.chapter}</p>
            <p className="display mt-1 text-[32px] leading-tight">{step?.claim}</p>
            {step?.note ? <p className="mt-3 text-[17px] leading-relaxed">{step.note}</p> : null}
            {s.error ? <p className="mt-2 text-amber">{s.error}</p> : null}
          </section>
          {next ? (
            <section className="rounded-2xl border border-line p-4">
              <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-2">Next</p>
              <p className="mt-1 text-[17px] font-medium">{next.claim}</p>
            </section>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => send({ kind: "back" })} className="inline-flex h-11 items-center gap-1 rounded-full border border-line px-4 cursor-pointer">
              <ArrowLeft size={16} aria-hidden /> Back
            </button>
            <button type="button" onClick={() => send({ kind: "next" })} className="inline-flex h-11 items-center gap-1 rounded-full bg-ink px-5 font-semibold text-bg cursor-pointer">
              Next <ArrowRight size={16} aria-hidden />
            </button>
            <button type="button" onClick={() => send({ kind: "templates" })} className={`h-11 rounded-full border px-4 cursor-pointer ${s.templates ? "border-amber bg-amber-tint text-amber" : "border-line"}`}>
              AI {s.templates ? "off" : "on"}
            </button>
            <button type="button" onClick={() => send({ kind: "offline" })} className={`h-11 rounded-full border px-4 cursor-pointer ${s.offline ? "border-amber bg-amber-tint text-amber" : "border-line"}`}>
              {s.offline ? "Offline replay" : "Live"}
            </button>
            <button type="button" onClick={() => setPair(p => !p)} className="inline-flex h-11 items-center gap-1 rounded-full border border-line px-4 cursor-pointer">
              <DeviceMobile size={16} aria-hidden /> Pair phone
            </button>
            <button
              type="button"
              onClick={() => window.confirm("Restart with fresh students?") && send({ kind: "restart" })}
              className="inline-flex h-11 items-center gap-1 rounded-full border border-line px-4 text-scarlet-ink cursor-pointer"
            >
              <ArrowClockwise size={16} aria-hidden /> Restart
            </button>
          </div>
          {pair && qr ? (
            <div className="flex items-center gap-4 rounded-2xl border border-line p-4">
              <img src={qr} alt="Pairing QR code" className="h-40 w-40" />
              <p className="text-[15px] text-ink-2">
                {s.token ? "Scan, then turn on Reminders on the phone. Skips on stage push to it." : "Start the story first, then pair."}
              </p>
            </div>
          ) : null}
          <section>
            <p className="mb-2 text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-2">Live requests</p>
            <ul className="flex flex-col gap-1 font-mono text-[12px] text-ink-2">
              {s.calls.map(c => (
                <li key={c.id} className="flex gap-3">
                  <span className="w-12 font-semibold text-ink">{c.method}</span>
                  <span className="flex-1 truncate">{c.path.replace(/\?.*$/, "")}</span>
                  <span className="tabular">{c.ms} ms</span>
                  <span>{c.source === "replay" ? "replay" : c.fallback ?? c.status}</span>
                </li>
              ))}
            </ul>
          </section>
          <p className="text-[12px] text-ink-2">Keys on the stage: → next · ← back · 1–9 chapter · A AI · O offline · F fullscreen · N this window</p>
        </div>
      )}
    </main>
  );
}
