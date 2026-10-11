import { ChatCircleDots, Compass, MapTrifold, UserCircle } from "@phosphor-icons/react";
import { NavLink } from "react-router";
import type { Key } from "../i18n/en";
import { useT } from "../i18n/useT";

const TABS: { to: string; label: Key; Icon: typeof Compass; tour: string }[] = [
  { to: "/next", label: "tab.today", Icon: Compass, tour: "tab-today" },
  { to: "/chat", label: "tab.chat", Icon: ChatCircleDots, tour: "tab-chat" },
  { to: "/map", label: "tab.map", Icon: MapTrifold, tour: "tab-map" },
  { to: "/you", label: "tab.you", Icon: UserCircle, tour: "tab-you" },
];

export function TabBar() {
  const t = useT();
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface/92 backdrop-blur-md safe-bottom"
    >
      <ul className="mx-auto flex max-w-[480px] items-stretch justify-around px-2">
        {TABS.map(({ to, label, Icon, tour }) => (
          <li key={to} className="flex-1">
            <NavLink
              to={to}
              data-tour={tour}
              className={({ isActive }) =>
                "flex h-16 flex-col items-center justify-center gap-0.5 text-[12px] font-medium transition-colors " +
                (isActive ? "text-scarlet" : "text-ink-2 hover:text-ink")
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={24} weight={isActive ? "fill" : "regular"} aria-hidden />
                  <span>{t(label)}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
