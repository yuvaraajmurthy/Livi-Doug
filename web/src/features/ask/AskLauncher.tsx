import { MagnifyingGlass } from "@phosphor-icons/react";
import { useState } from "react";
import { useT } from "../../i18n/useT";
import { AskSheet } from "./AskSheet";

export function AskLauncher({ className = "" }: { className?: string }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-tour="ask-open"
        className={`flex h-14 w-full items-center gap-3 rounded-full border border-line bg-surface px-5 text-left text-[16px] text-ink-2 hover:bg-surface-2 cursor-pointer ${className}`}
      >
        <MagnifyingGlass size={20} aria-hidden />
        {t("today.ask")}
      </button>
      <AskSheet open={open} onClose={() => setOpen(false)} />
    </>
  );
}
