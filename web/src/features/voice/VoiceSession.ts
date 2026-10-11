// Voice WebSocket client + state machine (spec 2026-10-11 §4).
import type { CrisisResponse } from "../../api/client";
import { inspector, signal } from "../../api/inspector";
import { apiBase } from "../../api/transport";
import { session } from "../../session/session";
import type { UIEvent } from "../chat/types";

export type VoiceState = "connecting" | "listening" | "thinking" | "speaking" | "ended" | "error";

export type ServerFrame =
  | { type: "ready"; conversation_id?: string }
  | { type: "audio"; data: string }
  | { type: "transcript"; role: "user" | "assistant"; text: string; final: boolean }
  | { type: "barge_in" }
  | { type: "ui"; event: UIEvent }
  | ({ type: "crisis" } & CrisisResponse)
  | { type: "error"; message: string }
  | { type: "ping" }
  | { type: "end" };

export type Handlers = {
  state: (s: VoiceState) => void;
  audio: (b64: string) => void;
  bargeIn: () => void;
  caption: (role: "user" | "assistant", text: string, final: boolean) => void;
  ui: (e: UIEvent) => void;
  crisis: (c: CrisisResponse) => void;
  error: (message: string) => void;
};

export function wsUrl(base = apiBase()): string {
  return base.replace(/^http/, "ws").replace(/\/$/, "") + "/voice/ws";
}

/** Pure reducer for the visible state, driven by server frames (kept separate so it's easy to test). */
export function nextState(s: VoiceState, f: ServerFrame): VoiceState {
  switch (f.type) {
    case "ready":
      return "listening";
    case "transcript":
      return f.role === "user" ? (f.final ? "thinking" : "listening") : "speaking";
    case "audio":
      return "speaking";
    case "barge_in":
      return "listening";
    case "error":
      return "error";
    case "end":
      return s === "error" ? s : "ended";
    default:
      return s;
  }
}

export class VoiceSession {
  private ws: WebSocket | null = null;
  private state: VoiceState = "connecting";
  private t0 = 0;

  constructor(private h: Handlers) {}

  private set(s: VoiceState) {
    if (s !== this.state) {
      this.state = s;
      this.h.state(s);
    }
  }

  start(conversationId: string | null = null) {
    this.t0 = performance.now();
    this.set("connecting");
    const ws = new WebSocket(wsUrl());
    this.ws = ws;
    ws.onopen = () => ws.send(JSON.stringify({ type: "start", token: session.token(), conversation_id: conversationId }));
    ws.onmessage = ev => {
      let f: ServerFrame;
      try {
        f = JSON.parse(String(ev.data));
      } catch {
        return;
      }
      if (f.type === "ready") {
        inspector.emit({
          type: "call",
          call: { id: crypto.randomUUID(), method: "WS", path: "/voice/ws", ms: Math.round(performance.now() - this.t0), status: 101, fallback: null, trace: {}, source: "live" },
        });
      }
      this.set(nextState(this.state, f));
      if (f.type === "audio") this.h.audio(f.data);
      else if (f.type === "barge_in") this.h.bargeIn();
      else if (f.type === "transcript") {
        this.h.caption(f.role, f.text, f.final);
        if (f.final && f.role === "assistant") signal("chat:answered");
      } else if (f.type === "ui") {
        this.h.ui(f.event);
        if (f.event.type === "events") signal("chat:events", f.event.items);
      } else if (f.type === "crisis") {
        const { type: _t, ...c } = f;
        this.h.crisis(c as CrisisResponse);
      } else if (f.type === "error") this.h.error(f.message);
    };
    ws.onerror = () => {
      this.set("error");
      this.h.error("Voice couldn't connect. You can type instead.");
    };
    ws.onclose = () => {
      if (this.state !== "error") this.set("ended");
    };
  }

  /** The model is speaking again after the student stopped: audio playback finished. */
  idle() {
    if (this.state === "speaking") this.set("listening");
  }

  sendAudio(b64: string) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: "audio", data: b64 }));
  }

  stop() {
    try {
      if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: "stop" }));
      this.ws?.close();
    } catch {
      // already closed
    }
    this.ws = null;
  }
}
