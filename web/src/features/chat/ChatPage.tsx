import { ArrowUp, NotePencil, Sparkle } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useT } from "../../i18n/useT";
import type { Key } from "../../i18n/en";
import { useSession } from "../../session/session";
import { PERSONA_COPY } from "../entry/personas";
import { EventSheet } from "../event/EventSheet";
import { useMap } from "../map/useMap";
import { CrisisScreen } from "../safety/CrisisScreen";
import { VoiceLauncher } from "../voice/VoiceLauncher";
import { MessageView } from "./Message";
import { useChat } from "./useChat";

const GROWTH_CHIP: Record<string, Key> = {
  social: "chat.chip.social",
  financial: "chat.chip.financial",
  physical: "chat.chip.physical",
  intellectual: "chat.chip.intellectual",
  emotional: "chat.chip.emotional",
};

export function ChatPage() {
  const t = useT();
  const s = useSession();
  const map = useMap();
  const chat = useChat();
  const [text, setText] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const name = s && s.persona !== "staff" ? PERSONA_COPY[s.persona].name : "";

  const chips = useMemo(() => {
    const out: Key[] = [];
    const win = map.data?.profile.free_windows?.[0];
    if (win?.toLowerCase().startsWith("tue")) out.push("chat.chip.tuesday");
    const g = map.data?.profile.focus ?? map.data?.growth_areas?.[0];
    if (g && GROWTH_CHIP[g]) out.push(GROWTH_CHIP[g]);
    out.push("chat.chip.food", "chat.chip.study");
    return [...new Set(out)].slice(0, 4);
  }, [map.data]);

  // keep the newest message in view only if the student is already near the bottom
  useEffect(() => {
    const onScroll = () => {
      nearBottom.current = window.innerHeight + window.scrollY >= document.body.scrollHeight - 160;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  useLayoutEffect(() => {
    if (nearBottom.current) end.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [chat.messages]);

  const submit = (v = text) => {
    if (!v.trim() || chat.busy) return;
    nearBottom.current = true;
    void chat.send(v);
    setText("");
    requestAnimationFrame(() => input.current?.focus());
  };

  if (chat.crisis) return <CrisisScreen crisis={chat.crisis} onBack={chat.clearCrisis} />;

  const lastAssistant = [...chat.messages].reverse().find(m => m.role === "assistant")?.id;
  const empty = !chat.loading && chat.messages.length === 0;

  return (
    <div className="flex min-h-[calc(100dvh-14rem)] flex-col pb-28">
      <div className="mb-2 flex items-center justify-between">
        <h1 tabIndex={-1} className={empty ? "sr-only" : "text-[15px] font-medium text-ink-2 outline-none"}>
          {t("chat.title")}
        </h1>
        {!empty ? (
          <button
            type="button"
            onClick={() => void chat.newChat()}
            className="inline-flex h-10 items-center gap-1.5 rounded-full px-3 text-[14px] font-medium text-ink-2 hover:bg-surface-2 cursor-pointer"
          >
            <NotePencil size={16} aria-hidden />
            {t("chat.new")}
          </button>
        ) : null}
      </div>

      {empty ? (
        <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-6">
          <p className="display text-[44px] leading-[1.02]">{t("chat.hi", { name })}</p>
          <p className="mt-3 max-w-[34ch] text-[17px] leading-relaxed text-ink-2">{t("chat.lede")}</p>
          <ul className="mt-8 flex flex-col gap-2">
            {chips.map((c, i) => (
              <motion.li key={c} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.05 }}>
                <button
                  type="button"
                  onClick={() => submit(t(c))}
                  data-tour={`chat-chip-${i}`}
                  className="flex w-full items-center gap-3 rounded-[18px] border border-line bg-surface px-4 py-3.5 text-left text-[16px] hover:bg-surface-2 cursor-pointer"
                >
                  <Sparkle size={18} className="shrink-0 text-scarlet-ink" aria-hidden />
                  {t(c)}
                </button>
              </motion.li>
            ))}
          </ul>
        </motion.section>
      ) : (
        <div role="log" aria-live="polite" aria-label={t("chat.title")} className="flex flex-col gap-5">
          {chat.messages.map(m => (
            <MessageView key={m.id} m={m} onOpen={setOpen} latest={m.id === lastAssistant} />
          ))}
        </div>
      )}
      <div ref={end} />

      <form
        onSubmit={e => {
          e.preventDefault();
          submit();
        }}
        className="fixed inset-x-0 bottom-[calc(64px+env(safe-area-inset-bottom))] z-20 px-3 pb-2"
      >
        <div className="mx-auto flex max-w-[464px] items-end gap-1 rounded-[26px] border border-line bg-surface p-1.5 shadow-float">
          <label htmlFor="chat-input" className="sr-only">
            {t("chat.label")}
          </label>
          <textarea
            ref={input}
            id="chat-input"
            data-tour="chat-input"
            rows={1}
            value={text}
            maxLength={500}
            placeholder={t("chat.placeholder")}
            onChange={e => {
              setText(e.target.value);
              const el = e.target;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
            }}
            onKeyDown={e => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            className="max-h-[120px] min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-[16px] leading-6 outline-none placeholder:text-ink-2/70"
          />
          <VoiceLauncher onEnded={() => void chat.reload()} conversationId={chat.conversationId()} />
          <button
            type="submit"
            aria-label={t("chat.send")}
            disabled={!text.trim() || chat.busy}
            data-tour="chat-send"
            className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-scarlet text-on-scarlet transition-opacity disabled:bg-surface-2 disabled:text-ink-2 cursor-pointer disabled:cursor-default"
          >
            <ArrowUp size={20} weight="bold" aria-hidden />
          </button>
        </div>
      </form>

      <EventSheet eventId={open} onClose={() => setOpen(null)} />
    </div>
  );
}
