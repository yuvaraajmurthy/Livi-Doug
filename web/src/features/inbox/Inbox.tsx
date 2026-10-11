import { BellRinging, CalendarStar, ChatCircleDots, Sparkle } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { useLang, useT } from "../../i18n/useT";
import { clockLabel } from "../../lib/format";
import { useClock } from "../../session/clock";
import { PageTitle } from "../../ui/Card";
import { EmptyState, ErrorState, Skeleton } from "../../ui/States";
import { markSeen } from "./seen";

const ICON: Record<string, React.ReactNode> = {
  reminder: <BellRinging size={20} aria-hidden />,
  followup: <ChatCircleDots size={20} aria-hidden />,
  weekly_pick: <CalendarStar size={20} aria-hidden />,
};

export function Inbox() {
  const t = useT();
  const lang = useLang();
  const now = useClock();
  const inbox = useQuery({ queryKey: ["inbox"], queryFn: api.inbox });
  useEffect(() => {
    if (now) markSeen(now);
  }, [now, inbox.data]);

  return (
    <div>
      <PageTitle>{t("inbox.title")}</PageTitle>
      {inbox.isPending ? <Skeleton className="h-40" /> : null}
      {inbox.isError ? <ErrorState error={inbox.error} onRetry={() => inbox.refetch()} /> : null}
      {inbox.data && !inbox.data.items.length ? <EmptyState icon={<BellRinging size={28} aria-hidden />}>{t("inbox.empty")}</EmptyState> : null}
      {inbox.data?.items.length ? (
        <ul className="overflow-hidden rounded-[20px] border border-line bg-surface">
          {inbox.data.items.map((i, n) => (
            <li key={i.id} className={n ? "border-t border-line" : ""}>
              <Link to={i.deep_link} className="flex items-start gap-3 px-4 py-4 hover:bg-surface-2" data-tour={`inbox-${i.kind}`}>
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-2 text-ink">
                  {ICON[i.kind] ?? <Sparkle size={20} aria-hidden />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[16px] font-semibold leading-snug">{i.title}</span>
                  <span className="block text-[15px] text-ink-2">{i.body}</span>
                  <span className="mt-1 block text-[13px] text-ink-2 tabular">
                    {clockLabel(i.at, lang)}
                    {i.delivered === "push" ? " · push" : ""}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
