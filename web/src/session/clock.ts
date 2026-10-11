// The simulated "now" from the API. Every response carries it; when it moves, student data is stale.
import type { QueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

let now: string | null = null;
const listeners = new Set<() => void>();
const changeListeners = new Set<(v: string) => void>();

export const STUDENT_KEYS = ["map", "next", "inbox", "memory", "pulse", "card"] as const;

export const clock = {
  get: () => now,
  observe(value: string | null | undefined) {
    if (!value || value === now) return;
    const first = now === null;
    now = value;
    for (const fn of [...listeners]) fn();
    if (!first) for (const fn of [...changeListeners]) fn(value);
  },
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
  reset() {
    now = null;
    for (const fn of [...listeners]) fn();
  },
};

export function bindClockToQueries(qc: QueryClient): () => void {
  const fn = () => {
    for (const k of STUDENT_KEYS) void qc.invalidateQueries({ queryKey: [k] });
  };
  changeListeners.add(fn);
  return () => {
    changeListeners.delete(fn);
  };
}

export function onClockChange(fn: (v: string) => void): () => void {
  changeListeners.add(fn);
  return () => {
    changeListeners.delete(fn);
  };
}

export function useClock(): string | null {
  return useSyncExternalStore(clock.subscribe, clock.get, clock.get);
}
