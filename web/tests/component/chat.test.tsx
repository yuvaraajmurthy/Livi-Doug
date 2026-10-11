import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { server } from "../setup";
import { API, fixture, renderAt, setupPersona } from "../helpers";
import { parseSSE } from "../../src/features/chat/sse";
import { ChatPage } from "../../src/features/chat/ChatPage";

const sse = (frames: [string, unknown][]) =>
  frames.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join("");

const LUNCH = {
  id: "pin-andre-lunch-2026-10-13",
  title: "Commuter lunch and board games (sample)",
  when_label: "Tue Oct 13, 12:30–1:30 PM",
  venue: "Paul Robeson Campus Center",
  cost_label: "Free",
  synthetic: true,
  kind: "event",
};

const DETAIL = {
  ...LUNCH,
  summary: "Drop-in lunch with board and card games.",
  dimensions: ["social"],
  starts_at: "2026-10-13T12:30:00-04:00",
  ends_at: "2026-10-13T13:30:00-04:00",
  address: "350 Dr. Martin Luther King Jr. Blvd, Newark, NJ 07102",
  lat: 40.7415,
  lon: -74.1752,
  campus: "newark",
  cost: "free",
  url: null,
  phone: null,
  hours_text: null,
  walk_min: 1,
  going: { count: 14, label: "14 students are going" },
  source: { name: "Compass sample event (synthetic)", url: null, verified_on: null },
  directions_url: "https://www.google.com/maps/dir/?api=1&destination=40.7415,-74.1752",
  calendar_url: "https://calendar.google.com/calendar/render?action=TEMPLATE",
  ics_url: null,
};

describe("parseSSE", () => {
  it("parses frames split across chunks", () => {
    const p = parseSSE();
    const out = [
      ...p.push('event: delta\ndata: {"te'),
      ...p.push('xt":"Hi"}\n\nevent: done\ndata: {"message_id":1,"source":"ai"}\n\n'),
    ];
    expect(out).toEqual([
      { event: "delta", data: { text: "Hi" } },
      { event: "done", data: { message_id: 1, source: "ai" } },
    ]);
  });
});

describe("Chat", () => {
  beforeEach(() => {
    setupPersona("andre");
    server.use(
      http.get(`${API}/chat/history`, () => HttpResponse.json({ conversation_id: null, messages: [] })),
      http.get(`${API}/items/:id`, () => HttpResponse.json(DETAIL)),
    );
  });

  it("streams a reply with event buttons that open the event card", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${API}/chat`, () =>
        new HttpResponse(
          sse([
            ["meta", { conversation_id: "c-1", now: "2026-10-12T09:00:00-04:00" }],
            ["status", { text: "Picking a few for you…" }],
            ["events", { items: [LUNCH] }],
            ["delta", { text: "This one sits in your " }],
            ["delta", { text: "Tuesday gap." }],
            ["done", { message_id: 2, source: "ai" }],
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );
    renderAt(<ChatPage />, "/chat");
    expect(await screen.findByText(/Hi Andre/)).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: /Message Compass/ }), "anything social this week?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("This one sits in your Tuesday gap.")).toBeInTheDocument();
    expect(screen.getByText("anything social this week?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Commuter lunch and board games/ }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("14 students are going")).toBeInTheDocument();
    expect(within(dialog).getByRole("link", { name: /Directions/ })).toHaveAttribute("href", DETAIL.directions_url);
  });

  it("Remind me on the card posts once and confirms", async () => {
    const user = userEvent.setup();
    let hits = 0;
    server.use(
      http.post(`${API}/chat`, () =>
        new HttpResponse(sse([["events", { items: [LUNCH] }], ["done", { message_id: 2, source: "ai" }]]), {
          headers: { "Content-Type": "text/event-stream" },
        }),
      ),
      http.post(`${API}/items/:id/remind`, async () => {
        hits++;
        await delay(80);
        return HttpResponse.json(fixture("andre", "commitment"));
      }),
    );
    renderAt(<ChatPage />, "/chat");
    await user.type(await screen.findByRole("textbox", { name: /Message Compass/ }), "lunch?{Enter}");
    await user.click(await screen.findByRole("button", { name: /Commuter lunch and board games/ }));
    const dialog = await screen.findByRole("dialog");
    const remind = await within(dialog).findByRole("button", { name: "Remind me" });
    await user.click(remind);
    await user.click(remind);
    expect(await within(dialog).findByText(/Reminder set/)).toBeInTheDocument();
    expect(hits).toBe(1);
  });

  it("a crisis event shows the crisis screen and never echoes the text", async () => {
    const user = userEvent.setup();
    const words = "i do not want to be here anymore";
    server.use(
      http.post(`${API}/chat`, () =>
        new HttpResponse(sse([["crisis", fixture("andre", "me_focus_crisis")], ["done", { message_id: 0, source: "rule" }]]), {
          headers: { "Content-Type": "text/event-stream" },
        }),
      ),
    );
    renderAt(<ChatPage />, "/chat");
    await user.type(await screen.findByRole("textbox", { name: /Message Compass/ }), `${words}{Enter}`);
    expect(await screen.findByRole("heading", { name: "You don't have to handle this alone" })).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(words);
  });

  it("memory chip Undo deletes the fact once", async () => {
    const user = userEvent.setup();
    const deletes: string[] = [];
    server.use(
      http.post(`${API}/chat`, () =>
        new HttpResponse(
          sse([
            ["memory", { id: "m:9", statement: "Plays pickup basketball", kind: "interest" }],
            ["delta", { text: "Noted." }],
            ["done", { message_id: 3, source: "ai" }],
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
      http.delete(`${API}/me/memory/:id`, ({ params }) => {
        deletes.push(String(params.id));
        return HttpResponse.json({ synthetic: true, now: "x", deleted: 1 });
      }),
    );
    renderAt(<ChatPage />, "/chat");
    await user.type(await screen.findByRole("textbox", { name: /Message Compass/ }), "I play basketball{Enter}");
    expect(await screen.findByText(/Plays pickup basketball/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Undo/ }));
    await waitFor(() => expect(deletes).toEqual(["m:9"]));
    expect(await screen.findByText(/Forgotten/)).toBeInTheDocument();
  });
});
