import { it, expect, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { clock, bindClockToQueries } from "../../src/session/clock";

it("clock change invalidates student queries, and only on change", () => {
  const qc = new QueryClient();
  const spy = vi.spyOn(qc, "invalidateQueries");
  const unbind = bindClockToQueries(qc);
  clock.observe("2026-10-12T09:00:00-04:00");
  spy.mockClear();
  clock.observe("2026-10-12T09:00:00-04:00");
  expect(spy).not.toHaveBeenCalled();
  clock.observe("2026-10-13T12:15:00-04:00");
  expect(spy).toHaveBeenCalled();
  expect(clock.get()).toBe("2026-10-13T12:15:00-04:00");
  unbind();
});

it("ignores missing values", () => {
  clock.observe("2026-10-12T09:00:00-04:00");
  clock.observe(undefined);
  expect(clock.get()).toBe("2026-10-12T09:00:00-04:00");
});
