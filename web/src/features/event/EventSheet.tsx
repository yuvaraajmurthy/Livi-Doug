import {
  ArrowSquareOut,
  CalendarBlank,
  CalendarPlus,
  CheckCircle,
  Globe,
  MapPin,
  NavigationArrow,
  Phone,
  Tag,
  UsersThree,
} from "@phosphor-icons/react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { signal } from "../../api/inspector";
import { useLang, useT } from "../../i18n/useT";
import type { Key } from "../../i18n/en";
import { timeLabel } from "../../lib/format";
import { SourceBadge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Sheet } from "../../ui/Sheet";
import { ErrorState, Skeleton } from "../../ui/States";
import { plans } from "../plan/plans";
import { cleanTitle } from "../today/StepCard";

const EventMap = lazy(() => import("./EventMap").then(m => ({ default: m.EventMap })));

/** The event card (spec §5.3): opened from chat or voice buttons. Fixed signature: { eventId, onClose }. */
export function EventSheet({ eventId, onClose }: { eventId: string | null; onClose: () => void }) {
  const t = useT();
  const lang = useLang();
  const q = useQuery({ queryKey: ["item", eventId], queryFn: () => api.item(eventId!), enabled: !!eventId });
  const remind = useMutation({
    mutationFn: () => api.remind(eventId!),
    onSuccess: c => {
      plans.add(c);
      signal("commitment:created", c);
      signal("reminder:set");
    },
  });
  const d = q.data;
  const place = d ? [d.venue, d.address].filter(Boolean).join(", ") : "";
  const quiet =
    "inline-flex h-11 items-center gap-1.5 rounded-xl border border-line bg-surface px-3.5 text-[15px] font-medium hover:bg-surface-2";

  return (
    <Sheet open={!!eventId} onClose={onClose} title={d ? cleanTitle(d.title) : t("common.loading")}>
      {q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : null}
      {!d && !q.isError ? (
        <div aria-hidden className="flex flex-col gap-3">
          <Skeleton className="h-[160px] rounded-2xl" />
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="mt-2 h-14 rounded-2xl" />
        </div>
      ) : null}
      {d ? (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <SourceBadge synthetic={d.synthetic} />
            {d.dimensions.slice(0, 3).map(x => (
              <span key={x} className="rounded-full bg-surface-2 px-2.5 py-0.5 text-[13px] font-medium text-ink-2">
                {t(`dim.${x}` as Key)}
              </span>
            ))}
          </div>

          {d.lat != null && d.lon != null ? (
            <Suspense fallback={<Skeleton className="h-[160px] rounded-2xl" />}>
              <EventMap lat={d.lat} lon={d.lon} label={place || cleanTitle(d.title)} />
            </Suspense>
          ) : d.campus === "online" ? (
            <div className="flex h-[72px] items-center gap-3 rounded-2xl bg-surface-2 px-4 text-[15px]">
              <Globe size={22} className="text-scarlet-ink" aria-hidden />
              {t("event.online")}
            </div>
          ) : null}

          <ul className="flex flex-col gap-2.5 text-[16px]">
            <li className="flex items-start gap-3">
              <CalendarBlank size={20} className="mt-0.5 shrink-0 text-ink-2" aria-hidden />
              {d.when_label}
            </li>
            {place ? (
              <li className="flex items-start gap-3">
                <MapPin size={20} className="mt-0.5 shrink-0 text-ink-2" aria-hidden />
                <span>
                  {place}
                  {d.walk_min != null ? <span className="text-ink-2"> · {t("event.walk", { n: d.walk_min })}</span> : null}
                </span>
              </li>
            ) : null}
            <li className="flex items-start gap-3">
              <Tag size={20} className="mt-0.5 shrink-0 text-ink-2" aria-hidden />
              {d.cost_label}
            </li>
            {d.going.label ? (
              <li className="flex items-start gap-3">
                <UsersThree size={20} className="mt-0.5 shrink-0 text-ink-2" aria-hidden />
                {d.going.label}
              </li>
            ) : null}
            {d.hours_text ? <li className="pl-8 text-[15px] text-ink-2">{d.hours_text}</li> : null}
          </ul>

          {d.summary ? <p className="text-[16px] leading-relaxed text-ink-2">{d.summary}</p> : null}

          {remind.isSuccess ? (
            <div role="status" className="flex flex-wrap items-center gap-2 rounded-2xl bg-green-tint px-4 py-3 text-[16px] font-medium text-green">
              <CheckCircle size={20} weight="fill" aria-hidden />
              {remind.data.reminder_at
                ? t("event.reminderAt", { time: timeLabel(remind.data.reminder_at, lang) })
                : t("event.planned")}
              <Link to={`/plan/${remind.data.commitment_id}`} onClick={onClose} className="ml-auto underline underline-offset-2">
                {t("today.viewPlan")}
              </Link>
            </div>
          ) : (
            <Button block loading={remind.isPending} onClick={() => !remind.isPending && remind.mutate()} data-tour="event-remind">
              {t("event.remind")}
            </Button>
          )}
          {remind.isError ? (
            <p role="alert" className="text-[15px] text-scarlet-ink">
              {(remind.error as Error).message}
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <a href={d.directions_url} target="_blank" rel="noreferrer" className={quiet} data-tour="event-directions">
              <NavigationArrow size={18} aria-hidden />
              {t("event.directions")}
            </a>
            {d.calendar_url ? (
              <a href={d.calendar_url} target="_blank" rel="noreferrer" className={quiet}>
                <CalendarPlus size={18} aria-hidden />
                {t("plan.calendar")}
              </a>
            ) : null}
            {d.phone ? (
              <a href={`tel:${d.phone}`} className={quiet}>
                <Phone size={18} aria-hidden />
                {d.phone}
              </a>
            ) : null}
            {d.url ? (
              <a href={d.url} target="_blank" rel="noreferrer" className={quiet}>
                <ArrowSquareOut size={18} aria-hidden />
                {t("event.website")}
              </a>
            ) : null}
          </div>

          <p className="text-[13px] text-ink-2">
            {d.source.name}
            {d.source.verified_on ? ` · ${t("event.verified", { date: d.source.verified_on })}` : ""}
          </p>
        </div>
      ) : null}
    </Sheet>
  );
}
