import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { API, fixture, renderAt, setupPersona } from "../helpers";
import { MapPage } from "../../src/features/map/MapPage";
import { YouPage } from "../../src/features/you/YouPage";
import { CampusPage } from "../../src/features/campus/CampusPage";
import { AskSheet } from "../../src/features/ask/AskSheet";
import { language } from "../../src/i18n/useT";

describe("Map", () => {
  beforeEach(() => setupPersona("andre"));

  it("leads with strengths and names the inventory date", async () => {
    renderAt(<MapPage />, "/map");
    expect(await screen.findByText("From the inventory on Sep 14")).toBeInTheDocument();
    const rows = screen.getAllByTestId("dim-row").map(r => r.getAttribute("data-dimension"));
    expect(rows[0]).toBe("spiritual");
    expect(rows.at(-1)).toBe("social");
    expect(screen.getByText(/Compass never changes them/)).toBeInTheDocument();
  });

  it("shows the change at a retake", async () => {
    const m = fixture("andre", "me_map");
    m.latest = { ...m.latest, take_no: 2, taken_on: "2026-10-26", scores: { ...m.latest.scores, social: 2.4 } };
    m.previous_takes = [{ take_no: 1, taken_on: "2026-09-14", total: 2.73, scores: { social: 1.9 } }];
    m.dimensions = m.dimensions.map((d: { dimension: string }) =>
      d.dimension === "social" ? { ...d, score: 2.4, band: "middle", change: 0.5 } : d,
    );
    server.use(http.get(`${API}/me/map`, () => HttpResponse.json(m)));
    renderAt(<MapPage />, "/map");
    const social = (await screen.findAllByTestId("dim-row")).find(r => r.getAttribute("data-dimension") === "social")!;
    expect(within(social).getByText("2.4")).toBeInTheDocument();
    expect(within(social).getByText(/0\.5 since Sep 14/)).toBeInTheDocument();
  });

  it("switches the chrome to Spanish for Sofia", async () => {
    setupPersona("sofia");
    renderAt(<MapPage />, "/map");
    await waitFor(() => expect(language.get()).toBe("es"));
    expect(await screen.findByRole("heading", { name: "Tu mapa de bienestar" })).toBeInTheDocument();
  });
});

describe("You: memory and privacy", () => {
  beforeEach(() => setupPersona("andre"));

  it("removes one memory fact optimistically with exactly one DELETE", async () => {
    const deletes: string[] = [];
    server.use(
      http.delete(`${API}/me/memory/:id`, ({ params }) => {
        deletes.push(String(params.id));
        return HttpResponse.json({ synthetic: true, now: "x", deleted: 1 });
      }),
    );
    renderAt(<YouPage />, "/you");
    const row = (await screen.findByText("You enjoyed game-based events")).closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: /Remove/ }));
    await waitFor(() => expect(screen.queryByText("You enjoyed game-based events")).not.toBeInTheDocument());
    expect(deletes).toEqual(["m:2"]);
  });

  it("asks before deleting everything or forgetting the student", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    let hits = 0;
    server.use(
      http.delete(`${API}/me`, () => {
        hits++;
        return HttpResponse.json({ synthetic: true, now: "x", deleted: 9 });
      }),
    );
    renderAt(<YouPage />, "/you");
    await userEvent.click(await screen.findByRole("button", { name: "Forget me" }));
    expect(confirm).toHaveBeenCalled();
    expect(hits).toBe(0);
    confirm.mockReturnValue(true);
    await userEvent.click(screen.getByRole("button", { name: "Forget me" }));
    await waitFor(() => expect(hits).toBe(1));
    confirm.mockRestore();
  });
});

describe("Campus", () => {
  beforeEach(() => setupPersona("andre"));

  it("shows cooperative challenges and lets you say same here, rolling back on error", async () => {
    server.use(http.post(`${API}/wins/:id/same-here`, () => new HttpResponse(null, { status: 500 })));
    renderAt(<CampusPage />, "/campus");
    expect(await screen.findByText("Scarlet Wellness Cup: steps this week")).toBeInTheDocument();
    expect(screen.getAllByText(/No individual leaderboard/).length).toBeGreaterThan(0);
    const win = (await screen.findByText(/Went to tutoring for the first time/)).closest("li")!;
    const btn = within(win).getByRole("button", { name: /Same here/ });
    expect(btn).toHaveTextContent("41");
    await userEvent.click(btn);
    await waitFor(() => expect(btn).toHaveTextContent("41"));
  });
});

describe("Ask", () => {
  beforeEach(() => setupPersona("andre"));

  it("answers with items", async () => {
    renderAt(<AskSheet open onClose={() => {}} />, "/next");
    await userEvent.type(screen.getByRole("textbox", { name: "Ask Compass" }), "anything social this week?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("Commuter lunch and board games", { selector: "p" })).toBeInTheDocument();
  });

  it("a crisis question shows the crisis card", async () => {
    server.use(http.post(`${API}/ask`, () => HttpResponse.json(fixture("andre", "me_focus_crisis"))));
    renderAt(<AskSheet open onClose={() => {}} />, "/next");
    await userEvent.type(screen.getByRole("textbox", { name: "Ask Compass" }), "i don't want to be here");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByRole("heading", { name: "You don't have to handle this alone" })).toBeInTheDocument();
  });
});
