import { describe, it, expect, beforeEach } from "vitest";
import { screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { server } from "../setup";
import { API, fixture, renderAt, setupPersona } from "../helpers";
import { Followup } from "../../src/features/followup/Followup";
import { NotificationHost } from "../../src/features/inbox/NotificationBanner";
import { plans } from "../../src/features/plan/plans";
import { queryClient } from "../../src/app/providers";

describe("follow-up", () => {
  beforeEach(() => {
    setupPersona("andre");
    plans.clear();
    plans.add(fixture("andre", "commitment"));
  });

  it("asks did you go before did it help, and submits once", async () => {
    const user = userEvent.setup();
    let hits = 0;
    let body: unknown = null;
    server.use(
      http.post(`${API}/followups/3096`, async ({ request }) => {
        hits++;
        body = await request.json();
        await delay(100);
        return HttpResponse.json(fixture("andre", "followup"));
      }),
    );
    renderAt(<Followup />, "/followup/3096", "/followup/:id");
    expect(await screen.findByRole("heading", { name: /How was Commuter lunch and board games/ })).toBeInTheDocument();
    expect(screen.queryByText("Did it help?")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yes" }));
    await user.click(await screen.findByRole("radio", { name: "4" }));
    const send = screen.getByRole("button", { name: "Send" });
    await user.click(send);
    await user.click(send);
    expect(await screen.findByText("1 step taken this month. That counts.")).toBeInTheDocument();
    expect(hits).toBe(1);
    expect(body).toEqual({ went: true, helped: 4 });
  });

  it("shows credit, the cup, what Compass learned and the next rung", async () => {
    const user = userEvent.setup();
    renderAt(<Followup />, "/followup/3096", "/followup/:id");
    await user.click(await screen.findByRole("button", { name: "Yes" }));
    await user.click(await screen.findByRole("radio", { name: "4" }));
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Wellness credit added to The Arc (demo)")).toBeInTheDocument();
    expect(screen.getByText("Scarlet Wellness Cup: steps this week")).toBeInTheDocument();
    expect(screen.getByText("+2")).toBeInTheDocument();
    const learned = screen.getByRole("region", { name: "What Compass learned" });
    expect(within(learned).getByText("You enjoyed game-based events")).toBeInTheDocument();
    expect(within(learned).getAllByText("You rated Commuter lunch and board games 4/5").length).toBeGreaterThan(0);
    expect(screen.getByText("That went well. Ready to try something a bit more open next week?")).toBeInTheDocument();
    expect(plans.get(3096)?.status).toBe("went");
  });

  it("a crisis in the win text shows the crisis screen", async () => {
    const user = userEvent.setup();
    server.use(http.post(`${API}/wins`, () => HttpResponse.json(fixture("andre", "win_crisis"))));
    renderAt(<Followup />, "/followup/3096", "/followup/:id");
    await user.click(await screen.findByRole("button", { name: "Yes" }));
    await user.click(await screen.findByRole("radio", { name: "5" }));
    await user.click(screen.getByRole("button", { name: "Send" }));
    await user.type(await screen.findByLabelText(/Share a small win/), "honestly i want to disappear");
    await user.click(screen.getByRole("button", { name: "Post" }));
    expect(await screen.findByRole("heading", { name: "You don't have to handle this alone" })).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("disappear");
  });
});

describe("notification banners", () => {
  beforeEach(() => setupPersona("andre"));

  it("shows a banner for each new inbox item, not for ones already there", async () => {
    let items: unknown[] = [];
    server.use(http.get(`${API}/me/inbox`, () => HttpResponse.json({ synthetic: true, now: "2026-10-12T09:00:00-04:00", items })));
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/next"]}>
          <Routes>
            <Route path="/next" element={<NotificationHost />} />
            <Route path="/plan/:id" element={<div data-testid="plan-page" />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(queryClient.getQueryData(["inbox"])).toBeTruthy());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    items = fixture("andre", "me_inbox").items.filter((i: { kind: string }) => i.kind === "reminder");
    await queryClient.invalidateQueries({ queryKey: ["inbox"] });
    const banner = await screen.findByRole("status");
    expect(within(banner).getByText("Commuter lunch and board games starts in 15 minutes")).toBeInTheDocument();
    await userEvent.click(within(banner).getByRole("button", { name: /starts in 15 minutes/ }));
    expect(await screen.findByTestId("plan-page")).toBeInTheDocument();
  });
});
