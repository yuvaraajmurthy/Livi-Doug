import { Brain, CalendarBlank, CalendarCheck, CaretRight } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { signal } from "../../api/inspector";
import { useT } from "../../i18n/useT";
import { timeLabel, shortDate } from "../../lib/format";
import { SourceBadge } from "../../ui/Badge";
import { Spinner } from "../../ui/Spinner";
import { cleanTitle } from "../today/StepCard";
import { SupportFirst } from "../today/SupportFirst";
import type { ChatMessage, EventChip, UIEvent } from "./types";

export function MessageView({ m, onOpen, latest }: { m: ChatMessage; onOpen: (id: string) => void; latest: boolean }) {
  if (m.role === "user") {
    return (
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-[20px] rounded-br-md bg-ink px-4 py-2.5 text-[16px] leading-6 text-bg">
          {m.text}
        </p>
      </motion.div>
    );
  }
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-3">
      {m.blocks.map((b, i) => (
        <Block key={i} b={b} onOpen={onOpen} latest={latest} />
      ))}
      {m.text ? (
        <p className="whitespace-pre-wrap text-[17px] leading-[1.55]">
          {m.text}
          {m.pending ? <span className="ml-0.5 inline-block h-[1.1em] w-[2px] translate-y-[3px] animate-pulse bg-ink" aria-hidden /> : null}
        </p>
      ) : null}
      {m.pending && (m.status || (!m.text && !m.blocks.length)) ? (
        <p className="flex items-center gap-2 text-[15px] text-ink-2" role="status">
          <Spinner className="scale-75" />
          {m.status ?? "Thinking…"}
        </p>
      ) : null}
    </motion.div>
  );
}

function Block({ b, onOpen, latest }: { b: UIEvent; onOpen: (id: string) => void; latest: boolean }) {
  if (b.type === "events") return <EventList items={b.items} onOpen={onOpen} latest={latest} />;
  if (b.type === "memory") return <MemoryChip id={b.id} statement={b.statement} />;
  if (b.type === "plan") return <PlanChip plan={b.plan} />;
  if (b.type === "support") return <SupportFirst card={b.card} />;
  return null;
}

function EventList({ items, onOpen, latest }: { items: EventChip[]; onOpen: (id: string) => void; latest: boolean }) {
  return (
    <ul className="flex flex-col gap-2">
      {items.map((e, i) => (
        <motion.li key={e.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
          <button
            type="button"
            onClick={() => {
              onOpen(e.id);
              signal("event:opened", e.id);
            }}
            data-tour={latest ? `chat-event-${i}` : undefined}
            className="flex w-full items-center gap-3 rounded-[18px] border border-line bg-surface px-4 py-3 text-left transition-colors hover:bg-surface-2 cursor-pointer"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-scarlet-tint text-scarlet-ink">
              <CalendarBlank size={20} aria-hidden />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-start gap-2">
                <span className="text-[16px] font-semibold leading-snug">{cleanTitle(e.title)}</span>
              </span>
              <span className="mt-0.5 block text-[14px] leading-snug text-ink-2">
                {[e.when_label, e.venue, e.cost_label].filter(Boolean).join(" · ")}
              </span>
            </span>
            <span className="flex shrink-0 flex-col items-end gap-1">
              <SourceBadge synthetic={e.synthetic} />
              <CaretRight size={18} className="text-ink-2" aria-hidden />
            </span>
          </button>
        </motion.li>
      ))}
    </ul>
  );
}

function MemoryChip({ id, statement }: { id: string; statement: string }) {
  const t = useT();
  const [state, setState] = useState<"saved" | "busy" | "gone">("saved");
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 self-start rounded-full bg-surface-2 px-3 py-1.5 text-[14px]" data-tour="memory-chip">
      <Brain size={16} className="text-scarlet-ink" aria-hidden />
      {state === "gone" ? (
        <span className="text-ink-2">{t("chat.forgotten")}</span>
      ) : (
        <>
          <span>
            {t("chat.saved")} <span className="font-medium">{statement}</span>
          </span>
          <button
            type="button"
            disabled={state === "busy"}
            onClick={async () => {
              setState("busy");
              try {
                await api.deleteMemory(id);
                setState("gone");
              } catch {
                setState("saved");
              }
            }}
            className="font-medium text-scarlet-ink underline underline-offset-2 cursor-pointer disabled:opacity-50"
          >
            {t("chat.undo")}
          </button>
        </>
      )}
    </p>
  );
}

function PlanChip({ plan }: { plan: { commitment_id: number; reminder_at?: string | null; when_label: string } }) {
  const t = useT();
  return (
    <Link
      to={`/plan/${plan.commitment_id}`}
      className="flex items-center gap-2 self-start rounded-full bg-green-tint px-3 py-1.5 text-[14px] font-medium text-green"
    >
      <CalendarCheck size={16} aria-hidden />
      {plan.reminder_at
        ? t("chat.reminderSet", { when: `${shortDate(plan.reminder_at)} ${timeLabel(plan.reminder_at)}` })
        : plan.when_label}
      <span className="underline underline-offset-2">{t("today.viewPlan")}</span>
    </Link>
  );
}
