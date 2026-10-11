import { CalendarBlank, CheckCircle, MapPin, UsersThree } from "@phosphor-icons/react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useParams } from "react-router";
import { api } from "../../api/client";
import { useT } from "../../i18n/useT";
import { SourceBadge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { LogoMark } from "../../ui/Logo";
import { ErrorState, Skeleton } from "../../ui/States";
import { cleanTitle } from "../today/StepCard";

/** What a friend sees from the share link. No account, no tab bar, no data about the inviter. */
export function InvitePage() {
  const t = useT();
  const { token = "" } = useParams();
  const view = useQuery({ queryKey: ["invite", token], queryFn: () => api.invite(token) });
  const accept = useMutation({ mutationFn: () => api.acceptInvite(token) });
  const accepted = accept.isSuccess || view.data?.accepted;

  return (
    <main id="main" className="mx-auto max-w-[480px] px-5 pb-12 pt-[max(28px,env(safe-area-inset-top))]">
      <div className="flex items-center gap-2">
        <LogoMark size={28} />
        <span className="display text-[24px] leading-none">Compass</span>
      </div>
      <p className="mt-8 text-[17px] text-ink-2">{t("invite.note")}</p>
      {view.isPending ? <Skeleton className="mt-6 h-56" /> : null}
      {view.isError ? <div className="mt-6"><ErrorState error={view.error} onRetry={() => view.refetch()} /></div> : null}
      {view.data ? (
        <Card elevated className="mt-6 px-5 py-5">
          <div className="mb-2 flex justify-end">
            <SourceBadge synthetic={view.data.item.synthetic} />
          </div>
          <h1 tabIndex={-1} className="text-[26px] font-semibold leading-8 tracking-tight outline-none">
            {cleanTitle(view.data.item.title)}
          </h1>
          {view.data.item.summary ? <p className="mt-2 text-[16px] text-ink-2">{view.data.item.summary}</p> : null}
          <ul className="mt-4 flex flex-col gap-2 text-[16px]">
            <li className="flex items-center gap-2.5">
              <CalendarBlank size={20} className="text-ink-2" aria-hidden />
              {view.data.when_label}
            </li>
            {view.data.where.venue ? (
              <li className="flex items-center gap-2.5">
                <MapPin size={20} className="text-ink-2" aria-hidden />
                {view.data.where.venue}
              </li>
            ) : null}
            {view.data.going.label ? (
              <li className="flex items-center gap-2.5">
                <UsersThree size={20} className="text-ink-2" aria-hidden />
                {view.data.going.label}
              </li>
            ) : null}
          </ul>
          <div className="mt-6">
            {accepted ? (
              <motion.p
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                role="status"
                className="flex items-center gap-2 rounded-2xl bg-green-tint px-4 py-3.5 text-[17px] font-semibold text-green"
              >
                <CheckCircle size={22} weight="fill" aria-hidden />
                {t("invite.accepted")}
              </motion.p>
            ) : (
              <Button block loading={accept.isPending} onClick={() => accept.mutate()}>
                {t("invite.accept")}
              </Button>
            )}
          </div>
        </Card>
      ) : null}
    </main>
  );
}
