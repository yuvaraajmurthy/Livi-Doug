import { useEffect } from "react";
import { useLocation } from "react-router";
import { inspector } from "../api/inspector";
import { session } from "../session/session";
import { isStageChild, STAGE_KEYS, toParent, type ToApp } from "./bridge";
import { perform } from "./perform";

/** Mounted in every app page; only active when running inside the stage presenter's iframe. */
export function StageChild() {
  const loc = useLocation();
  const active = isStageChild();

  useEffect(() => {
    if (!active) return;
    toParent({ kind: "ready", route: window.location.pathname });
    const offInspector = inspector.on(e => {
      if (e.type === "call") toParent({ kind: "call", call: e.call });
      else toParent({ kind: "signal", name: e.name, data: e.data });
    });
    let lastToken = session.token();
    const offSession = session.subscribe(() => {
      const s = session.get();
      if (s && s.token !== lastToken) {
        lastToken = s.token;
        toParent({ kind: "session", token: s.token, persona: s.persona });
      }
    });
    // One at a time: a step's actions must not start while an earlier switch (offline replay loading) is still running.
    let queue = Promise.resolve();
    const onMessage = (ev: MessageEvent<ToApp>) => {
      if (ev.origin !== window.location.origin || ev.data?.source !== "compass-stage") return;
      const msg = ev.data;
      if (msg.kind !== "perform") return;
      queue = queue.then(async () => {
        try {
          await perform(msg.actions, { stage: true });
          toParent({ kind: "performed", id: msg.id });
        } catch (e) {
          toParent({ kind: "performed", id: msg.id, error: (e as Error).message });
        }
      });
    };
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement | null)?.closest?.("input, textarea, select");
      // on stage nobody types by hand: navigation keys (and the clicker) always drive the story
      const nav = ["ArrowRight", "ArrowLeft", "PageDown", "PageUp"].includes(e.key);
      if ((nav || !typing) && STAGE_KEYS.has(e.key)) {
        e.preventDefault();
        toParent({ kind: "key", key: e.key });
      }
    };
    window.addEventListener("message", onMessage);
    window.addEventListener("keydown", onKey);
    return () => {
      offInspector();
      offSession();
      window.removeEventListener("message", onMessage);
      window.removeEventListener("keydown", onKey);
    };
  }, [active]);

  useEffect(() => {
    if (active) toParent({ kind: "ready", route: loc.pathname });
  }, [loc.pathname, active]);

  return null;
}
