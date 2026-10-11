import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { useParams } from "react-router";
import { api, type FollowupResponse } from "../../api/client";
import { signal } from "../../api/inspector";
import { useT } from "../../i18n/useT";
import { Button } from "../../ui/Button";
import { plans, usePlans } from "../plan/plans";
import { cleanTitle } from "../today/StepCard";
import { FollowupResult } from "./FollowupResult";

export function Followup() {
  const t = useT();
  const qc = useQueryClient();
  const { id } = useParams();
  const cid = Number(id);
  usePlans();
  const rec = plans.get(cid);
  const [went, setWent] = useState<boolean | null>(null);
  const [helped, setHelped] = useState<number | null>(null);
  const [result, setResult] = useState<FollowupResponse | null>(rec?.followup ?? null);

  const send = useMutation({
    mutationFn: (body: { went: boolean; helped?: number | null }) => api.followup(cid, body),
    onSuccess: r => {
      plans.update(cid, { status: r.status, helped, followup: r });
      setResult(r);
      signal("followup:submitted", r);
      for (const k of ["memory", "pulse", "next", "map"]) void qc.invalidateQueries({ queryKey: [k] });
    },
  });

  const submit = (body: { went: boolean; helped?: number | null }) => {
    if (send.isPending || result) return;
    send.mutate(body);
  };

  if (result) return <FollowupResult r={result} title={rec ? cleanTitle(rec.commitment.item.title) : null} />;

  const title = rec ? cleanTitle(rec.commitment.item.title) : null;
  return (
    <div>
      <p className="text-[15px] text-ink-2">{rec?.commitment.when_label}</p>
      <h1 tabIndex={-1} className="display mt-1 text-[36px] leading-[1.08] outline-none">
        {title ? t("followup.howWas", { title }) : t("followup.howGeneric")}
      </h1>

      <section className="mt-8" aria-labelledby="q-went">
        <h2 id="q-went" className="text-[20px] font-semibold">
          {t("followup.went")}
        </h2>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {[true, false].map(v => (
            <button
              key={String(v)}
              type="button"
              aria-pressed={went === v}
              data-tour={v ? "went-yes" : "went-no"}
              onClick={() => {
                setWent(v);
                if (!v) setHelped(null);
              }}
              className={`h-14 rounded-2xl border text-[17px] font-medium transition-colors cursor-pointer ${
                went === v ? "border-ink bg-ink text-bg" : "border-line-strong/60 bg-surface hover:bg-surface-2"
              }`}
            >
              {v ? t("followup.yes") : t("followup.no")}
            </button>
          ))}
        </div>
      </section>

      <AnimatePresence>
        {went ? (
          <motion.section
            key="helped"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-8"
            aria-labelledby="q-helped"
          >
            <h2 id="q-helped" className="text-[20px] font-semibold">
              {t("followup.helped")}
            </h2>
            <div role="radiogroup" aria-labelledby="q-helped" className="mt-3 grid grid-cols-5 gap-2">
              {[1, 2, 3, 4, 5].map(n => (
                <button
                  key={n}
                  type="button"
                  role="radio"
                  aria-checked={helped === n}
                  aria-label={String(n)}
                  data-tour={`helped-${n}`}
                  onClick={() => setHelped(n)}
                  className={`h-14 rounded-2xl border text-[19px] font-semibold tabular transition-colors cursor-pointer ${
                    helped === n ? "border-scarlet bg-scarlet text-on-scarlet" : "border-line-strong/60 bg-surface hover:bg-surface-2"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
            <div className="mt-2 flex justify-between text-[13px] text-ink-2">
              <span>{t("followup.helpedLow")}</span>
              <span>{t("followup.helpedHigh")}</span>
            </div>
          </motion.section>
        ) : null}
      </AnimatePresence>

      {send.isError ? (
        <p role="alert" className="mt-4 text-[15px] text-scarlet-ink">
          {(send.error as Error).message}
        </p>
      ) : null}

      <Button
        block
        className="mt-8"
        disabled={went === null || (went && helped === null)}
        loading={send.isPending}
        onClick={() => submit(went ? { went: true, helped } : { went: false })}
        data-tour="followup-send"
      >
        {t("followup.submit")}
      </Button>
    </div>
  );
}
