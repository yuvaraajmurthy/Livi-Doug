import { useState } from "react";
import { api, isCrisis, type CrisisResponse, type Dimension } from "../../api/client";
import { signal } from "../../api/inspector";
import { useT } from "../../i18n/useT";
import { Button } from "../../ui/Button";
import { CrisisScreen } from "../safety/CrisisScreen";

export function WinPrompt({ dimension }: { dimension: Dimension | null }) {
  const t = useT();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [skipped, setSkipped] = useState(false);
  const [crisis, setCrisis] = useState<CrisisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (crisis) return <CrisisScreen crisis={crisis} onBack={() => setCrisis(null)} />;
  if (skipped) return null;
  if (done)
    return (
      <p role="status" className="rounded-2xl bg-green-tint px-4 py-3 text-[16px] font-medium text-green">
        {done}
      </p>
    );

  async function post() {
    if (busy || !text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.postWin(text.trim(), dimension);
      setText("");
      if (isCrisis(r)) setCrisis(r);
      else {
        setDone(r.message);
        signal("win:posted");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-[20px] border border-line bg-surface p-4">
      <label htmlFor="win" className="block text-[17px] font-semibold">
        {t("followup.winTitle")}
      </label>
      <p id="win-help" className="mt-1 text-[14px] text-ink-2">
        {t("followup.winHelp")}
      </p>
      <textarea
        id="win"
        value={text}
        onChange={e => setText(e.target.value.slice(0, 140))}
        rows={2}
        maxLength={140}
        aria-describedby="win-help"
        placeholder={t("followup.winPlaceholder")}
        className="mt-3 w-full resize-none rounded-xl border border-line-strong bg-bg px-3 py-2.5 text-[16px] placeholder:text-ink-2/60"
      />
      {error ? (
        <p role="alert" className="mt-2 text-[14px] text-scarlet-ink">
          {error}
        </p>
      ) : null}
      <div className="mt-3 flex gap-2">
        <Button size="sm" onClick={post} loading={busy} disabled={!text.trim()}>
          {t("followup.winPost")}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setSkipped(true)}>
          {t("followup.winSkip")}
        </Button>
      </div>
    </div>
  );
}
