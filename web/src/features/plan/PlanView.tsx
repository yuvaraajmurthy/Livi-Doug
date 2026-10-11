import {
  ArrowLeft,
  BellRinging,
  CalendarPlus,
  ChatCircleDots,
  CheckCircle,
  GoogleLogo,
  MapPin,
  ShareNetwork,
  UserPlus,
} from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { signal } from "../../api/inspector";
import { apiBase } from "../../api/transport";
import { useLang, useT } from "../../i18n/useT";
import { timeLabel } from "../../lib/format";
import { enablePush, pushPermission, type PushState } from "../../push/push";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { Sheet } from "../../ui/Sheet";
import { toast } from "../../ui/Toast";
import { cleanTitle } from "../today/StepCard";
import { usePlans } from "./plans";

export function PlanView() {
  const t = useT();
  const lang = useLang();
  const nav = useNavigate();
  const { id } = useParams();
  const list = usePlans();
  const rec = list.find(p => String(p.commitment.commitment_id) === id) ?? null;
  const [calOpen, setCalOpen] = useState(false);
  const [push, setPush] = useState<PushState | null>(pushPermission() === "granted" ? "on" : null);
  const [pushBusy, setPushBusy] = useState(false);

  if (!rec) {
    return (
      <div>
        <h1 tabIndex={-1} className="text-[28px] font-semibold tracking-tight outline-none">
          {t("plan.title")}
        </h1>
        <p className="mt-3 text-[16px] text-ink-2">{t("plan.missing")}</p>
        <Link to="/you" className="mt-4 inline-block font-medium text-scarlet-ink underline underline-offset-4">
          {t("tab.you")}
        </Link>
      </div>
    );
  }
  const c = rec.commitment;
  const inviteUrl = `${window.location.origin}/i/${c.invite_token}`;
  const ics = c.ics_url.startsWith("http") ? c.ics_url : apiBase() + c.ics_url;

  async function invite() {
    const data = { title: cleanTitle(c.item.title), text: c.share_text, url: inviteUrl };
    try {
      if (typeof navigator.share === "function") {
        await navigator.share(data);
      } else {
        await navigator.clipboard.writeText(`${c.share_text} ${inviteUrl}`);
        toast(t("plan.linkCopied"));
      }
      signal("invite:shared", { token: c.invite_token });
    } catch {
      // user cancelled the share sheet
    }
  }

  async function reminders() {
    setPushBusy(true);
    const r = await enablePush();
    setPush(r);
    setPushBusy(false);
    if (r !== "on") toast(t("plan.remindersBlocked"), "amber");
  }

  return (
    <div>
      <Link to="/next" className="-ml-2 mb-3 inline-flex h-11 items-center gap-1.5 rounded-full px-2 text-[15px] text-ink-2 hover:bg-surface-2">
        <ArrowLeft size={18} aria-hidden />
        {t("tab.today")}
      </Link>
      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: "spring", stiffness: 420, damping: 24 }}
        className="mb-3 inline-flex items-center gap-2 rounded-full bg-green-tint px-3 py-1 text-[14px] font-semibold text-green"
      >
        <CheckCircle size={18} weight="fill" aria-hidden />
        {rec.status === "went" ? t("plan.went") : t("plan.title")}
      </motion.div>
      <h1 tabIndex={-1} className="display text-[34px] leading-[1.12] outline-none" data-tour="plan-text">
        “{c.plan_text}”
      </h1>

      <motion.div layoutId={`step-${c.item.id}`} transition={{ type: "spring", stiffness: 300, damping: 34 }} className="mt-6">
        <Card className="px-5 py-4">
          <p className="text-[18px] font-semibold leading-snug">{cleanTitle(c.item.title)}</p>
          <p className="mt-1 text-[15px] text-ink-2">{c.when_label}</p>
          {c.where.venue ? (
            <p className="mt-1 flex items-start gap-1.5 text-[15px] text-ink-2">
              <MapPin size={16} className="mt-0.5 shrink-0" aria-hidden />
              {c.where.venue}
            </p>
          ) : null}
          <div className="mt-4 flex flex-col gap-2 border-t border-line pt-4 text-[15px]">
            {c.reminder_at ? (
              <p className="flex items-center gap-2">
                <BellRinging size={18} className="text-scarlet-ink" aria-hidden />
                {t("plan.remind", { time: timeLabel(c.reminder_at, lang) })}
              </p>
            ) : null}
            {c.followup_at ? (
              <p className="flex items-center gap-2 text-ink-2">
                <ChatCircleDots size={18} aria-hidden />
                {t("plan.followupAt", { time: timeLabel(c.followup_at, lang) })}
              </p>
            ) : null}
            {rec.friendComing ? (
              <p className="flex items-center gap-2 text-green">
                <UserPlus size={18} aria-hidden />
                {t("plan.friendComing")}
              </p>
            ) : null}
          </div>
        </Card>
      </motion.div>

      <ul className="mt-5 flex flex-col gap-2">
        <li>
          <ActionRow
            icon={<CalendarPlus size={22} aria-hidden />}
            label={t("plan.calendar")}
            onClick={() => setCalOpen(true)}
            tour="add-calendar"
          />
        </li>
        <li>
          <ActionRow
            icon={<ShareNetwork size={22} aria-hidden />}
            label={t("plan.invite")}
            help={t("plan.inviteHelp")}
            onClick={invite}
            tour="invite"
          />
        </li>
        <li>
          <ActionRow
            icon={<BellRinging size={22} aria-hidden />}
            label={push === "on" ? t("plan.remindersOn") : t("plan.reminders")}
            help={push && push !== "on" ? t("plan.remindersBlocked") : undefined}
            onClick={reminders}
            done={push === "on"}
            busy={pushBusy}
            tour="reminders"
          />
        </li>
      </ul>

      <Button block className="mt-7" onClick={() => nav("/next")} data-tour="plan-done">
        {t("plan.done")}
      </Button>

      <Sheet open={calOpen} onClose={() => setCalOpen(false)} title={t("plan.calendar")}>
        <div className="flex flex-col gap-2 pt-2">
          <a
            href={c.google_calendar_url}
            target="_blank"
            rel="noreferrer"
            className="flex h-14 items-center gap-3 rounded-2xl border border-line px-4 text-[16px] font-medium hover:bg-surface-2"
          >
            <GoogleLogo size={22} aria-hidden />
            {t("plan.google")}
          </a>
          <a
            href={ics}
            className="flex h-14 items-center gap-3 rounded-2xl border border-line px-4 text-[16px] font-medium hover:bg-surface-2"
          >
            <CalendarPlus size={22} aria-hidden />
            {t("plan.ics")}
          </a>
        </div>
      </Sheet>
    </div>
  );
}

function ActionRow({
  icon,
  label,
  help,
  onClick,
  done,
  busy,
  tour,
}: {
  icon: React.ReactNode;
  label: string;
  help?: string;
  onClick: () => void;
  done?: boolean;
  busy?: boolean;
  tour?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      data-tour={tour}
      className="flex min-h-16 w-full items-center gap-4 rounded-2xl border border-line bg-surface px-4 py-3 text-left hover:bg-surface-2 cursor-pointer disabled:cursor-wait"
    >
      <span
        className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${done ? "bg-green-tint text-green" : "bg-surface-2 text-ink"}`}
      >
        {done ? <CheckCircle size={22} weight="fill" aria-hidden /> : icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[16px] font-medium">{label}</span>
        {help ? <span className="block text-[14px] text-ink-2">{help}</span> : null}
      </span>
    </button>
  );
}
