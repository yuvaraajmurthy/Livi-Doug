import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { http, HttpResponse, delay } from "msw";
import { server } from "../setup";
import { transport, setTransport, parseTrace } from "../../src/api/transport";
import { inspector, type InspectorEvent } from "../../src/api/inspector";

const BASE = "https://api.test";

describe("parseTrace", () => {
  it("parses key=value pairs and ignores junk", () => {
    expect(parseTrace("safety=lexicon;safety_ms=0.4;;")).toEqual({ safety: "lexicon", safety_ms: "0.4" });
    expect(parseTrace(null)).toEqual({});
  });
});

describe("live transport", () => {
  beforeEach(() => setTransport("live", { base: BASE, token: () => "tok" }));
  afterEach(() => vi.useRealTimers());

  it("sends the bearer token and reports fallback and trace to the inspector", async () => {
    server.use(http.get(`${BASE}/me/next`, ({ request }) => {
      expect(request.headers.get("authorization")).toBe("Bearer tok");
      return HttpResponse.json({ now: "2026-10-12T09:00:00-04:00" }, {
        headers: { "X-Compass-Fallback": "fixture", "X-Compass-Trace": "candidates=193;passed=41" } });
    }));
    const seen: InspectorEvent[] = [];
    const off = inspector.on(e => seen.push(e));
    const { call, data } = await transport.request<{ now: string }>("GET", "/me/next");
    off();
    expect(data.now).toBe("2026-10-12T09:00:00-04:00");
    expect(call.fallback).toBe("fixture");
    expect(call.trace).toEqual({ candidates: "193", passed: "41" });
    expect(call.source).toBe("live");
    expect(seen).toHaveLength(1);
  });

  it("surfaces the API's error message", async () => {
    server.use(http.post(`${BASE}/me/focus`, () =>
      HttpResponse.json({ error: "invalid_request", message: "body.dimension: required" }, { status: 422 })));
    await expect(transport.request("POST", "/me/focus", {})).rejects.toThrow("body.dimension: required");
  });

  it("times out after 8s and retries a GET once", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    let hits = 0;
    server.use(http.get(`${BASE}/me/map`, async () => { hits++; await delay("infinite"); return HttpResponse.json({}); }));
    const p = transport.request("GET", "/me/map");
    const assertion = expect(p).rejects.toThrow(/timed out/i);
    await vi.advanceTimersByTimeAsync(16_100);
    await assertion;
    expect(hits).toBe(2);
  });

  it("never retries a POST", async () => {
    let hits = 0;
    server.use(http.post(`${BASE}/commitments`, () => { hits++; return new HttpResponse(null, { status: 502 }); }));
    await expect(transport.request("POST", "/commitments", { rec_id: 1 })).rejects.toThrow();
    expect(hits).toBe(1);
  });

  it("counts consecutive network failures and resets on success", async () => {
    server.use(http.get(`${BASE}/me/inbox`, () => HttpResponse.error()));
    await expect(transport.request("GET", "/me/inbox")).rejects.toThrow();
    expect(transport.failures()).toBe(2);
    server.use(http.get(`${BASE}/me/inbox`, () => HttpResponse.json({ now: "x", items: [] })));
    await transport.request("GET", "/me/inbox");
    expect(transport.failures()).toBe(0);
  });
});
