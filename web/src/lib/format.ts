// Dates are always shown in Rutgers time (America/New_York), whatever the viewer's device zone is.
const TZ = "America/New_York";

const fmt = (opts: Intl.DateTimeFormatOptions, lang = "en") =>
  new Intl.DateTimeFormat(lang === "es" ? "es-US" : "en-US", { timeZone: TZ, ...opts });

export function timeLabel(iso: string, lang = "en"): string {
  return fmt({ hour: "numeric", minute: "2-digit" }, lang).format(new Date(iso));
}

export function dayLabel(iso: string, lang = "en"): string {
  return fmt({ weekday: "long" }, lang).format(new Date(iso));
}

export function shortDate(iso: string, lang = "en"): string {
  // "2026-09-14" (date-only) is a calendar date: render it without shifting zones
  const d = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? new Date(`${iso}T12:00:00-04:00`) : new Date(iso);
  return fmt({ month: "short", day: "numeric" }, lang).format(d);
}

export function clockLabel(iso: string, lang = "en"): string {
  const d = new Date(iso);
  const day = fmt({ weekday: "short", month: "short", day: "numeric" }, lang).format(d).replace(",", "");
  return `${day} · ${timeLabel(iso, lang)}`;
}

export function relativeAgo(iso: string, nowIso: string | null): string {
  if (!nowIso) return shortDate(iso);
  const mins = Math.round((new Date(nowIso).getTime() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m ago`;
  const h = Math.round(mins / 60);
  if (h < 24) return `${h}h ago`;
  return shortDate(iso);
}

export const pct = (x: number) => `${Math.round(x * 100)}%`;
export const score = (x: number) => x.toFixed(1);
