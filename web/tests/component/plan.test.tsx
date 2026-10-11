import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { server } from "../setup";
import { API, fixture, renderAt, setupPersona } from "../helpers";
import { Today } from "../../src/features/today/Today";
import { PlanView } from "../../src/features/plan/PlanView";
import { InvitePage } from "../../src/features/invite/InvitePage";
import { plans } from "../../src/features/plan/plans";

describe("committing", () => {
  beforeEach(() => {
    setupPersona("andre");
    const map = fixture("andre", "me_map");
    map.profile = { ...map.profile, focus: "social" };
    server.use(http.get(`${API}/me/map`, () => HttpResponse.json(map)));
  });

  it("sends exactly one commitment when I'm in is tapped twice", async () => {
    let hits = 0;
    server.use(
      http.post(`${API}/commitments`, async () => {
        hits++;
        await delay(150);
        return HttpResponse.json(fixture("andre", "commitment"));
      }),
    );
    renderAt(<Today />, "/next");
    const b = await screen.findByRole("button", { name: "I'm in" });
    await userEvent.click(b);
    await userEvent.click(b);
    await waitFor(() => expect(screen.getByTestId("navigated")).toBeInTheDocument());
    expect(hits).toBe(1);
    expect(plans.pending()?.commitment.commitment_id).toBe(3096);
  });
});

describe("plan view", () => {
  beforeEach(() => {
    setupPersona("andre");
    plans.clear();
    plans.add(fixture("andre", "commitment"));
  });

  it("shows the if-then plan, reminder time and calendar links", async () => {
    renderAt(<PlanView />, "/plan/3096", "/plan/:id");
    expect(await screen.findByText(/When class ends on Tuesday at 12:20/)).toBeInTheDocument();
    expect(screen.getByText("We'll remind you at 12:15 PM.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add to calendar" }));
    expect(await screen.findByRole("link", { name: /Google Calendar/ })).toHaveAttribute(
      "href",
      expect.stringContaining("calendar.google.com"),
    );
    expect(screen.getByRole("link", { name: /\.ics/ })).toHaveAttribute(
      "href",
      `${API}/commitments/3096/ics?t=Id1lD3mS3qr8`,
    );
  });

  it("shares the invite link, or copies it when sharing isn't available", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "share", { value: undefined, configurable: true });
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    renderAt(<PlanView />, "/plan/3096", "/plan/:id");
    await user.click(await screen.findByRole("button", { name: /Invite a friend/ }));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("/i/Id1lD3mS3qr8"));

    const share = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "share", { value: share, configurable: true });
    await user.click(screen.getByRole("button", { name: /Invite a friend/ }));
    expect(share).toHaveBeenCalledWith(expect.objectContaining({ url: expect.stringContaining("/i/Id1lD3mS3qr8") }));
  });

  it("says where to find a plan it doesn't know", async () => {
    renderAt(<PlanView />, "/plan/999", "/plan/:id");
    expect(await screen.findByText("This plan is in your You tab.")).toBeInTheDocument();
  });
});

describe("friend invite page", () => {
  beforeEach(() => {
    setupPersona("andre");
    server.use(
      http.get(`${API}/invites/:token`, () => HttpResponse.json(fixture("_shared", "invite"))),
      http.post(`${API}/invites/:token`, () => HttpResponse.json(fixture("_shared", "invite_accepted"))),
    );
  });

  it("lets a friend say they'll come, with no account", async () => {
    renderAt(<InvitePage />, "/i/Id1lD3mS3qr8", "/i/:token");
    expect(await screen.findByText("Your friend thought you might like this. No account needed.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Commuter lunch and board games" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "I'll come" }));
    expect(await screen.findByText("You're in. See you there.")).toBeInTheDocument();
  });
});

describe("today after committing", () => {
  beforeEach(() => {
    setupPersona("andre");
    const map = fixture("andre", "me_map");
    map.profile = { ...map.profile, focus: "social" };
    server.use(http.get(`${API}/me/map`, () => HttpResponse.json(map)));
    plans.clear();
    plans.add(fixture("andre", "commitment"));
  });

  it("shows the plan instead of offering the same step again", async () => {
    renderAt(<Today />, "/next");
    expect(await screen.findByText("You have a plan")).toBeInTheDocument();
    expect(await screen.findByText("Open gym pickup basketball")).toBeInTheDocument();
    expect(screen.queryByTestId("step-card")).not.toBeInTheDocument();
  });
});
