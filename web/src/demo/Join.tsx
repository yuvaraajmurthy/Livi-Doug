import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { session, sessionFromToken } from "../session/session";
import { toast } from "../ui/Toast";

/** Opened from the stage pairing QR: this phone joins the presenter's session (same student, same clock). */
export function Join() {
  const nav = useNavigate();
  const [bad, setBad] = useState(false);
  useEffect(() => {
    const t = new URLSearchParams(window.location.hash.slice(1)).get("t");
    const s = t ? sessionFromToken(t) : null;
    if (!s) {
      setBad(true);
      return;
    }
    session.set(s);
    toast("Paired. Turn on reminders to get the real push.");
    nav("/you", { replace: true });
  }, [nav]);
  return (
    <main id="main" className="mx-auto max-w-[480px] px-5 pt-16">
      <h1 tabIndex={-1} className="text-[26px] font-semibold outline-none">
        {bad ? "That pairing code didn't work." : "Pairing…"}
      </h1>
      {bad ? <p className="mt-2 text-ink-2">Ask the presenter to show a fresh code.</p> : null}
    </main>
  );
}
