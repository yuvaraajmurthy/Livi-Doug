import { it, expect, afterEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { loadReplay, routeKey } from "../../src/demo/replay/replay";
import { setTransport, startRecording } from "../../src/api/transport";
import { streamChat } from "../../src/features/chat/sse";
import type { ChatSSE } from "../../src/features/chat/types";

const API = "https://api.test";
const FRAMES: ChatSSE[] = [
  { event: "meta", data: { conversation_id: "c-1", now: "2026-10-12T09:00:00-04:00" } },
  { event: "delta", data: { text: "Friday lunch." } },
  { event: "done", data: { message_id: 2, source: "ai" } },
] as ChatSSE[];

afterEach(() => setTransport("live", { base: API }));

it("chat item and history routes keep their names in replay keys", () => {
  expect(routeKey("GET", "/chat/history")).toBe("GET /chat/history");
  expect(routeKey("POST", "/items/pin-andre-lunch-2026-10-13/remind")).toBe("POST /items/:id/remind");
});

it("records a live chat stream as one replayable call", async () => {
  setTransport("live", { base: API, token: () => "v1.andre.x.sig" });
  startRecording();
  server.use(
    http.post(`${API}/chat`, () =>
      new HttpResponse(FRAMES.map(f => `event: ${f.event}\ndata: ${JSON.stringify(f.data)}\n\n`).join(""), {
        headers: { "Content-Type": "text/event-stream" },
      }),
    ),
  );
  await streamChat({ message: "hi", conversation_id: null }, () => {});
  const rec = (globalThis as { __compassRecording?: { path: string; body: unknown; persona?: string }[] }).__compassRecording!;
  expect(rec.at(-1)).toMatchObject({ path: "/chat", persona: "andre", body: { frames: FRAMES } });
});

it("replays a recorded chat stream offline, frame by frame", async () => {
  loadReplay({ calls: [{ method: "POST", path: "/chat", status: 200, body: { frames: FRAMES } }], fixtures: {} });
  setTransport("replay");
  const got: ChatSSE[] = [];
  await streamChat({ message: "hi", conversation_id: null }, e => got.push(e));
  expect(got).toEqual(FRAMES);
});
