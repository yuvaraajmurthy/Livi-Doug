// Typed wrappers over the Compass API. Types come from contract/openapi.json (npm run gen:api).
import type { components } from "./schema";
import { transport } from "./transport";
import { clock } from "../session/clock";
import type { Persona } from "../demo/types";

export type S = components["schemas"];
export type MapResponse = S["MapResponse"];
export type NextResponse = S["NextResponse"];
export type Suggestion = S["Suggestion"];
export type ProfileResult = S["ProfileResult"];
export type CrisisResponse = S["CrisisResponse"];
export type FocusResponse = ProfileResult | CrisisResponse;
export type CommitResponse = S["CommitResponse"];
export type FollowupResponse = S["FollowupResponse"];
export type InboxResponse = S["InboxResponse"];
export type MemoryList = S["MemoryList"];
export type MemoryItem = S["MemoryItem"];
export type PulseResponse = S["PulseResponse"];
export type AskResult = S["AskResponse"] | CrisisResponse;
export type CardResponse = S["CardResponse"];
export type SessionResponse = S["SessionResponse"];
export type SkipAheadResponse = S["SkipAheadResponse"];
export type FiredNotification = S["FiredNotification"];
export type InviteView = S["InviteView"];
export type CrisisLine = S["CrisisLine"];
export type SupportCard = S["SupportCard"];
export type Dimension = S["DimensionScore"]["dimension"];
export type BarrierMeta = S["BarrierMeta"];
export type WinResult = S["WinAccepted"] | CrisisResponse;
export type StaffFilters = {
  campus?: string | null;
  dimension?: string | null;
  level?: string | null;
  first_gen?: boolean | null;
  housing?: string | null;
};

export const DIMENSIONS = [
  "emotional",
  "environmental",
  "financial",
  "intellectual",
  "occupational",
  "physical",
  "social",
  "spiritual",
] as const;

export const isCrisis = (x: unknown): x is CrisisResponse =>
  typeof x === "object" && x !== null && (x as { kind?: string }).kind === "crisis";

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const { data } = await transport.request<T>(method, path, body);
  clock.observe((data as { now?: string } | undefined)?.now);
  return data;
}

function qs(f: StaffFilters & { threshold?: number }): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const api = {
  health: () => call<S["Health"]>("GET", "/health"),
  personas: () => call<S["PersonasResponse"]>("GET", "/demo/personas"),
  session: (persona: Persona, sandbox = false) =>
    call<SessionResponse>("POST", "/demo/session", { persona, sandbox }),
  setClock: (now: string) => call<SessionResponse>("POST", "/demo/clock", { now }),
  skipAhead: (to: string) => call<SkipAheadResponse>("POST", "/demo/skip-ahead", { to }),
  reset: () => call<S["ResetResponse"]>("POST", "/demo/reset"),
  forceTemplates: (on: boolean) => call<S["ResetResponse"]>("POST", "/demo/force-templates", { on }),
  barriers: () => call<BarrierMeta>("GET", "/meta/barriers"),

  map: () => call<MapResponse>("GET", "/me/map"),
  focus: (body: S["FocusRequest"]) => call<FocusResponse>("POST", "/me/focus", body),
  next: () => call<NextResponse>("GET", "/me/next"),
  decline: (recId: number, reason: S["DeclineRequest"]["reason"]) =>
    call<NextResponse>("POST", `/me/next/${recId}/decline`, { reason }),
  card: () => call<CardResponse>("GET", "/me/card"),
  memory: () => call<MemoryList>("GET", "/me/memory"),
  deleteMemory: (id: string) => call<S["DeleteResult"]>("DELETE", `/me/memory/${encodeURIComponent(id)}`),
  deleteAllMemory: () => call<S["DeleteResult"]>("DELETE", "/me/memory"),
  forgetMe: () => call<S["DeleteResult"]>("DELETE", "/me"),
  inbox: () => call<InboxResponse>("GET", "/me/inbox"),
  ask: (question: string) => call<AskResult>("POST", "/ask", { question }),

  commit: (recId: number) => call<CommitResponse>("POST", "/commitments", { rec_id: recId }),
  invite: (token: string) => call<InviteView>("GET", `/invites/${encodeURIComponent(token)}`),
  acceptInvite: (token: string) => call<S["InviteAccepted"]>("POST", `/invites/${encodeURIComponent(token)}`),
  followup: (id: number, body: S["FollowupRequest"]) => call<FollowupResponse>("POST", `/followups/${id}`, body),

  pulse: () => call<PulseResponse>("GET", "/pulse"),
  postWin: (text: string, dimension?: Dimension | null) => call<WinResult>("POST", "/wins", { text, dimension }),
  sameHere: (id: string) => call<S["SameHere"]>("POST", `/wins/${encodeURIComponent(id)}/same-here`),

  vapidKey: () => call<S["VapidKey"]>("GET", "/push/vapid-key"),
  subscribePush: (sub: S["SubscriptionRequest"]) => call<S["SubscriptionResult"]>("POST", "/push/subscriptions", sub),
  unsubscribePush: (sub: S["SubscriptionRequest"]) =>
    call<S["SubscriptionResult"]>("DELETE", "/push/subscriptions", sub),

  item: (id: string) => call<import("../features/chat/types").ItemDetail>("GET", `/items/${encodeURIComponent(id)}`),
  remind: (id: string) => call<CommitResponse>("POST", `/items/${encodeURIComponent(id)}/remind`),
  chatHistory: () =>
    call<{ conversation_id: string | null; messages: { id: number; role: "user" | "assistant"; text: string; blocks: import("../features/chat/types").UIEvent[]; source: string | null; at: string }[] }>(
      "GET",
      "/chat/history",
    ),
  chatNew: () => call<{ conversation_id: string }>("POST", "/chat/new"),

  staff: {
    funnel: (f: StaffFilters = {}) => call<S["FunnelResponse"]>("GET", `/staff/funnel${qs(f)}`),
    gaps: (f: StaffFilters = {}) => call<S["GapsResponse"]>("GET", `/staff/gaps${qs(f)}`),
    weekly: (f: StaffFilters = {}) => call<S["WeeklyResponse"]>("GET", `/staff/weekly${qs(f)}`),
    dips: (f: StaffFilters = {}) => call<S["DipsResponse"]>("GET", `/staff/dips${qs(f)}`),
    retakes: (f: StaffFilters = {}) => call<S["RetakesResponse"]>("GET", `/staff/retakes${qs(f)}`),
    ask: (question: string) => call<S["StaffAskResponse"]>("POST", "/staff/ask", { question }),
  },
};

export const icsUrl = (base: string, path: string) => (path.startsWith("http") ? path : base + path);
