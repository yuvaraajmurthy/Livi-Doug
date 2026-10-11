import { ArrowRight, Brain, Database, HandHeart, LockSimple, ShieldCheck, Sparkle, Timer } from "@phosphor-icons/react";
import { motion } from "motion/react";
import type { ReactNode } from "react";
import type { CommitResponse, FollowupResponse, MapResponse, S, Suggestion } from "../../api/client";
import type { CallLog } from "../../api/inspector";
import type { ProofKind } from "../types";
import type { Evidence } from "./useStage";

const lastCall = (calls: CallLog[], path: RegExp) => calls.find(c => path.test(c.path));

function Card({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <motion.div
      key={title}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="rounded-[20px] border border-line bg-surface p-4 xl:p-5"
    >
      <p className="mb-3 flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.1em] text-ink-2">
        {icon}
        {title}
      </p>
      {children}
    </motion.div>
  );
}

const LABEL: Record<string, string> = {
  dimension: "Matches his focus",
  barrier: "Gets around what's in the way",
  window: "Fits his schedule",
  rung: "Right size of step",
  helped_similar: "Helped students like him",
};

export function Proof({ kind, ev }: { kind?: ProofKind; ev: Evidence }) {
  if (!kind || kind === "none") return null;
  switch (kind) {
    case "strengths":
      return (
        <Card icon={<Sparkle size={14} aria-hidden />} title="What it reads">
          <p className="text-[17px] leading-snug">
            The 18-item Wellness Inventory he already took on Sep 14. No new questionnaire, no chatbot intake.
          </p>
          <p className="mt-2 text-[15px] text-ink-2">Scores are imported, never computed or changed by AI.</p>
        </Card>
      );
    case "latency": {
      const c = lastCall(ev.calls, /^\/me\/next/);
      return (
        <Card icon={<Timer size={14} aria-hidden />} title="Live, just now">
          {c ? (
            <>
              <p className="text-[40px] font-semibold leading-none tracking-tight tabular">
                {c.ms}
                <span className="text-[20px] text-ink-2"> ms</span>
              </p>
              <p className="mt-2 text-[16px] text-ink-2">
                {c.trace.candidates ? `${c.trace.candidates} Newark events and services ranked, ` : ""}
                {c.trace.passed ? `${c.trace.passed} passed the hard filters.` : "ranked by fit, then distance."}
              </p>
              <Pipeline steps={["Hard filters", "Fit score", "Diverse top 3", c.trace.wording === "ai" ? "AI sentence (cached)" : "Template sentence"]} />
            </>
          ) : (
            <p className="text-[16px] text-ink-2">Ranking…</p>
          )}
        </Card>
      );
    }
    case "fit": {
      const s = ev["next:shown"] as Suggestion | undefined;
      if (!s) return null;
      return (
        <Card icon={<Database size={14} aria-hidden />} title={`Why: ${s.item.title.replace(/ \(sample\)$/, "")}`}>
          <ul className="flex flex-col gap-1.5">
            {s.reasons.components.map(c => (
              <li key={c.name}>
                <div className="flex justify-between text-[14px]">
                  <span className="font-medium">{LABEL[c.name] ?? c.name}</span>
                  <span className="text-ink-2 tabular">{Math.round(c.weight * 100)}%</span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2">
                  <motion.div
                    className="h-full rounded-full bg-ink"
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.max(2, c.score * 100)}%` }}
                    transition={{ duration: 0.6 }}
                  />
                </div>
              </li>
            ))}
          </ul>
          {s.reasons.memory.length ? (
            <p className="mt-3 flex items-start gap-2 rounded-xl bg-scarlet-tint px-3 py-2 text-[15px] text-scarlet-ink">
              <Brain size={18} className="mt-0.5 shrink-0" aria-hidden />
              Remembered: {s.reasons.memory.map(m => m.statement).join("; ")}
            </p>
          ) : null}
          <p className="mt-3 text-[14px] text-ink-2">
            Weights live in a YAML file a staffer can read. {s.why_source === "ai" ? "The sentence is AI wording, checked against these facts." : "The sentence is a template."}
          </p>
        </Card>
      );
    }
    case "plan": {
      const c = ev["commitment:created"] as CommitResponse | undefined;
      return (
        <Card icon={<ArrowRight size={14} aria-hidden />} title="If-then plan">
          {c ? <p className="display text-[24px] leading-tight">“{c.plan_text}”</p> : <p className="text-ink-2">Planning…</p>}
          <p className="mt-3 text-[14px] text-ink-2">
            Implementation intentions: meta-analysis of 94 studies, medium-to-large effect on follow-through (Gollwitzer &
            Sheeran, 2006).
          </p>
        </Card>
      );
    }
    case "push": {
      const n = ev["notification:shown"] as S["InboxItem"] | undefined;
      return (
        <Card icon={<Timer size={14} aria-hidden />} title="Reminder">
          {n ? (
            <>
              <p className="text-[18px] font-semibold leading-snug">{n.title}</p>
              <p className="text-[15px] text-ink-2">{n.body}</p>
              <p className="mt-3 text-[14px] text-ink-2">
                Delivered: {n.delivered === "push" ? "web push to subscribed devices + in-app" : "in-app"} · budget 3 per week · quiet
                hours 10 pm to 8 am · lock-screen-safe wording
              </p>
            </>
          ) : (
            <p className="text-ink-2">Skipping ahead…</p>
          )}
        </Card>
      );
    }
    case "memory": {
      const f = ev["followup:submitted"] as FollowupResponse | undefined;
      if (!f) return null;
      return (
        <Card icon={<Brain size={14} aria-hidden />} title="What Compass learned">
          <ul className="flex flex-col gap-2">
            {f.learned.map(m => (
              <li key={m.id}>
                <p className="text-[16px] font-medium leading-snug">{m.statement}</p>
                <p className="text-[13px] text-ink-2">
                  {m.source.label} · used for: {m.used_for.toLowerCase()}
                </p>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[14px] text-ink-2">Rules write memory, not a model. At most 25 facts, each one deletable.</p>
        </Card>
      );
    }
    case "score": {
      const m = ev["map:shown"] as MapResponse | undefined;
      const social = m?.dimensions.find(d => d.dimension === "social");
      return (
        <Card icon={<Sparkle size={14} aria-hidden />} title="From the inventory retake">
          {social?.change ? (
            <p className="text-[44px] font-semibold leading-none tracking-tight tabular">
              {(social.score - social.change).toFixed(1)} <span className="text-ink-2">→</span> <span className="text-green">{social.score.toFixed(1)}</span>
            </p>
          ) : (
            <p className="text-ink-2">Loading the October take…</p>
          )}
          <p className="mt-3 text-[14px] text-ink-2">
            Social, Sep 14 vs Oct 26. Compass shows it; it never writes it. Synthetic data, not an outcome claim.
          </p>
        </Card>
      );
    }
    case "care":
      return (
        <Card icon={<HandHeart size={14} aria-hidden />} title="Care-first rule">
          <p className="text-[17px] leading-snug">Emotional at or below 1.6, or low plus three other lows: a person comes first.</p>
          <p className="mt-2 text-[14px] text-ink-2">CAPS, Uwill and Togetherall, by campus. Events are held back, not pushed.</p>
        </Card>
      );
    case "safety": {
      const c = lastCall(ev.calls, /^\/ask/);
      return (
        <Card icon={<ShieldCheck size={14} aria-hidden />} title="Safety check, this request">
          <Pipeline
            steps={[
              "Her words",
              c?.trace.safety === "lexicon" ? `Code check: crisis (${c.trace.safety_ms ?? "<1"} ms)` : "Code check",
              "Fixed crisis card",
            ]}
            highlight={1}
          />
          <p className="mt-3 text-[16px] font-medium">AI models called: none. Words stored: none.</p>
          <p className="mt-1 text-[14px] text-ink-2">61 of 61 crisis test phrases caught by code alone; 0 false alarms in 27 look-alikes.</p>
        </Card>
      );
    }
    case "gaps": {
      const g = ev["staff:gaps"] as S["GapsResponse"] | undefined;
      const cam = g?.rows.filter(r => r.campus === "camden").sort((a, b) => b.low_students_per_item - a.low_students_per_item)[0];
      return (
        <Card icon={<Database size={14} aria-hidden />} title="A decision, not a dashboard">
          {cam ? (
            <p className="text-[20px] font-semibold leading-snug">
              Camden {cam.dimension}: {cam.low_students} students with a low score, {cam.items} resources.
            </p>
          ) : null}
          <p className="mt-2 text-[14px] text-ink-2">Same pipeline as the student app. Groups only.</p>
        </Card>
      );
    }
    case "suppression":
      return (
        <Card icon={<LockSimple size={14} aria-hidden />} title="Enforced in the database">
          <pre className="overflow-x-auto rounded-xl bg-ink p-3 text-[12px] leading-relaxed text-bg">
            {`CASE WHEN n >= staff_min_group()  -- 10\n     THEN value END\n-- role compass_staff_ro: SECURITY DEFINER functions only`}
          </pre>
          <p className="mt-2 text-[14px] text-ink-2">The staff role can't read rows, only these functions. Smaller groups come back as nothing.</p>
        </Card>
      );
    default:
      return null;
  }
}

function Pipeline({ steps, highlight }: { steps: string[]; highlight?: number }) {
  return (
    <ol className="mt-4 flex flex-wrap items-center gap-1.5 text-[13px]">
      {steps.map((s, i) => (
        <li key={s} className="flex items-center gap-1.5">
          <span className={`rounded-full px-2.5 py-1 font-medium ${i === highlight ? "bg-scarlet text-on-scarlet" : "bg-surface-2"}`}>{s}</span>
          {i < steps.length - 1 ? <ArrowRight size={12} className="text-ink-2" aria-hidden /> : null}
        </li>
      ))}
    </ol>
  );
}
