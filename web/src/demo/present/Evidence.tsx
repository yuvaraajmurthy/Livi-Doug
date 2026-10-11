// One piece of evidence per step (bars show the fixed ranking weights: that is the claim) (spec §6): a number, up to three chips, a quote, or five small bars. Never a paragraph.
import { motion } from "motion/react";
import type { CommitResponse, FollowupResponse, MapResponse, S, Suggestion } from "../../api/client";
import type { CallLog } from "../../api/inspector";
import type { ProofKind } from "../types";
import type { Evidence as Ev } from "./useStage";

const last = (calls: CallLog[], path: RegExp) => calls.find(c => path.test(c.path));

function NumberEv({ value, caption }: { value: string; caption: string }) {
  return (
    <div>
      <p className="text-[clamp(44px,8vh,80px)] font-semibold leading-none tracking-tight tabular">{value}</p>
      <p className="mt-2 text-[clamp(15px,2.2vh,19px)] text-ink-2">{caption}</p>
    </div>
  );
}

function Chips({ items, accent }: { items: string[]; accent?: number }) {
  return (
    <ul className="flex flex-wrap gap-2">
      {items.slice(0, 3).map((t, i) => (
        <motion.li
          key={t}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.08 }}
          className={`rounded-full px-4 py-2 text-[clamp(14px,2.1vh,18px)] font-medium ${
            i === accent ? "bg-scarlet text-on-scarlet" : "bg-surface border border-line"
          }`}
        >
          {t}
        </motion.li>
      ))}
    </ul>
  );
}

const LABEL: Record<string, string> = {
  dimension: "Focus",
  barrier: "Barriers",
  window: "Schedule",
  rung: "Step size",
  helped_similar: "Peers",
};

function Bars({ s }: { s: Suggestion }) {
  return (
    <ul className="grid max-w-[460px] grid-cols-5 items-end gap-3">
      {s.reasons.components.map((c, i) => (
        <li key={c.name} className="flex flex-col items-center gap-2">
          <div className="flex h-[clamp(70px,13vh,120px)] w-full items-end rounded-lg bg-surface-2">
            <motion.div
              className="w-full rounded-lg bg-ink"
              initial={{ height: 0 }}
              animate={{ height: `${(c.weight / 0.35) * 100}%` }}
              transition={{ delay: 0.1 + i * 0.08, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            />
          </div>
          <span className="text-[13px] font-medium text-ink-2">{LABEL[c.name] ?? c.name}</span>
          <span className="text-[12px] text-ink-2 tabular">{Math.round(c.weight * 100)}%</span>
        </li>
      ))}
    </ul>
  );
}

export function Evidence({ kind, ev }: { kind?: ProofKind; ev: Ev }) {
  switch (kind) {
    case "strengths":
      return <Chips items={["From the inventory", "No new survey", "His choice"]} />;
    case "latency": {
      const c = last(ev.calls, /^\/me\/next/);
      return c ? <NumberEv value={`${c.ms} ms`} caption={c.trace.candidates ? `${c.trace.candidates} Newark options ranked, live` : "ranked live"} /> : null;
    }
    case "fit": {
      const s = ev["next:shown"] as Suggestion | undefined;
      if (!s) return null;
      if (s.reasons.memory.length) return <Chips items={["Remembered:", s.reasons.memory[0].statement]} accent={1} />;
      return <Bars s={s} />;
    }
    case "plan": {
      const c = ev["commitment:created"] as CommitResponse | undefined;
      return c ? <p className="display max-w-[22ch] text-[clamp(24px,4vh,38px)] leading-tight text-ink-2">“{c.plan_text}”</p> : null;
    }
    case "push":
      return <Chips items={["Push + in-app", "3 a week, max", "Quiet hours"]} />;
    case "memory": {
      const f = ev["followup:submitted"] as FollowupResponse | undefined;
      return f ? <Chips items={f.learned.map(m => m.statement)} /> : <Chips items={["Sourced", "Visible", "Deletable"]} />;
    }
    case "score": {
      const m = ev["map:shown"] as MapResponse | undefined;
      const s = m?.dimensions.find(d => d.dimension === "social");
      return s?.change ? (
        <NumberEv value={`${(s.score - s.change).toFixed(1)} → ${s.score.toFixed(1)}`} caption="Social · Sep 14 vs Oct 26 retake" />
      ) : null;
    }
    case "chat": {
      const c = last(ev.calls, /^\/chat/);
      return <Chips items={["Every real event, in context", "Buttons, not lists", c ? `${(c.ms / 1000).toFixed(1)} s` : "Strands + Haiku"]} />;
    }
    case "card":
      return <Chips items={["Live listing", "Map", "Directions"]} />;
    case "reminder":
      return <Chips items={["Plan", "Reminder", "Follow-up"]} accent={1} />;
    case "care":
      return <Chips items={["CAPS", "Teletherapy", "Peers"]} />;
    case "safety": {
      const c = last(ev.calls, /^\/(chat|ask)/);
      return <Chips items={[`Code check${c?.trace.safety_ms ? ` · ${c.trace.safety_ms} ms` : ""}`, "AI: not called", "Nothing stored"]} accent={1} />;
    }
    case "gaps": {
      const g = ev["staff:gaps"] as S["GapsResponse"] | undefined;
      const r = g?.rows.filter(x => x.campus === "camden").sort((a, b) => b.low_students_per_item - a.low_students_per_item)[0];
      return r ? <NumberEv value={r.low_students_per_item.toFixed(1)} caption={`Camden ${r.dimension}: students per resource`} /> : null;
    }
    case "suppression":
      return <Chips items={["Groups under 10", "Refused by the database"]} accent={1} />;
    default:
      return null;
  }
}
