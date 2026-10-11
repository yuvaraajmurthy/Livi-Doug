import { Microphone } from "@phosphor-icons/react";
import { AnimatePresence } from "motion/react";
import { useState } from "react";
import { useT } from "../../i18n/useT";
import { VoiceOverlay } from "./VoiceOverlay";

/** Round mic button in the chat composer. Opens voice mode; when it closes, the chat reloads its history so the
 *  spoken turns appear in the thread. */
export function VoiceLauncher({ onEnded, conversationId }: { onEnded?: () => void; conversationId?: string | null }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("voice.open")}
        data-tour="voice-open"
        className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-ink hover:bg-surface-2 cursor-pointer"
      >
        <Microphone size={22} aria-hidden />
      </button>
      <AnimatePresence>
        {open ? (
          <VoiceOverlay
            conversationId={conversationId}
            onClose={typeInstead => {
              setOpen(false);
              onEnded?.();
              if (typeInstead) requestAnimationFrame(() => document.querySelector<HTMLElement>('[data-tour="chat-input"]')?.focus());
            }}
          />
        ) : null}
      </AnimatePresence>
    </>
  );
}
