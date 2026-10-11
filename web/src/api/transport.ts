// All HTTP goes through here: base URL, bearer token, 8 s timeout, one retry for GETs, and an inspector event per
// call (timing, fallback header, trace header) so the stage demo can show real evidence.
import { inspector, type CallLog } from "./inspector";
import { replayRequest } from "../demo/replay/replay";

type Opts = { base: string; token: () => string | null };
export const DEFAULT_API =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "https://d2fap8zqnl1gn5.cloudfront.net";

let kind: "live" | "replay" = "live";
let opts: Opts = { base: DEFAULT_API, token: () => null };
let consecutiveFailures = 0;
let recorder: { method: string; path: string; status: number; body: unknown; persona?: string }[] | null = null;
const failureListeners = new Set<(n: number) => void>();

/** Record every live response (used once, to capture the stage story for offline replay). */
export function startRecording() {
  recorder = [];
  (globalThis as { __compassRecording?: unknown }).__compassRecording = recorder;
}
/** Called with the running count each time a request fails for network/server reasons. */
export function onFailure(fn: (n: number) => void) {
  failureListeners.add(fn);
  return () => {
    failureListeners.delete(fn);
  };
}
const failed = () => {
  consecutiveFailures++;
  for (const fn of failureListeners) fn(consecutiveFailures);
};
const kindListeners = new Set<(k: "live" | "replay") => void>();

export function setTransport(k: "live" | "replay", o?: Partial<Opts>) {
  kind = k;
  opts = { ...opts, ...o };
  consecutiveFailures = 0;
  for (const fn of kindListeners) fn(k);
}
export const transportKind = () => kind;
export const apiBase = () => opts.base;
export function onTransportKind(fn: (k: "live" | "replay") => void) {
  kindListeners.add(fn);
  return () => {
    kindListeners.delete(fn);
  };
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
  }
}

export function parseTrace(h: string | null): Record<string, string> {
  if (!h) return {};
  const out: Record<string, string> = {};
  for (const part of h.split(";")) {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i)] = part.slice(i + 1);
  }
  return out;
}

function messageFor(status: number, body: unknown): string {
  const b = body as { message?: string; detail?: { message?: string } | string } | undefined;
  if (b && typeof b.message === "string") return b.message;
  if (typeof b?.detail === "string") return b.detail;
  if (b?.detail && typeof b.detail === "object" && b.detail.message) return b.detail.message;
  return status >= 500 || status === 0
    ? "Compass is having trouble right now. Try again."
    : "That didn't go through. Try again.";
}

const uid = () => globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);

async function once<T>(method: string, path: string, body?: unknown): Promise<{ data: T; call: CallLog }> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 8000);
  const t0 = performance.now();
  try {
    const token = opts.token();
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (token) headers.Authorization = `Bearer ${token}`;
    const r = await fetch(opts.base + path, {
      method,
      signal: ctl.signal,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const text = await r.text();
    let data: unknown = undefined;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = undefined;
      }
    }
    const call: CallLog = {
      id: uid(),
      method,
      path,
      ms: Math.round(performance.now() - t0),
      status: r.status,
      fallback: (r.headers.get("X-Compass-Fallback") as CallLog["fallback"]) ?? null,
      trace: parseTrace(r.headers.get("X-Compass-Trace")),
      requestId: r.headers.get("X-Request-Id") ?? undefined,
      source: "live",
    };
    inspector.emit({ type: "call", call });
    recorder?.push({ method, path, status: r.status, body: data, persona: token?.split(".")[1] });
    if (!r.ok) throw new ApiError(messageFor(r.status, data), r.status, data);
    return { data: data as T, call };
  } catch (e) {
    if ((e as Error).name === "AbortError") throw new ApiError("Request timed out", 0);
    if (e instanceof ApiError) throw e;
    throw new ApiError(messageFor(0, undefined), 0);
  } finally {
    clearTimeout(timer);
  }
}

const transient = (e: unknown) => {
  const s = e instanceof ApiError ? e.status : 0;
  return s === 0 || s >= 500;
};

export const transport = {
  async request<T>(method: string, path: string, body?: unknown): Promise<{ data: T; call: CallLog }> {
    if (kind === "replay") return replayRequest<T>(method, path, body);
    try {
      const res = await once<T>(method, path, body);
      consecutiveFailures = 0;
      return res;
    } catch (e) {
      if (!transient(e)) throw e;
      failed();
      if (method !== "GET") throw e;
      try {
        const res = await once<T>(method, path, body);
        consecutiveFailures = 0;
        return res;
      } catch (e2) {
        if (transient(e2)) failed();
        throw e2;
      }
    }
  },
  failures: () => consecutiveFailures,
};
