import { api } from "../api/client";
import { signal } from "../api/inspector";
import { queryClient } from "../app/providers";
import type { Persona } from "../demo/types";
import { language } from "../i18n/useT";
import { clock } from "./clock";
import { session } from "./session";

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
  return map.profile.focus ? "/next" : "/focus";
}
