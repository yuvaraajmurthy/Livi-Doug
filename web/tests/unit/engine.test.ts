import { describe, it, expect } from "vitest";
import { reduce, init, current } from "../../src/demo/engine";
import { MAIN_STORY } from "../../src/demo/story";
import { TOURS } from "../../src/demo/tours";
import type { StoryStep } from "../../src/demo/types";

const s = (over: Partial<StoryStep>): StoryStep => ({ id: Math.random().toString(36), chapter: "c", persona: "andre", claim: "x", ...over });

describe("demo engine", () => {
  it("advances on next and on the awaited signal only", () => {
    const steps = [s({ target: "a" }), s({ target: "im-in", waitFor: "commitment:created" }), s({})];
    let st = reduce(init(steps), { type: "next" });
    expect(st.index).toBe(1);
    st = reduce(st, { type: "signal", name: "next:shown" });
    expect(st.index).toBe(1);
    st = reduce(st, { type: "signal", name: "commitment:created" });
    expect(st.index).toBe(2);
  });

  it("advances on a tap of the current target when the step waits for nothing", () => {
    const steps = [s({ target: "strengths-cta" }), s({ target: "pick-social" }), s({})];
    let st = reduce(init(steps), { type: "tap", target: "pick-social" });
    expect(st.index).toBe(0);
    st = reduce(st, { type: "tap", target: "strengths-cta" });
    expect(st.index).toBe(1);
  });

  it("does not advance on a tap when the step waits for a signal", () => {
    const steps = [s({ target: "focus-submit", waitFor: "next:shown" }), s({})];
    expect(reduce(init(steps), { type: "tap", target: "focus-submit" }).index).toBe(0);
  });

  it("back returns to the previously visited step; never before the start or past the end", () => {
    let st = init(MAIN_STORY);
    st = reduce(st, { type: "back" });
    expect(st.index).toBe(0);
    st = reduce(st, { type: "jump", index: 4 });
    st = reduce(st, { type: "next" });
    st = reduce(st, { type: "back" });
    expect(st.index).toBe(4);
    st = reduce(st, { type: "jump", index: 999 });
    expect(st.index).toBe(MAIN_STORY.length - 1);
    st = reduce(st, { type: "next" });
    expect(st.index).toBe(MAIN_STORY.length - 1);
    expect(current(reduce(st, { type: "restart" })).id).toBe(MAIN_STORY[0].id);
  });

  it("every step that waits for a signal can be performed or tapped", () => {
    for (const st of [...MAIN_STORY, ...Object.values(TOURS).flat()]) {
      if (st.waitFor) expect(Boolean(st.perform?.length || st.target), st.id).toBe(true);
    }
  });

  it("all sessions are sandboxed (stage and table), so no shared state is touched", () => {
    for (const st of [...MAIN_STORY, ...Object.values(TOURS).flat()])
      for (const a of st.perform ?? []) if (a.kind === "session" && a.persona !== "staff") expect(a.sandbox, st.id).toBe(true);
  });

  it("main story: at most 12 chapters, opens and closes with slides, ids unique", () => {
    expect(new Set(MAIN_STORY.map(x => x.chapter)).size).toBeLessThanOrEqual(12);
    expect(MAIN_STORY[0].slide).toBe("cold-open");
    expect(MAIN_STORY.at(-1)!.slide).toBe("close");
    const ids = [...MAIN_STORY, ...Object.values(TOURS).flat()].map(x => x.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("the story visits the judge's example, care-first, safety and staff", () => {
    const personas = MAIN_STORY.map(x => x.persona);
    for (const p of ["andre", "priya", "taylor", "staff"] as const) expect(personas).toContain(p);
    expect(MAIN_STORY.some(x => x.waitFor === "crisis:shown")).toBe(true);
  });

  it("tours start with their own session and are short", () => {
    for (const [name, tour] of Object.entries(TOURS)) {
      expect(tour[0].perform?.[0]?.kind, name).toBe("session");
      expect(tour.length, name).toBeLessThanOrEqual(14);
      for (const st of tour) expect(st.coach, st.id).toBeTruthy();
    }
  });
});
