import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../setup";
import { API, fixture } from "../helpers";
import { setTransport } from "../../src/api/transport";
import { queryClient } from "../../src/app/providers";
import { language } from "../../src/i18n/useT";
import { session } from "../../src/session/session";
import { startSession } from "../../src/session/start";
import type { MapResponse } from "../../src/api/client";

function serve(persona: string) {
  const posted: unknown[] = [];
  server.use(
    http.post(`${API}/demo/session`, () => HttpResponse.json(fixture(persona, "session"))),
    http.get(`${API}/me/map`, () => HttpResponse.json(fixture(persona, "me_map"))),
    http.post(`${API}/me/focus`, async ({ request }) => {
      posted.push(await request.json());
      return HttpResponse.json(fixture(persona, "me_focus"));
    }),
  );
  return posted;
}

describe("startSession: no questionnaire", () => {
  beforeEach(() => {
    setTransport("live", { base: API, token: () => session.token() });
    language.set("en");
  });

  it("sets the weakest dimension as focus with the persona's barriers, then lands on Today", async () => {
    const posted = serve("andre");
    expect(await startSession("andre")).toBe("/next");
    expect(posted).toEqual([{ dimension: "social", barriers: ["no_time", "dont_know_anyone"] }]);
    expect(queryClient.getQueryData<MapResponse>(["map"])?.profile.focus).toBe("social");
  });

  it("keeps Sofia in Spanish from her profile", async () => {
    const posted = serve("sofia");
    expect(await startSession("sofia")).toBe("/next");
    expect(posted).toEqual([{ dimension: "financial", barriers: ["no_time", "money"] }]);
    expect(language.get()).toBe("es");
  });

  it("leaves care-first students without a focus", async () => {
    const posted = serve("taylor");
    expect(await startSession("taylor")).toBe("/next");
    expect(posted).toEqual([]);
  });
});
