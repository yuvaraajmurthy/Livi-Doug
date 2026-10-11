import { Database } from "@phosphor-icons/react";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import { signal } from "../../api/inspector";
import { Button } from "../../ui/Button";
import { Panel } from "./shared";

const EXAMPLES = [
  "Which campus has the fewest financial resources per student with a low score?",
  "Attendance rate by campus for social steps",
  "How many students brought a friend, by campus?",
];

export function AskData() {
  const [q, setQ] = useState("");
  const ask = useMutation({
    mutationFn: (question: string) => api.staff.ask(question),
    onSuccess: r => signal("staff:asked", r),
  });
  const r = ask.data;
  const go = (text: string) => {
    if (!text.trim() || ask.isPending) return;
    setQ(text);
    ask.mutate(text.trim());
  };

  return (
    <>
      <h1 tabIndex={-1} className="mb-6 text-[30px] font-semibold tracking-tight outline-none">
        Ask the data
      </h1>
      <Panel title="Plain-English questions, read-only SQL" sub="Runs as a read-only role over the same suppressed aggregates. The query is always shown.">
        <form
          onSubmit={e => {
            e.preventDefault();
            go(q);
          }}
          className="flex flex-col gap-2 sm:flex-row"
        >
          <label htmlFor="staff-q" className="sr-only">
            Ask the data
          </label>
          <input
            id="staff-q"
            value={q}
            onChange={e => setQ(e.target.value.slice(0, 300))}
            placeholder="e.g. Which campus has the thinnest financial supply?"
            className="h-12 min-w-0 flex-1 rounded-xl border border-line-strong bg-bg px-3.5 text-[16px]"
            data-tour="staff-ask-input"
          />
          <Button type="submit" size="md" loading={ask.isPending} disabled={!q.trim()}>
            Ask
          </Button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map(e => (
            <button
              key={e}
              type="button"
              onClick={() => go(e)}
              className="min-h-10 rounded-full bg-surface-2 px-3.5 py-2 text-left text-[14px] hover:brightness-95 cursor-pointer"
            >
              {e}
            </button>
          ))}
        </div>

        {ask.isError ? (
          <p role="alert" className="mt-4 text-[15px] text-scarlet-ink">
            {(ask.error as Error).message}
          </p>
        ) : null}

        {r ? (
          <div className="mt-6" aria-live="polite">
            <p className="text-[17px] font-medium leading-snug">{r.message}</p>
            {r.sql ? (
              <pre className="mt-4 overflow-x-auto rounded-xl bg-ink p-4 text-[13px] leading-relaxed text-bg">
                <span className="mb-2 flex items-center gap-1.5 font-sans text-[12px] uppercase tracking-wide opacity-70">
                  <Database size={14} aria-hidden /> SQL that ran
                </span>
                <code>{r.sql}</code>
              </pre>
            ) : null}
            {r.columns.length ? (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-left text-[14px]">
                  <thead>
                    <tr className="border-b border-line">
                      {r.columns.map(c => (
                        <th key={c} scope="col" className="py-2 pr-4 font-semibold">
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {r.rows.map((row, i) => (
                      <tr key={i} className="border-b border-line/60">
                        {r.columns.map(c => (
                          <td key={c} className="py-2 pr-4 tabular">
                            {row[c] === null || row[c] === undefined ? "—" : String(row[c])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        ) : null}
      </Panel>
    </>
  );
}
