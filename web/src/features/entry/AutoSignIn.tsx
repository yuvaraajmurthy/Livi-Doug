import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import type { Persona } from "../../demo/types";
import { session } from "../../session/session";
import { startSession } from "../../session/start";
import { Spinner } from "../../ui/Spinner";

const PERSONAS: Persona[] = ["andre", "priya", "taylor", "sofia", "jordan", "staff"];

/** /as/:persona — sign straight in as a demo persona (used by the myRutgers embed). Reuses this tab's session. */
export function AutoSignIn() {
  const { persona } = useParams();
  const nav = useNavigate();
  const started = useRef(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const p = persona as Persona;
    if (!PERSONAS.includes(p)) {
      nav("/", { replace: true });
      return;
    }
    const s = session.get();
    if (s?.persona === p) {
      nav(s.role === "staff" ? "/staff" : "/next", { replace: true });
      return;
    }
    startSession(p, { sandbox: true }).then(
      to => nav(to, { replace: true }),
      e => setError((e as Error).message),
    );
  }, [persona, nav]);

  return (
    <main id="main" className="grid min-h-dvh place-items-center px-5">
      {error ? (
        <p className="text-center text-[15px] text-ink-2">
          {error}{" "}
          <Link to="/" className="font-semibold text-scarlet-ink underline">
            Choose a student
          </Link>
        </p>
      ) : (
        <Spinner label="Signing in" className="text-ink-2" />
      )}
    </main>
  );
}
