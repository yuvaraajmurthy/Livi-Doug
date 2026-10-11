// Pure story reducer: the same steps drive the stage presenter and the table tours. No React, no I/O.
import type { EngineEvent, EngineState, StoryStep } from "./types";

export function init(steps: StoryStep[]): EngineState {
  return { steps, index: 0, history: [] };
}

export const current = (s: EngineState): StoryStep => s.steps[s.index];
export const atEnd = (s: EngineState) => s.index >= s.steps.length - 1;

function go(s: EngineState, index: number): EngineState {
  const i = Math.max(0, Math.min(s.steps.length - 1, index));
  if (i === s.index) return s;
  return { ...s, index: i, history: [...s.history, s.index] };
}

export function reduce(s: EngineState, e: EngineEvent): EngineState {
  const step = current(s);
  switch (e.type) {
    case "next":
      return go(s, s.index + 1);
    case "jump":
      return go(s, e.index);
    case "back": {
      if (!s.history.length) return s;
      const history = s.history.slice(0, -1);
      return { ...s, index: s.history[s.history.length - 1], history };
    }
    case "restart":
      return init(s.steps);
    case "signal":
      return step.waitFor === e.name ? go(s, s.index + 1) : s;
    case "tap":
      return !step.waitFor && step.target === e.target ? go(s, s.index + 1) : s;
  }
}
