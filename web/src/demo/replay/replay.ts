// Offline replay: answers API calls from a recorded production run of the stage story, then from the backend's
// per-persona fixtures. Every replayed call is reported to the inspector as source "replay" so the UI says so.
import { inspector, type CallLog } from "../../api/inspector";
import { clock } from "../../session/clock";
import { session } from "../../session/session";

export type Recorded = { method: string; path: string; status: number; body: unknown; persona?: string };
export type ReplayData = { calls: Recorded[]; fixtures: Record<string, unknown> };

let queues = new Map<string, Recorded[]>();
let lastByKey = new Map<string, Recorded>();
let fixtures: Record<string, unknown> = {};

const ID_SEGMENT = /^(?:\d+|[A-Za-z0-9_-]{8,}|m%3A\d+|m:\d+|profile[:%].*)$/;
const STATIC = new Set(["me", "next", "map", "focus", "memory", "inbox", "card", "decline", "commitments", "followups", "invites", "wins", "same-here", "pulse", "ask", "demo", "session", "clock", "skip-ahead", "reset", "personas", "force-templates", "staff", "funnel", "gaps", "weekly", "dips", "retakes", "push", "subscriptions", "vapid-key", "meta", "barriers", "health", "ics", "chat", "history", "new", "items", "remind"]);

export function routeKey(method: string, path: string): string {
  const clean = path.split("?")[0];
  const segs = clean.split("/").map(s => (s && !STATIC.has(s) && ID_SEGMENT.test(s) ? ":id" : s));
  return `${method.toUpperCase()} ${segs.join("/")}`;
}

export function loadReplay(data: ReplayData) {
  queues = new Map();
  lastByKey = new Map();
  for (const c of data.calls) {
    const k = routeKey(c.method, c.path);
    if (!queues.has(k)) queues.set(k, []);
    queues.get(k)!.push(c);
  }
  fixtures = data.fixtures;
}

export const replayLoaded = () => queues.size > 0 || Object.keys(fixtures).length > 0;

const uid = () => globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);

export async function replayRequest<T>(method: string, path: string, _body?: unknown): Promise<{ data: T; call: CallLog }> {
  const k = routeKey(method, path);
  const q = queues.get(k) ?? [];
  // Match the current student and don't go back in simulated time, so replay can take over mid-story.
  const persona = session.get()?.persona;
  const now = clock.get();
  const wanted = (_body as { persona?: string } | undefined)?.persona;
  const fits = (c: Recorded) => {
    // a new session is matched on the persona it asks for (the old session is still current at that moment)
    if (k === "POST /demo/session") return (c.body as { persona?: string } | undefined)?.persona === wanted;
    if (persona && c.persona && c.persona !== persona) return false;
    const t = (c.body as { now?: string } | undefined)?.now;
    return !(now && t && new Date(t).getTime() < new Date(now).getTime());
  };
  const i = q.findIndex(fits);
  let hit: Recorded | undefined;
  if (i >= 0) {
    hit = q.splice(i, 1)[0];
    lastByKey.set(`${k}|${hit.persona ?? ""}`, hit);
  } else hit = lastByKey.get(`${k}|${persona ?? ""}`) ?? lastByKey.get(`${k}|`);
  let body: unknown;
  let status = 200;
  if (hit) {
    body = hit.body;
    status = hit.status;
  } else if (k in fixtures) {
    body = fixtures[k];
  } else {
    throw new Error(`Not available offline: ${k}`);
  }
  await new Promise(r => setTimeout(r, 90));
  const call: CallLog = { id: uid(), method, path, ms: 90, status, fallback: null, trace: {}, source: "replay" };
  inspector.emit({ type: "call", call });
  return { data: structuredClone(body) as T, call };
}
