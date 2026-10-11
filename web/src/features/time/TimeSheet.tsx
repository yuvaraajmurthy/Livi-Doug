import { ArrowCounterClockwise, CalendarBlank, FastForward, SkipForward } from "@phosphor-icons/react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../../api/client";
import { signal } from "../../api/inspector";
import { useLang, useT } from "../../i18n/useT";
import { clockLabel } from "../../lib/format";
import { useClock } from "../../session/clock";
import { useSession } from "../../session/session";
import { startSession } from "../../session/start";
import { Sheet } from "../../ui/Sheet";
import { toast } from "../../ui/Toast";

/** The story's key moments, in Rutgers time. */
export const PRESETS: { label: string; now: string }[] = [
  { label: "Tue Oct 13 · 12:15 PM", now: "2026-10-13T12:15:00-04:00" },
  { label: "Tue Oct 13 · 3:30 PM", now: "2026-10-13T15:30:00-04:00" },
  { label: "Mon Oct 19 · 9:00 AM", now: "2026-10-19T09:00:00-04:00" },
  { label: "Tue Oct 27 · 9:00 AM", now: "2026-10-27T09:00:00-04:00" },
];

export async function skipTime(to: string) {
  const r = await api.skipAhead(to);
  signal("clock:changed", r.now);
  return r;
}

export async function jumpTime(now: string) {
  const r = await api.setClock(now);
  signal("clock:changed", r.now);
  return r;
}

export function TimeSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useT();
  const lang = useLang();
  const nav = useNavigate();
  const now = useClock();
  const s = useSession();
  const [busy, setBusy] = useState<string | null>(null);

  async function run(key: string, fn: () => Promise<unknown>) {
    if (busy) return;
    setBusy(key);
    try {
      await fn();
      onClose();
    } catch (e) {
      toast((e as Error).message, "amber");
    } finally {
      setBusy(null);
    }
  }

  const skip = (to: string) =>
    run(to, async () => {
      const r = await skipTime(to);
      if (!r.fired.some(f => f.delivered === "push" || f.delivered === "in_app")) toast(t("time.nothingDue"));
    });

  return (
    <Sheet open={open} onClose={onClose} title={t("time.title")}>
      <p className="text-[15px] text-ink-2">{t("time.now")}</p>
      <p className="mt-0.5 text-[22px] font-semibold tabular">{now ? clockLabel(now, lang) : "…"}</p>

      <div className="mt-5 flex flex-col gap-2">
        <Row icon={<SkipForward size={20} aria-hidden />} label={t("time.nextDue")} busy={busy === "next_due"} onClick={() => skip("next_due")} tour="skip-next" />
        <Row icon={<FastForward size={20} aria-hidden />} label={t("time.plusDay")} busy={busy === "+1d"} onClick={() => skip("+1d")} />
      </div>

      <h3 className="mb-2 mt-6 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-2">{t("time.jump")}</h3>
      <div className="grid grid-cols-2 gap-2">
        {PRESETS.map(p => (
          <button
            key={p.now}
            type="button"
            disabled={!!busy}
            onClick={() => run(p.now, () => jumpTime(p.now))}
            className="flex min-h-12 items-center gap-2 rounded-xl border border-line px-3 py-2 text-left text-[14px] font-medium hover:bg-surface-2 cursor-pointer disabled:opacity-50"
          >
            <CalendarBlank size={16} className="shrink-0 text-ink-2" aria-hidden />
            {p.label}
          </button>
        ))}
      </div>

      {s?.stage ? (
        <button
          type="button"
          disabled={!!busy}
          onClick={() =>
            window.confirm(t("time.resetConfirm")) &&
            run("reset", async () => {
              await api.reset();
              nav(await startSession(s.persona, { sandbox: false, stage: true }));
            })
          }
          className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-xl text-[15px] font-medium text-scarlet-ink hover:bg-scarlet-tint cursor-pointer"
        >
          <ArrowCounterClockwise size={18} aria-hidden />
          {t("time.reset")}
        </button>
      ) : null}
    </Sheet>
  );
}

function Row({ icon, label, onClick, busy, tour }: { icon: React.ReactNode; label: string; onClick: () => void; busy?: boolean; tour?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      aria-busy={busy || undefined}
      data-tour={tour}
      className="flex h-14 w-full items-center gap-3 rounded-2xl bg-ink px-4 text-left text-[16px] font-medium text-bg hover:opacity-90 cursor-pointer disabled:opacity-60"
    >
      {icon}
      {label}
    </button>
  );
}
