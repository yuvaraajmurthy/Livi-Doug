// A tiny event bus: every API call and every demo signal goes through here. The stage rail and the coach bar listen.
import type { Signal } from "../demo/types";

export type CallLog = {
  id: string;
  method: string;
  path: string;
  ms: number;
  status: number;
  fallback: "fixture" | "template" | null;
  trace: Record<string, string>;
  requestId?: string;
  source: "live" | "replay";
};

export type InspectorEvent =
  | { type: "call"; call: CallLog }
  | { type: "signal"; name: Signal; data?: unknown };

type Listener = (e: InspectorEvent) => void;
const listeners = new Set<Listener>();

export const inspector = {
  on(fn: Listener): () => void {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
  emit(e: InspectorEvent) {
    for (const fn of [...listeners]) {
      try {
        fn(e);
      } catch {
        // a broken listener must never break the app
      }
    }
  },
};

export function signal(name: Signal, data?: unknown) {
  inspector.emit({ type: "signal", name, data });
}
