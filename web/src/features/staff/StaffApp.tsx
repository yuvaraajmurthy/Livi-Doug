import { ChartBar, ChartLine, ChatCircleText, SignOut, SquaresFour } from "@phosphor-icons/react";
import { useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useNavigate } from "react-router";
import type { StaffFilters } from "../../api/client";
import { useClock } from "../../session/clock";
import { session, useSession } from "../../session/session";
import { clockLabel } from "../../lib/format";
import { LogoMark } from "../../ui/Logo";
import { AskData } from "./AskData";
import { Filters } from "./Filters";
import { Gaps } from "./Gaps";
import { Overview } from "./Overview";
import { Trends } from "./Trends";

const NAV = [
  { to: "/staff", end: true, label: "Overview", Icon: SquaresFour },
  { to: "/staff/gaps", label: "Where supply is thin", Icon: ChartBar },
  { to: "/staff/trends", label: "Trends", Icon: ChartLine },
  { to: "/staff/ask", label: "Ask the data", Icon: ChatCircleText },
];

export function StaffApp() {
  const s = useSession();
  const now = useClock();
  const nav = useNavigate();
  const [filters, setFilters] = useState<StaffFilters>({});
  if (!s) return <Navigate to="/" replace />;
  if (s.role !== "staff") return <Navigate to="/next" replace />;

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[240px_1fr]">
      <aside className="border-b border-line bg-surface lg:sticky lg:top-0 lg:h-dvh lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between px-5 py-4 lg:block">
          <Link to="/staff" className="flex items-center gap-2">
            <LogoMark size={26} />
            <span className="display text-[22px] leading-none">Staff Pulse</span>
          </Link>
          <button
            type="button"
            onClick={() => {
              session.clear();
              nav("/");
            }}
            className="inline-flex h-10 items-center gap-1.5 rounded-full px-3 text-[14px] text-ink-2 hover:bg-surface-2 lg:mt-6 cursor-pointer"
          >
            <SignOut size={16} aria-hidden />
            Exit
          </button>
        </div>
        <nav aria-label="Staff" className="overflow-x-auto px-3 pb-3 lg:px-3">
          <ul className="flex gap-1 lg:flex-col">
            {NAV.map(n => (
              <li key={n.to}>
                <NavLink
                  to={n.to}
                  end={n.end}
                  data-tour={`staff-${n.to.split("/")[2] ?? "overview"}`}
                  className={({ isActive }) =>
                    `flex h-11 items-center gap-2.5 whitespace-nowrap rounded-xl px-3 text-[15px] font-medium ${
                      isActive ? "bg-ink text-bg" : "text-ink hover:bg-surface-2"
                    }`
                  }
                >
                  <n.Icon size={18} aria-hidden />
                  {n.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      <main id="main" className="mx-auto w-full max-w-[1100px] px-5 pb-16 pt-6 lg:px-10 lg:pt-10">
        <p className="mb-5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[14px] text-ink-2">
          <span className="rounded-full bg-amber-tint px-2.5 py-0.5 font-medium text-amber">Synthetic semester</span>
          <span>as of {now ? clockLabel(now) : "…"}</span>
          <span aria-hidden>·</span>
          <span className="font-medium text-ink">Groups under 10 hidden by the database</span>
        </p>
        <Filters value={filters} onChange={setFilters} />
        <Routes>
          <Route index element={<Overview filters={filters} />} />
          <Route path="gaps" element={<Gaps filters={filters} />} />
          <Route path="trends" element={<Trends filters={filters} />} />
          <Route path="ask" element={<AskData />} />
        </Routes>
      </main>
    </div>
  );
}
