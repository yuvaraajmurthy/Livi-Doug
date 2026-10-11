import { ChatCircleText, Phone, Siren } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useEffect, useRef } from "react";
import type { CrisisLine, CrisisResponse } from "../../api/client";
import { signal } from "../../api/inspector";
import { useT } from "../../i18n/useT";
import { Button } from "../../ui/Button";

function LineIcon({ kind }: { kind: string }) {
  if (kind === "text") return <ChatCircleText size={22} aria-hidden />;
  if (kind === "emergency") return <Siren size={22} aria-hidden />;
  return <Phone size={22} aria-hidden />;
}

export function CrisisLineRow({ line }: { line: CrisisLine }) {
  const t = useT();
  return (
    <a
      href={line.href ?? undefined}
      className="flex min-h-16 items-center gap-4 rounded-2xl border border-line bg-surface px-4 py-3 hover:bg-surface-2"
    >
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-scarlet-tint text-scarlet-ink">
        <LineIcon kind={line.kind} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[17px] font-semibold leading-snug">{line.name}</span>
        <span className="block text-[15px] text-ink-2">
          {line.contact} · {line.hours}
        </span>
      </span>
      {!line.verified ? (
        <span className="shrink-0 rounded-full bg-surface-2 px-2 py-0.5 text-[12px] font-medium text-ink-2">
          {t("common.verifying")}
        </span>
      ) : null}
    </a>
  );
}

/** Fixed support card. Calm, no echo of what was typed, every line a real tel:/sms: link. */
export function CrisisScreen({ crisis, onBack }: { crisis: CrisisResponse; onBack: () => void }) {
  const t = useT();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
    signal("crisis:shown");
  }, []);
  return (
    <motion.div
      role="region"
      aria-labelledby="crisis-title"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="fixed inset-0 z-[60] overflow-y-auto bg-bg"
      data-tour="crisis"
    >
      <div className="mx-auto max-w-[480px] px-5 pb-[calc(32px+env(safe-area-inset-bottom))] pt-[max(40px,env(safe-area-inset-top))]">
        <h1 ref={heading} id="crisis-title" tabIndex={-1} className="display text-[38px] leading-[1.05] outline-none">
          {crisis.title}
        </h1>
        <p className="mt-4 text-[17px] leading-relaxed text-ink-2">{crisis.message}</p>
        <ul className="mt-7 flex flex-col gap-2.5">
          {crisis.lines.map(l => (
            <li key={l.id}>
              <CrisisLineRow line={l} />
            </li>
          ))}
        </ul>
        <Button variant="secondary" block className="mt-8" onClick={onBack}>
          {t("crisis.back")}
        </Button>
      </div>
    </motion.div>
  );
}
