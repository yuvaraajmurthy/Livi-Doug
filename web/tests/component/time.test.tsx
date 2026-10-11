import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { API, fixture, renderAt, setupPersona } from "../helpers";
import { TimeSheet } from "../../src/features/time/TimeSheet";
import { clock } from "../../src/session/clock";
import { session, sessionFromToken } from "../../src/session/session";

describe("time sheet", () => {
  beforeEach(() => {
    setupPersona("andre");
    clock.observe("2026-10-12T09:00:00-04:00");
  });

  it("skips to the next reminder and moves the clock", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${API}/demo/skip-ahead`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(fixture("andre", "skip_ahead"));
      }),
    );
    renderAt(<TimeSheet open onClose={() => {}} />, "/next");
    await userEvent.click(screen.getByRole("button", { name: /Skip to the next reminder/ }));
    await screen.findByRole("dialog");
    expect(body).toEqual({ to: "next_due" });
    expect(clock.get()).toBe("2026-10-13T12:15:00-04:00");
  });

  it("jumps to a preset date through the clock endpoint", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${API}/demo/clock`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...(fixture("andre", "session") as object), now: "2026-10-19T09:00:00-04:00" });
      }),
    );
    renderAt(<TimeSheet open onClose={() => {}} />, "/next");
    await userEvent.click(screen.getByRole("button", { name: /Mon Oct 19/ }));
    expect(body).toEqual({ now: "2026-10-19T09:00:00-04:00" });
  });

  it("only offers a full reset on the stage session", () => {
    const first = renderAt(<TimeSheet open onClose={() => {}} />, "/next");
    expect(screen.queryByRole("button", { name: /Reset the whole demo/ })).not.toBeInTheDocument();
    first.unmount();
    session.set({ ...sessionFromToken("v1.andre.stage1.sig")!, stage: true });
    renderAt(<TimeSheet open onClose={() => {}} />, "/next");
    expect(screen.getByRole("button", { name: /Reset the whole demo/ })).toBeInTheDocument();
  });
});
