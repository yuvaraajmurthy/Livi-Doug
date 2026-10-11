import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { API, fixture, renderAt, setupPersona } from "../helpers";
import { ChatPage } from "../../src/features/chat/ChatPage";
import { plans } from "../../src/features/plan/plans";

const sse = (frames: [string, unknown][]) =>
  frames.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join("");

// "Remind me about the lunch" in chat must leave the same state as the card's Remind me: the plan is in the plan
// list (Today, You, /plan/:id). Cache refresh is covered in tests/unit/applyPlan.test.ts.
describe("chat set_reminder", () => {
  beforeEach(() => {
    setupPersona("andre");
    plans.clear();
  });

  it("adds the plan from the stream to the plan list", async () => {
    const user = userEvent.setup();
    const plan = fixture("andre", "commitment");
    server.use(
      http.get(`${API}/chat/history`, () => HttpResponse.json({ conversation_id: null, messages: [] })),
      http.post(`${API}/chat`, () =>
        new HttpResponse(
          sse([
            ["meta", { conversation_id: "c-1", now: "2026-10-12T09:00:00-04:00" }],
            ["status", { text: "Setting your reminder…" }],
            ["plan", plan],
            ["delta", { text: "Done, I'll remind you Tuesday." }],
            ["done", { message_id: 2, source: "ai" }],
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );
    renderAt(<ChatPage />, "/chat");
    await user.type(await screen.findByRole("textbox", { name: /Message Compass/ }), "yes remind me about the lunch");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Done, I'll remind you Tuesday.")).toBeInTheDocument();
    expect(plans.pending()?.commitment.commitment_id).toBe(plan.commitment_id);
    expect(screen.getByRole("link", { name: /View plan/ })).toHaveAttribute("href", `/plan/${plan.commitment_id}`);
  });

  it("restores plans saved in earlier turns (e.g. made by voice) into the plan list", async () => {
    const plan = fixture("andre", "commitment");
    server.use(
      http.get(`${API}/chat/history`, () =>
        HttpResponse.json({
          conversation_id: "c-old",
          messages: [
            { id: 1, role: "user", text: "remind me about the lunch", blocks: [], at: "2026-10-12T08:59:00-04:00" },
            { id: 2, role: "assistant", text: "Done.", blocks: [{ type: "plan", plan }], at: "2026-10-12T09:00:00-04:00" },
          ],
        }),
      ),
    );
    renderAt(<ChatPage />, "/chat");
    expect(await screen.findByText("Done.")).toBeInTheDocument();
    expect(plans.get(plan.commitment_id)?.status).toBe("planned");
  });
});
