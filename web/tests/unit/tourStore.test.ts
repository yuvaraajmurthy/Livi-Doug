import { describe, it, expect, vi } from "vitest";

vi.mock("../../src/demo/perform", () => ({ perform: vi.fn(async () => {}) }));
vi.mock("../../src/demo/tours", () => ({
  TOURS: {
    andre: [
      { id: "s", chapter: "andre", persona: "andre", perform: [{ kind: "session", persona: "andre" }], coach: "start", claim: "" },
      { id: "ask", chapter: "andre", persona: "andre", target: "chat-input", perform: [{ kind: "type", target: "chat-input", text: "hi" }], waitFor: "chat:answered", coach: "ask", claim: "" },
      { id: "end", chapter: "andre", persona: "andre", coach: "end", claim: "" },
    ],
  },
}));

const { dispatch, runCurrent, startTour, tour } = await import("../../src/demo/tourStore");
const { perform } = await import("../../src/demo/perform");

describe("tour store", () => {
  it("stays busy on a waitFor step until its signal arrives, so a second tap can't repeat it", async () => {
    await startTour("andre");
    expect(tour.get()?.engine.index).toBe(1);
    const run = runCurrent();
    await new Promise(r => setTimeout(r, 120));
    expect(tour.get()?.busy).toBe(true);
    await runCurrent(); // a second tap while waiting does nothing
    expect(perform).toHaveBeenCalledTimes(2); // session + one ask
    dispatch({ type: "signal", name: "chat:answered" });
    await run;
    expect(tour.get()?.engine.index).toBe(2);
    expect(tour.get()?.busy).toBe(false);
  });
});
