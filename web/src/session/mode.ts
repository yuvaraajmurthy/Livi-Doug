// What the audience is looking at: live API, backend fixture fallback, templates (AI off) or offline replay.
import { useSyncExternalStore } from "react";
import { inspector } from "../api/inspector";
import { onTransportKind, transportKind } from "../api/transport";

export type DataMode = "live" | "fixture" | "replay";
let mode: DataMode = "live";
let templates = false;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach(fn => fn());

inspector.on(e => {
  if (e.type !== "call") return;
  const next: DataMode = e.call.source === "replay" ? "replay" : e.call.fallback === "fixture" ? "fixture" : "live";
  if (next !== mode) {
    mode = next;
    emit();
  }
});
onTransportKind(k => {
  mode = k === "replay" ? "replay" : "live";
  emit();
});

export const dataMode = {
  get: () => mode,
  templates: () => templates,
  setTemplates(on: boolean) {
    templates = on;
    emit();
  },
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
};

export function useDataMode(): { mode: DataMode; templates: boolean } {
  const m = useSyncExternalStore(dataMode.subscribe, () => (transportKind() === "replay" ? "replay" : mode), () => mode);
  const tpl = useSyncExternalStore(dataMode.subscribe, dataMode.templates, dataMode.templates);
  return { mode: m, templates: tpl };
}
