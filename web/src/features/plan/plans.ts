// The API has no "list my plans" route, so the app keeps the commitments it made in this session (per token).
import { useSyncExternalStore } from "react";
import type { CommitResponse, FollowupResponse } from "../../api/client";
import { session } from "../../session/session";

export type PlanRecord = {
  commitment: CommitResponse;
  status: "planned" | "went" | "missed";
  helped: number | null;
  friendComing: boolean;
  followup?: FollowupResponse;
};

const listeners = new Set<() => void>();
let cache: { token: string | null; list: PlanRecord[] } = { token: null, list: [] };

const key = () => `compass.plans.${session.token() ?? "none"}`;

function load(): PlanRecord[] {
  const tok = session.token();
  if (cache.token === tok) return cache.list;
  let list: PlanRecord[] = [];
  try {
    list = JSON.parse(sessionStorage.getItem(key()) ?? "[]");
  } catch {
    list = [];
  }
  cache = { token: tok, list };
  return list;
}

function save(list: PlanRecord[]) {
  cache = { token: session.token(), list };
  try {
    sessionStorage.setItem(key(), JSON.stringify(list));
  } catch {
    // memory only
  }
  listeners.forEach(fn => fn());
}

session.subscribe(() => listeners.forEach(fn => fn()));

export const plans = {
  all: load,
  get: (id: number) => load().find(p => p.commitment.commitment_id === id) ?? null,
  add(c: CommitResponse) {
    const list = load().filter(p => p.commitment.commitment_id !== c.commitment_id);
    save([{ commitment: c, status: "planned", helped: null, friendComing: false }, ...list]);
  },
  update(id: number, patch: Partial<PlanRecord>) {
    save(load().map(p => (p.commitment.commitment_id === id ? { ...p, ...patch } : p)));
  },
  pending: () => load().find(p => p.status === "planned") ?? null,
  clear: () => save([]),
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
};

export function usePlans(): PlanRecord[] {
  return useSyncExternalStore(plans.subscribe, plans.all, plans.all);
}
