// POST-based server-sent events for /chat (EventSource can't POST or send headers).
import { inspector } from "../../api/inspector";
import { apiBase } from "../../api/transport";
import { session } from "../../session/session";
import { clock } from "../../session/clock";
import type { ChatSSE } from "./types";

/** Incremental SSE frame parser: push text chunks, get complete frames back. */
export function parseSSE() {
  let buf = "";
  return {
    push(chunk: string): ChatSSE[] {
      buf += chunk.replace(/\r\n/g, "\n");
      const out: ChatSSE[] = [];
      let i: number;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, i);
        buf = buf.slice(i + 2);
        let event = "message";
        const data: string[] = [];
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
        }
        if (!data.length) continue;
        try {
          out.push({ event, data: JSON.parse(data.join("\n")) } as ChatSSE);
        } catch {
          // ignore a malformed frame rather than break the stream
        }
      }
      return out;
    },
  };
}

export async function streamChat(
  body: { message: string; conversation_id: string | null },
  onEvent: (e: ChatSSE) => void,
  signal?: AbortSignal,
): Promise<void> {
  const t0 = performance.now();
  const token = session.token();
  const r = await fetch(`${apiBase()}/chat`, {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json", Accept: "text/event-stream", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  });
  if (!r.ok || !r.body) {
    inspector.emit({ type: "call", call: { id: crypto.randomUUID(), method: "POST", path: "/chat", ms: Math.round(performance.now() - t0), status: r.status, fallback: null, trace: {}, source: "live" } });
    throw new Error(r.status === 401 ? "Your demo session expired. Pick a student again." : "Compass couldn't answer just now. Try again.");
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  const parser = parseSSE();
  let source: string | null = null;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    for (const ev of parser.push(dec.decode(value, { stream: true }))) {
      if (ev.event === "meta") clock.observe(ev.data.now);
      if (ev.event === "done") source = ev.data.source;
      onEvent(ev);
    }
  }
  inspector.emit({
    type: "call",
    call: {
      id: crypto.randomUUID(),
      method: "POST",
      path: "/chat",
      ms: Math.round(performance.now() - t0),
      status: r.status,
      fallback: source === "fallback" ? "template" : null,
      trace: source ? { wording: source } : {},
      source: "live",
    },
  });
}
