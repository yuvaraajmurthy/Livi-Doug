// Stage presenter <-> app-in-iframe messaging. Same origin only. The iframe is named "compass-stage".
import type { CallLog } from "../api/inspector";
import type { Action, Signal } from "./types";

export const STAGE_FRAME_NAME = "compass-stage";

export type ToApp = { source: "compass-stage"; kind: "perform"; id: number; actions: Action[] };
export type FromApp =
  | { source: "compass-app"; kind: "ready"; route: string }
  | { source: "compass-app"; kind: "call"; call: CallLog }
  | { source: "compass-app"; kind: "signal"; name: Signal; data?: unknown }
  | { source: "compass-app"; kind: "performed"; id: number; error?: string }
  | { source: "compass-app"; kind: "session"; token: string; persona: string }
  | { source: "compass-app"; kind: "key"; key: string };

export const isStageChild = () => typeof window !== "undefined" && window.name === STAGE_FRAME_NAME && window.parent !== window;

type DistOmit<T, K extends keyof T> = T extends unknown ? Omit<T, K> : never;

export function toParent(msg: DistOmit<FromApp, "source">) {
  try {
    window.parent.postMessage(JSON.parse(JSON.stringify({ ...msg, source: "compass-app" })), window.location.origin);
  } catch {
    // data that can't be cloned is dropped; the stage still works on signals
  }
}

/** Keys the presenter uses; forwarded from the iframe so a click inside the phone doesn't steal the clicker. */
export const STAGE_KEYS = new Set([
  "ArrowRight", "ArrowLeft", "PageDown", "PageUp", " ",
  "n", "N", "a", "A", "o", "O", "p", "P", "f", "F", "r", "R", "1", "2", "3", "4", "5", "6", "7", "8", "9",
]);
