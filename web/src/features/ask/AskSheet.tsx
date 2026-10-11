import { ArrowSquareOut, MapPin, Phone } from "@phosphor-icons/react";
import { useState } from "react";
import { api, isCrisis, type AskResult, type CrisisResponse } from "../../api/client";
import { signal } from "../../api/inspector";
import { useT } from "../../i18n/useT";
import { SourceBadge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Sheet } from "../../ui/Sheet";
import { CrisisScreen } from "../safety/CrisisScreen";
import { cleanTitle } from "../today/StepCard";

const SUGGESTIONS = ["Free food this week?", "Somewhere quiet to study tonight", "Help with Calc homework"];

export function AskSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useT();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<Exclude<AskResult, CrisisResponse> | null>(null);
  const [crisis, setCrisis] = useState<CrisisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ask(question: string) {
    if (busy || !question.trim()) return;
    setBusy(true);
    setError(null);
    setAnswer(null);
    try {
      const r = await api.ask(question.trim());
      if (isCrisis(r)) {
        setQ("");
        setCrisis(r);
      } else {
        setAnswer(r);
        signal("ask:answered", r);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (crisis && open) return <CrisisScreen crisis={crisis} onBack={() => { setCrisis(null); onClose(); }} />;

  return (
    <Sheet open={open} onClose={onClose} title={t("ask.title")}>
      <form
        onSubmit={e => {
          e.preventDefault();
          void ask(q);
        }}
        className="pt-1"
      >
        <label htmlFor="ask-q" className="sr-only">
          {t("ask.title")}
        </label>
        <div className="flex gap-2">
          <input
            id="ask-q"
            data-tour="ask-input"
            value={q}
            onChange={e => setQ(e.target.value.slice(0, 300))}
            placeholder={t("ask.placeholder")}
            autoComplete="off"
            enterKeyHint="send"
            className="h-12 min-w-0 flex-1 rounded-xl border border-line-strong bg-bg px-3.5 text-[16px] placeholder:text-ink-2/70"
          />
          <Button type="submit" size="md" loading={busy} disabled={!q.trim()} data-tour="ask-send">
            {t("ask.send")}
          </Button>
        </div>
        <p className="mt-2 text-[13px] text-ink-2">{t("ask.scope")}</p>
      </form>

      {!answer && !busy ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {SUGGESTIONS.map(s => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setQ(s);
                void ask(s);
              }}
              className="min-h-10 rounded-full bg-surface-2 px-3.5 py-2 text-[14px] font-medium hover:brightness-95 cursor-pointer"
            >
              {s}
            </button>
          ))}
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="mt-4 text-[15px] text-scarlet-ink">
          {error}
        </p>
      ) : null}

      {answer ? (
        <div className="mt-5" aria-live="polite">
          <p className="text-[16px] leading-relaxed">{answer.text}</p>
          {answer.items.length ? (
            <ul className="mt-4 flex flex-col gap-2">
              {answer.items.map(i => (
                <li key={i.id} className="rounded-2xl border border-line px-4 py-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-[16px] font-semibold leading-snug">{cleanTitle(i.title)}</p>
                    <SourceBadge synthetic={i.synthetic} />
                  </div>
                  {i.when_label ? <p className="text-[14px] text-ink-2">{i.when_label}</p> : null}
                  {i.where.venue ? (
                    <p className="mt-0.5 flex items-center gap-1 text-[14px] text-ink-2">
                      <MapPin size={14} aria-hidden />
                      {i.where.venue}
                    </p>
                  ) : null}
                  <div className="mt-2 flex gap-3 text-[14px] font-medium">
                    {i.url ? (
                      <a href={i.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-scarlet-ink">
                        Open <ArrowSquareOut size={14} aria-hidden />
                      </a>
                    ) : null}
                    {i.phone ? (
                      <a href={`tel:${i.phone}`} className="inline-flex items-center gap-1 text-scarlet-ink">
                        <Phone size={14} aria-hidden /> {i.phone}
                      </a>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
          <p className="mt-3 text-[12px] text-ink-2">{answer.source === "ai" ? t("why.wordingAi") : t("why.wordingTemplate")}</p>
        </div>
      ) : null}
    </Sheet>
  );
}
