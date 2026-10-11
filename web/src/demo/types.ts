export type Persona = "andre" | "priya" | "taylor" | "sofia" | "jordan" | "staff";

export type Signal =
  | "session:started"
  | "focus:submitted"
  | "next:shown"
  | "why:opened"
  | "commitment:created"
  | "invite:shared"
  | "push:enabled"
  | "notification:shown"
  | "followup:submitted"
  | "memory:deleted"
  | "map:shown"
  | "crisis:shown"
  | "staff:gaps"
  | "staff:suppressed"
  | "staff:asked"
  | "ask:answered"
  | "clock:changed"
  | "route:changed"
  | "decline:done"
  | "win:posted"
  | "chat:answered"
  | "chat:events"
  | "event:opened"
  | "reminder:set";

export type Action =
  | { kind: "tap"; target: string }
  | { kind: "type"; target: string; text: string; submit?: string }
  | { kind: "navigate"; to: string }
  | { kind: "skip"; to: "next_due" | string }
  | { kind: "clock"; now: string }
  | { kind: "session"; persona: Persona; sandbox: boolean }
  | { kind: "templates"; on: boolean }
  | { kind: "key"; key: string }
  | { kind: "wait"; ms: number }
  | { kind: "replay"; on: boolean };

export type ProofKind =
  | "fit"
  | "latency"
  | "safety"
  | "plan"
  | "push"
  | "memory"
  | "score"
  | "funnel"
  | "gaps"
  | "sql"
  | "suppression"
  | "strengths"
  | "care"
  | "none";

export type Tag = "Impact" | "Engagement" | "Safety" | "Equity" | "Feasibility" | "Privacy";

export type EngineState = { steps: StoryStep[]; index: number; history: number[] };
export type EngineEvent =
  | { type: "next" }
  | { type: "back" }
  | { type: "jump"; index: number }
  | { type: "signal"; name: Signal }
  | { type: "tap"; target: string }
  | { type: "restart" };

export type StoryStep = {
  id: string;
  chapter: string;
  persona: Persona | null;
  route?: string;
  target?: string;
  perform?: Action[];
  waitFor?: Signal;
  claim: string;
  coach?: string;
  proof?: ProofKind;
  note?: string;
  tag?: Tag;
  slide?: "cold-open" | "close";
};
