import { it, expect, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";

const h = vi.hoisted(() => ({ order: [] as string[], release: () => {} }));

vi.mock("../../src/demo/bridge", async orig => ({
  ...(await orig<typeof import("../../src/demo/bridge")>()),
  isStageChild: () => true,
  toParent: vi.fn(),
}));
vi.mock("../../src/demo/perform", () => ({
  perform: vi.fn(async (actions: { kind: string }[]) => {
    const k = actions[0].kind;
    h.order.push(`start ${k}`);
    if (k === "replay") await new Promise<void>(r => (h.release = r));
    h.order.push(`end ${k}`);
  }),
}));

const { StageChild } = await import("../../src/demo/StageChild");

const post = (id: number, kind: string) =>
  window.dispatchEvent(
    new MessageEvent("message", { origin: window.location.origin, data: { source: "compass-stage", kind: "perform", id, actions: [{ kind }] } }),
  );

it("runs stage actions one at a time, so a step waits for offline replay to switch on", async () => {
  render(
    <MemoryRouter>
      <StageChild />
    </MemoryRouter>,
  );
  post(1, "replay");
  post(2, "tap");
  await new Promise(r => setTimeout(r, 50));
  expect(h.order).toEqual(["start replay"]);
  h.release();
  await waitFor(() => expect(h.order).toEqual(["start replay", "end replay", "start tap", "end tap"]));
});
