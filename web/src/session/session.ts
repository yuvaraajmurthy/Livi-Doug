// Demo session: token per browser tab (sessionStorage), so the stage iframe, a judge's phone and a second tab never
// share state by accident. `?t=` / `#t=` attaches a device to an existing session (phone pairing).
import { useSyncExternalStore } from "react";
import type { Persona } from "../demo/types";

export type Session = {
  token: string;
  persona: Persona;
  role: "student" | "staff";
  sandbox: boolean;
  stage: boolean;
  studentId: string | null;
};

const KEY = "compass.session";
let current: Session | null = read();
const listeners = new Set<() => void>();

function read(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

function write(s: Session | null) {
  current = s;
  try {
    if (s) sessionStorage.setItem(KEY, JSON.stringify(s));
    else sessionStorage.removeItem(KEY);
  } catch {
    // private mode: keep it in memory only
  }
  for (const fn of [...listeners]) fn();
}

export const session = {
  get: () => current,
  token: () => current?.token ?? null,
  set: write,
  clear: () => write(null),
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
};

/** Parse a token (v1.<persona>.<sid>.<sig>) into a session without a network call; used when joining by QR. */
export function sessionFromToken(token: string, stage = false): Session | null {
  const parts = token.split(".");
  if (parts.length !== 4 || parts[0] !== "v1") return null;
  const persona = parts[1] as Persona;
  const sandbox = parts[2].startsWith("sb");
  return {
    token,
    persona,
    role: persona === "staff" ? "staff" : "student",
    sandbox,
    stage,
    studentId: null,
  };
}

export function useSession(): Session | null {
  return useSyncExternalStore(session.subscribe, session.get, session.get);
}
