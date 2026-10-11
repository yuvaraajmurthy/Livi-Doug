// Table-tour state: which tour, where in it, and whether it's finished. Advances on real signals and real taps.
import { useSyncExternalStore } from "react";
import { inspector } from "../api/inspector";
import { current, init, reduce } from "./engine";
import { perform } from "./perform";
import { TOURS } from "./tours";
import type { EngineEvent, EngineState, Persona } from "./types";

type TourState = { name: Persona; engine: EngineState; done: boolean; busy: boolean; error: string | null } | null;
let state: TourState = null;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach(fn => fn());
const set = (s: TourState) => {
  state = s;
  emit();
};

function matches(e: EngineEvent, s: EngineState): boolean {
  const st = current(s);
  if (e.type === "signal") return st.waitFor === e.name;
  if (e.type === "tap") return !st.waitFor && st.target === e.target;
  return false;
}

export function dispatch(e: EngineEvent) {
  if (!state || state.done) return;
  const isLast = state.engine.index === state.engine.steps.length - 1;
  if (isLast && matches(e, state.engine)) return set({ ...state, done: true });
  const next = reduce(state.engine, e);
  if (next !== state.engine) set({ ...state, engine: next, error: null });
}

inspector.on(e => {
  if (e.type === "signal") dispatch({ type: "signal", name: e.name });
});

if (typeof document !== "undefined") {
  document.addEventListener(
    "click",
    ev => {
      if (!state) return;
      const el = (ev.target as HTMLElement | null)?.closest?.("[data-tour]");
      const id = el?.getAttribute("data-tour");
      // let the click do its work first, then advance
      if (id) setTimeout(() => dispatch({ type: "tap", target: id }), 0);
    },
    true,
  );
}

/** Resolves once the tour has moved off step `id` (or ended), or after `ms` so a lost signal can't wedge the button. */
function leaves(id: string, ms = 30_000): Promise<void> {
  return new Promise(resolve => {
    const check = () => {
      if (!state || state.done || current(state.engine).id !== id) finish();
    };
    const finish = () => {
      clearTimeout(timer);
      listeners.delete(check);
      resolve();
    };
    const timer = setTimeout(finish, ms);
    listeners.add(check);
    check();
  });
}

export async function runCurrent() {
  if (!state || state.busy) return;
  const st = current(state.engine);
  set({ ...state, busy: true, error: null });
  try {
    if (st.perform?.length) await perform(st.perform);
    // A step that waits on a signal (an answer streaming in) stays busy until it arrives: tapping again would redo it.
    if (st.waitFor) await leaves(st.id);
    // A performed tap advances through the click listener; anything else (typing, info steps) advances here.
    // Wait a beat so a click-driven advance lands first, then only advance if we're still on the same step.
    await new Promise(r => setTimeout(r, 60));
    if (state && !st.waitFor && current(state.engine).id === st.id && !state.done) {
      const isLast = state.engine.index === state.engine.steps.length - 1;
      set(isLast ? { ...state, done: true } : { ...state, engine: reduce(state.engine, { type: "next" }) });
    }
  } catch (e) {
    if (state) set({ ...state, error: (e as Error).message });
  } finally {
    if (state) set({ ...state, busy: false });
  }
}

export async function startTour(name: Persona) {
  set({ name, engine: init(TOURS[name]), done: false, busy: false, error: null });
  await runCurrent(); // first step starts the session
}

export const tour = {
  get: () => state,
  back: () => state && set({ ...state, engine: reduce(state.engine, { type: "back" }), done: false }),
  next: () => dispatch({ type: "next" }),
  exit: () => set(null),
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
};

export function useTour() {
  return useSyncExternalStore(tour.subscribe, tour.get, tour.get);
}
