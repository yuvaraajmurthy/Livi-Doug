// Switch the app to offline replay: recorded stage story first, then the current persona's backend fixtures.
import { onFailure, setTransport, transportKind } from "../../api/transport";
import { session } from "../../session/session";
import { toast } from "../../ui/Toast";
import { loadReplay, type Recorded } from "./replay";

// Backend fixtures (fixtures/<persona>/<name>.json), bundled lazily; only fetched when replay is switched on.
const FIXTURE_FILES = import.meta.glob("@fixtures/*/*.json", { import: "default" });

const ENDPOINTS: Record<string, string> = {
  "GET /me/map": "me_map",
  "GET /me/next": "me_next",
  "POST /me/focus": "me_focus",
  "POST /me/next/:id/decline": "me_next_after_decline",
  "GET /me/card": "me_card",
  "GET /me/memory": "me_memory",
  "DELETE /me/memory/:id": "delete_result",
  "DELETE /me/memory": "delete_result",
  "DELETE /me": "delete_result",
  "GET /me/inbox": "me_inbox",
  "POST /ask": "ask",
  "POST /commitments": "commitment",
  "POST /followups/:id": "followup",
  "GET /pulse": "pulse",
  "POST /wins": "win_accepted",
  "POST /wins/:id/same-here": "same_here",
  "POST /demo/skip-ahead": "skip_ahead",
  "POST /demo/session": "session",
  "POST /push/subscriptions": "subscription",
  "GET /staff/funnel": "staff_funnel",
  "GET /staff/gaps": "staff_gaps",
  "GET /staff/weekly": "staff_weekly",
  "GET /staff/dips": "staff_dips",
  "GET /staff/retakes": "staff_retakes",
};
const SHARED: Record<string, string> = {
  "GET /demo/personas": "personas",
  "GET /invites/:id": "invite",
  "POST /invites/:id": "invite_accepted",
  "POST /demo/reset": "reset",
};

async function fixtureMap(persona: string): Promise<Record<string, unknown>> {
  const out: Record<string, unknown> = {};
  const load = async (dir: string, name: string) => {
    const entry = Object.entries(FIXTURE_FILES).find(([p]) => p.endsWith(`/${dir}/${name}.json`));
    return entry ? await entry[1]() : undefined;
  };
  for (const [k, name] of Object.entries(ENDPOINTS)) {
    const v = (await load(persona, name)) ?? (persona === "staff" ? undefined : await load("staff", name));
    if (v !== undefined) out[k] = v;
  }
  for (const [k, name] of Object.entries(SHARED)) {
    const v = await load("_shared", name);
    if (v !== undefined) out[k] = v;
  }
  return out;
}

export async function enableReplay(useRecording = true) {
  let calls: Recorded[] = [];
  if (useRecording) {
    try {
      calls = ((await import("./recording.json")).default as { calls: Recorded[] }).calls;
    } catch {
      calls = [];
    }
  }
  const persona = session.get()?.persona ?? "andre";
  loadReplay({ calls, fixtures: await fixtureMap(persona) });
  setTransport("replay");
}

export function disableReplay() {
  setTransport("live");
}

/** After three network/server failures in a row, carry on in replay mode and say so. */
export function installAutoReplay() {
  return onFailure(n => {
    if (n >= 3 && transportKind() === "live") {
      void enableReplay().then(() => toast("Connection lost. Continuing with recorded data.", "amber"));
    }
  });
}
