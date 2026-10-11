import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { http, HttpResponse, type HttpHandler } from "msw";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import { setTransport } from "../src/api/transport";
import { queryClient } from "../src/app/providers";
import { clock } from "../src/session/clock";
import { session, sessionFromToken } from "../src/session/session";
import { language } from "../src/i18n/useT";
import { server } from "./setup";

export const API = "https://api.test";
const FIX = resolve(__dirname, "../../fixtures");

export function fixture<T = any>(persona: string, name: string): T {
  return JSON.parse(readFileSync(resolve(FIX, persona, `${name}.json`), "utf-8"));
}

/** Standard student handlers for one persona, from the backend's recorded fixtures. */
export function personaHandlers(persona: string): HttpHandler[] {
  const j = (name: string) => () => HttpResponse.json(fixture(persona, name));
  return [
    http.get(`${API}/me/map`, j("me_map")),
    http.get(`${API}/me/next`, j("me_next")),
    http.post(`${API}/me/focus`, j("me_focus")),
    http.get(`${API}/me/inbox`, () => HttpResponse.json({ ...(fixture(persona, "me_inbox") as object), items: [] })),
    http.get(`${API}/me/memory`, j("me_memory")),
    http.get(`${API}/pulse`, j("pulse")),
    http.get(`${API}/me/card`, j("me_card")),
    http.post(`${API}/me/next/:id/decline`, j("me_next_after_decline")),
    http.post(`${API}/commitments`, j("commitment")),
    http.post(`${API}/followups/:id`, j("followup")),
    http.post(`${API}/ask`, j("ask")),
    http.post(`${API}/wins`, j("win_accepted")),
    http.post(`${API}/demo/skip-ahead`, j("skip_ahead")),
    http.get(`${API}/meta/barriers`, () =>
      HttpResponse.json({
        barriers: [
          { id: "no_time", label: "No time between class and work", label_es: "No tengo tiempo entre clases y trabajo" },
          { id: "dont_know_anyone", label: "I don't know anyone", label_es: "No conozco a nadie" },
          { id: "coursework", label: "Coursework is eating my time", label_es: "Las tareas me quitan el tiempo" },
        ],
        dimensions: {},
      }),
    ),
  ];
}

export function setupPersona(persona: string) {
  setTransport("live", { base: API, token: () => session.token() });
  queryClient.clear();
  clock.reset();
  language.set("en");
  session.set(sessionFromToken(`v1.${persona}.test.sig`));
  server.use(...personaHandlers(persona));
}

export function renderAt(ui: ReactElement, path: string, routePath = path) {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={routePath} element={ui} />
          <Route path="*" element={<div data-testid="navigated" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
