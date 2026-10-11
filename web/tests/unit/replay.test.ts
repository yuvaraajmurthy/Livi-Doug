import { it, expect, beforeEach } from "vitest";
import { loadReplay, replayRequest, routeKey } from "../../src/demo/replay/replay";
import { inspector, type InspectorEvent } from "../../src/api/inspector";

beforeEach(() =>
  loadReplay({
    calls: [
      { method: "GET", path: "/me/next", status: 200, body: { now: "a", pick: { rec_id: 1 } } },
      { method: "POST", path: "/commitments", status: 200, body: { now: "a", commitment_id: 9 } },
      { method: "GET", path: "/me/next", status: 200, body: { now: "b", pick: null } },
    ],
    fixtures: { "GET /me/inbox": { now: "x", items: [] } },
  }),
);

it("replays matching calls in recorded order, then repeats the last", async () => {
  expect((await replayRequest<any>("GET", "/me/next")).data.pick.rec_id).toBe(1);
  expect((await replayRequest<any>("POST", "/commitments", { rec_id: 1 })).data.commitment_id).toBe(9);
  expect((await replayRequest<any>("GET", "/me/next")).data.pick).toBeNull();
  expect((await replayRequest<any>("GET", "/me/next")).data.pick).toBeNull();
});

it("falls back to persona fixtures, then to a clear error", async () => {
  expect((await replayRequest<any>("GET", "/me/inbox")).data.items).toEqual([]);
  await expect(replayRequest("GET", "/staff/funnel")).rejects.toThrow(/not available offline/i);
});

it("normalises ids and tokens in paths and drops the query", () => {
  expect(routeKey("POST", "/followups/3096")).toBe("POST /followups/:id");
  expect(routeKey("GET", "/invites/Id1lD3mS3qr8")).toBe("GET /invites/:id");
  expect(routeKey("POST", "/me/next/8515/decline")).toBe("POST /me/next/:id/decline");
  expect(routeKey("GET", "/staff/gaps?campus=camden")).toBe("GET /staff/gaps");
  expect(routeKey("DELETE", "/me/memory/m%3A2")).toBe("DELETE /me/memory/:id");
});

it("reports replayed calls to the inspector, marked as replay", async () => {
  const seen: InspectorEvent[] = [];
  const off = inspector.on(e => seen.push(e));
  await replayRequest("GET", "/me/next");
  off();
  expect(seen[0]).toMatchObject({ type: "call", call: { source: "replay", path: "/me/next" } });
});

it("mid-story, answers with the current student's data at the current time", async () => {
  const { clock } = await import("../../src/session/clock");
  const { session, sessionFromToken } = await import("../../src/session/session");
  loadReplay({
    calls: [
      { method: "GET", path: "/me/map", status: 200, body: { now: "2026-10-12T09:00:00-04:00", who: "andre-mon" }, persona: "andre" },
      { method: "GET", path: "/me/map", status: 200, body: { now: "2026-10-27T09:00:00-04:00", who: "andre-retake" }, persona: "andre" },
      { method: "GET", path: "/me/map", status: 200, body: { now: "2026-10-12T09:00:00-04:00", who: "priya-mon" }, persona: "priya" },
    ],
    fixtures: {},
  });
  session.set(sessionFromToken("v1.priya.sbX.sig"));
  clock.reset();
  clock.observe("2026-10-12T09:00:00-04:00");
  expect((await replayRequest<any>("GET", "/me/map")).data.who).toBe("priya-mon");
  session.set(sessionFromToken("v1.andre.sbY.sig"));
  clock.observe("2026-10-27T09:00:00-04:00");
  expect((await replayRequest<any>("GET", "/me/map")).data.who).toBe("andre-retake");
  session.clear();
});

it("a new session is matched on the persona it asks for", async () => {
  loadReplay({
    calls: [
      { method: "POST", path: "/demo/session", status: 200, body: { now: "x", persona: "andre", token: "A" }, persona: undefined },
      { method: "POST", path: "/demo/session", status: 200, body: { now: "x", persona: "priya", token: "P" }, persona: "andre" },
    ],
    fixtures: {},
  });
  expect((await replayRequest<any>("POST", "/demo/session", { persona: "priya", sandbox: true })).data.token).toBe("P");
});
