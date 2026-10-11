import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router";
import { api } from "../api/client";
import { signal } from "../api/inspector";
import { countUnread, lastSeen } from "../features/inbox/seen";
import { TimeSheet } from "../features/time/TimeSheet";
import { NotificationHost } from "../features/inbox/NotificationBanner";
import { useMap } from "../features/map/useMap";
import { useSession } from "../session/session";
import { TabBar } from "../ui/TabBar";
import { TopBar } from "../ui/TopBar";

/** Student app frame: top bar, page, bottom tabs. Redirects to the entry screen without a session. */
export function Shell() {
  const s = useSession();
  const loc = useLocation();
  const [timeOpen, setTimeOpen] = useState(false);
  const student = s?.role === "student";
  useMap(student);
  const inbox = useQuery({ queryKey: ["inbox"], queryFn: api.inbox, enabled: student });

  useEffect(() => {
    signal("route:changed", loc.pathname);
    // move focus to the page heading for screen readers, without scrolling jumps
    const h = window.setTimeout(() => {
      const h1 = document.querySelector<HTMLElement>("main h1");
      h1?.focus({ preventScroll: true });
    }, 60);
    window.scrollTo({ top: 0 });
    return () => window.clearTimeout(h);
  }, [loc.pathname]);

  if (!s) return <Navigate to="/" replace />;
  if (s.role === "staff") return <Navigate to="/staff" replace />;

  const unread = countUnread(inbox.data?.items ?? [], lastSeen());
  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <TopBar unread={unread} onOpenTime={() => setTimeOpen(true)} />
      <main id="main" className="mx-auto max-w-[480px] px-5 pb-[calc(104px+env(safe-area-inset-bottom))] pt-5 max-[359px]:px-4">
        <Outlet />
      </main>
      <TabBar />
      <TimeSheet open={timeOpen} onClose={() => setTimeOpen(false)} />
      <NotificationHost />
    </div>
  );
}
