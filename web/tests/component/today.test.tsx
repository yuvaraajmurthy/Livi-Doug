import { describe, it, expect, beforeEach } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { API, fixture, renderAt, setupPersona } from "../helpers";
import { Today } from "../../src/features/today/Today";

describe("Today (Andre)", () => {
  beforeEach(() => {
    setupPersona("andre");
    const map = fixture("andre", "me_map");
    map.profile = { ...map.profile, focus: "social", barriers: ["no_time", "dont_know_anyone"] };
    server.use(http.get(`${API}/me/map`, () => HttpResponse.json(map)));
  });

  it("keeps a student without a focus on Today (no questionnaire)", async () => {
    server.use(http.get(`${API}/me/map`, () => HttpResponse.json(fixture("andre", "me_map"))));
    renderAt(<Today />, "/next");
    expect(await screen.findByRole("heading", { name: "One step that fits your week" })).toBeInTheDocument();
    expect(screen.queryByTestId("navigated")).not.toBeInTheDocument();
  });

  it("shows one concrete step with the facts that make it fit", async () => {
    renderAt(<Today />, "/next");
    const card = await screen.findByTestId("step-card");
    const c = within(card);
    expect(c.getByRole("heading", { name: "Commuter lunch and board games" })).toBeInTheDocument();
    expect(c.getByText("Sample")).toBeInTheDocument();
    expect(c.getByText("Tue Oct 13, 12:30–1:30 PM")).toBeInTheDocument();
    expect(c.getByText("Fits your Tuesday gap, 12:20–2:30")).toBeInTheDocument();
    expect(c.getByText(/Paul Robeson Campus Center/)).toBeInTheDocument();
    expect(c.getByText("Free")).toBeInTheDocument();
    expect(c.getByText("14 Newark students are going")).toBeInTheDocument();
    expect(c.getByRole("button", { name: "I'm in" })).toBeInTheDocument();
  });

  it("explains the ranking with the real weights", async () => {
    renderAt(<Today />, "/next");
    await userEvent.click(await screen.findByRole("button", { name: "Why this fits" }));
    const dialog = await screen.findByRole("dialog", { name: "Why this fits" });
    const d = within(dialog);
    expect(d.getByText("Matches your focus")).toBeInTheDocument();
    expect(d.getByText("35%")).toBeInTheDocument();
    expect(d.getByText("Fits your schedule")).toBeInTheDocument();
    expect(d.getByText("20%")).toBeInTheDocument();
    expect(d.getByText("72% of 36 Newark commuters rated it 4+")).toBeInTheDocument();
    expect(d.getByText("Code chose this step from fixed weights. AI only wrote the sentence.")).toBeInTheDocument();
  });

  it("lists the two other options under the step", async () => {
    renderAt(<Today />, "/next");
    expect(await screen.findByText("Open gym pickup basketball")).toBeInTheDocument();
    expect(screen.getByText("Togetherall 24/7 peer support community")).toBeInTheDocument();
  });
});

describe("Today (Taylor, care-first)", () => {
  beforeEach(() => setupPersona("taylor"));

  it("puts a person first and holds events back until asked", async () => {
    renderAt(<Today />, "/next");
    const support = await screen.findByTestId("support-card");
    expect(within(support).getByText("Talking to someone can help")).toBeInTheDocument();
    expect(within(support).getByRole("link", { name: /Call.*848-932-7884/ })).toHaveAttribute("href", "tel:848-932-7884");
    expect(screen.queryByRole("button", { name: "I'm in" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Prefer something small to do?" }));
    expect(await screen.findByRole("button", { name: "I'm in" })).toBeInTheDocument();
  });
});
