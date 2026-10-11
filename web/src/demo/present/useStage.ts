import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { CallLog } from "../../api/inspector";
import type { FromApp, ToApp } from "../bridge";
import { current, init, reduce } from "../engine";
import { MAIN_STORY } from "../story";
import type { Action, EngineState, Signal } from "../types";

export type Evidence = Partial<Record<Signal, unknown>> & { calls: CallLog[] };

type Status = "idle" | "performing" | "waiting" | "done" | "error";

/** Drives the main story: arriving at a step performs its actions inside the phone, then waits for its signal. */
export function useStage(frame: React.RefObject<HTMLIFrameElement | null>) {
  const [engine, dispatch] = useReducer(reduce, MAIN_STORY, init);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<Evidence>({ calls: [] });
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const seq = useRef(0);
  const pending = useRef(new Map<number, (err?: string) => void>());
  const engineRef = useRef<EngineState>(engine);
  engineRef.current = engine;

  useEffect(() => {
    const onMessage = (ev: MessageEvent<FromApp>) => {
      if (ev.origin !== window.location.origin || ev.data?.source !== "compass-app") return;
      const m = ev.data;
      if (m.kind === "ready") setReady(true);
      if (m.kind === "call") setEvidence(e => ({ ...e, calls: [m.call, ...e.calls].slice(0, 8) }));
      if (m.kind === "signal") {
        setEvidence(e => ({ ...e, [m.name]: m.data ?? true }));
        if (current(engineRef.current).waitFor === m.name) setStatus("done");
      }
      if (m.kind === "session") setToken(m.token);
      if (m.kind === "performed") {
        pending.current.get(m.id)?.(m.error);
        pending.current.delete(m.id);
      }
      if (m.kind === "key") window.dispatchEvent(new KeyboardEvent("keydown", { key: m.key }));
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  const send = useCallback(
    (actions: Action[]) =>
      new Promise<void>((resolve, reject) => {
        const w = frame.current?.contentWindow;
        if (!w) return reject(new Error("The phone isn't ready yet"));
        const id = ++seq.current;
        pending.current.set(id, err => (err ? reject(new Error(err)) : resolve()));
        const msg: ToApp = { source: "compass-stage", kind: "perform", id, actions };
        w.postMessage(msg, window.location.origin);
      }),
    [frame],
  );

  /** Perform the step at index (arrival), then wait for its signal if it has one. */
  const arrive = useCallback(
    async (index: number) => {
      const step = MAIN_STORY[index];
      setError(null);
      if (!step?.perform?.length) {
        setStatus("done");
        return;
      }
      setStatus("performing");
      try {
        await send(step.perform);
        setStatus(s => (step.waitFor ? (s === "done" ? "done" : "waiting") : "done"));
      } catch (e) {
        setError((e as Error).message);
        setStatus("error");
      }
    },
    [send],
  );

  const next = useCallback(() => {
    const s = engineRef.current;
    if (s.index >= s.steps.length - 1) return;
    if (startedAt === null) setStartedAt(Date.now());
    const to = s.index + 1;
    dispatch({ type: "next" });
    void arrive(to);
  }, [arrive, startedAt]);

  const back = useCallback(() => {
    dispatch({ type: "back" });
    setStatus("done");
  }, []);

  const jump = useCallback(
    (index: number) => {
      dispatch({ type: "jump", index });
      void arrive(index);
    },
    [arrive],
  );

  const retry = useCallback(() => void arrive(engineRef.current.index), [arrive]);

  const restart = useCallback(() => {
    dispatch({ type: "restart" });
    setEvidence({ calls: [] });
    setStatus("idle");
    setStartedAt(null);
    setToken(null);
  }, []);

  return { engine, step: current(engine), status, error, evidence, token, ready, startedAt, next, back, jump, retry, restart, send };
}
