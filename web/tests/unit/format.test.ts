import { it, expect } from "vitest";
import { clockLabel, shortDate, timeLabel, dayLabel } from "../../src/lib/format";

it("formats in New York time regardless of device zone", () => {
  expect(timeLabel("2026-10-13T16:15:00Z")).toBe("12:15 PM");
  expect(dayLabel("2026-10-12T09:00:00-04:00")).toBe("Monday");
  expect(clockLabel("2026-10-12T09:00:00-04:00")).toBe("Mon Oct 12 · 9:00 AM");
});

it("does not shift date-only values across zones", () => {
  expect(shortDate("2026-09-14")).toBe("Sep 14");
});
