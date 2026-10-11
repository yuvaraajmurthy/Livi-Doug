// Every path that makes a plan (Today "I'm in", the event card's "Remind me", chat and voice set_reminder) goes
// through here, so they all leave the app in the same state: the plan in the local plan list (Today, You, the plan
// page), the same inspector signals, and fresh student data.
import type { QueryClient } from "@tanstack/react-query";
import type { CommitResponse } from "../../api/client";
import { signal } from "../../api/inspector";
import { clock } from "../../session/clock";
import { plans } from "./plans";

/** Queries whose server data changes when a plan is made (the inbox gets its reminder when it fires). "next" is left
 *  alone: Today hides planned items itself, so a fresh set doesn't push a new step under the plan just made. */
export const PLAN_KEYS = ["inbox", "map", "card"] as const;

export function applyPlan(qc: QueryClient | null, c: CommitResponse, opts: { reminder?: boolean } = {}): void {
  plans.add(c);
  signal("commitment:created", c);
  if (opts.reminder ?? true) signal("reminder:set");
  if (qc) for (const k of PLAN_KEYS) void qc.invalidateQueries({ queryKey: [k] });
}

/** Plans found in saved chat/voice turns (another tab, or a voice call) join the local list if missing.
 *  Ones whose follow-up time has passed are left out: they may already have been answered elsewhere. */
export function hydratePlans(blocks: { type: string; plan?: CommitResponse }[]): void {
  const now = clock.get();
  for (const b of blocks) {
    if (b.type !== "plan" || !b.plan) continue;
    if (now && b.plan.followup_at && new Date(b.plan.followup_at).getTime() < new Date(now).getTime()) continue;
    plans.ensure(b.plan);
  }
}
