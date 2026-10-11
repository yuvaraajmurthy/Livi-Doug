// Unread = inbox items newer than the last time the inbox was opened (per tab).
const KEY = "compass.inboxSeen";

export function lastSeen(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function markSeen(at: string) {
  try {
    sessionStorage.setItem(KEY, at);
  } catch {
    // ignore
  }
}

export function countUnread(items: { at: string }[], seen: string | null): number {
  if (!seen) return items.length;
  const t = new Date(seen).getTime();
  return items.filter(i => new Date(i.at).getTime() > t).length;
}
