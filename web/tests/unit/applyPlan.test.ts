import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { fixture, setupPersona } from "../helpers";
import { applyPlan, hydratePlans } from "../../src/features/plan/applyPlan";
import { plans } from "../../src/features/plan/plans";
import { clock } from "../../src/session/clock";

// Plans made by chat or voice (set_reminder) must end up exactly like the card's "Remind me".
describe("applyPlan", () => {
  beforeEach(() => {
    setupPersona("andre");
    plans.clear();
  });

  it("adds the plan and refreshes inbox, map and card", () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const c = fixture("andre", "commitment");
    applyPlan(qc, c);
    expect(plans.pending()?.commitment.commitment_id).toBe(c.commitment_id);
    const keys = spy.mock.calls.map(([f]) => (f as { queryKey: string[] }).queryKey[0]);
    expect(keys).toEqual(expect.arrayContaining(["inbox", "map", "card"]));
  });

  it("hydrates missing plans from saved turns without resetting answered ones", () => {
    const c = fixture("andre", "commitment");
    const other = { ...c, commitment_id: c.commitment_id + 1 };
    plans.add(c);
    plans.update(c.commitment_id, { status: "went" });
    hydratePlans([{ type: "events" }, { type: "plan", plan: c }, { type: "plan", plan: other }]);
    expect(plans.get(c.commitment_id)?.status).toBe("went");
    expect(plans.get(other.commitment_id)?.status).toBe("planned");
  });

  it("skips saved plans whose follow-up time has already passed", () => {
    const c = { ...fixture("andre", "commitment"), commitment_id: 777, followup_at: "2026-10-01T10:00:00-04:00" };
    clock.observe("2026-10-12T09:00:00-04:00");
    hydratePlans([{ type: "plan", plan: c }]);
    expect(plans.get(777)).toBeNull();
  });
});
