import { api, isCrisis, type MapResponse, type S } from "../api/client";
import { signal } from "../api/inspector";
import { queryClient } from "../app/providers";
import type { Persona } from "../demo/types";
import { language } from "../i18n/useT";
import { clock } from "./clock";
import { session } from "./session";

type Barrier = S["FocusRequest"]["barriers"][number];

// What each persona would have tapped in the old focus questionnaire. Profiles start with no barriers, so these stand in
// for them; they match the backend's prewarm script (app/services/prewarm.py) so the cached AI wording is used.
const PERSONA_BARRIERS: Partial<Record<Persona, Barrier[]>> = {
  andre: ["no_time", "dont_know_anyone"],
  priya: ["coursework"],
  sofia: ["no_time", "money"],
  jordan: ["dont_know_anyone", "not_my_scene"],
};

/** No questionnaire: give the engine a focus (the weakest inventory dimension) so a student lands straight on Today. */
async function ensureFocus(persona: Persona, map: MapResponse) {
  if (map.profile.focus || map.care_first || !map.dimensions.length) return;
  const weakest = map.dimensions.reduce((lo, d) => (d.score < lo.score ? d : lo)).dimension;
  const barriers = map.profile.barriers.length ? map.profile.barriers : (PERSONA_BARRIERS[persona] ?? []);
  const r = await api.focus({ dimension: weakest, barriers });
  if (!isCrisis(r)) queryClient.setQueryData<MapResponse>(["map"], m => (m ? { ...m, profile: r.profile } : m));
}

/** Start a fresh demo session and return where the app should land. */
export async function startSession(
  persona: Persona,
  opts: { sandbox?: boolean; stage?: boolean } = {},
): Promise<string> {
  const sandbox = opts.sandbox ?? true;
  queryClient.clear();
  clock.reset();
  try {
    sessionStorage.removeItem("compass.inboxSeen");
  } catch {
    // ignore
  }
  const r = await api.session(persona, sandbox && persona !== "staff");
  session.set({
    token: r.token,
    persona,
    role: r.role === "staff" ? "staff" : "student",
    sandbox: sandbox && persona !== "staff",
    stage: !!opts.stage,
    studentId: r.student_id ?? null,
  });
  signal("session:started", { persona });
  if (persona === "staff") return "/staff";
  const map = await queryClient.fetchQuery({ queryKey: ["map"], queryFn: api.map });
  const l = map.student.language;
  language.set(l === "es" ? "es" : "en");
  await ensureFocus(persona, map);
  return "/next";
}
