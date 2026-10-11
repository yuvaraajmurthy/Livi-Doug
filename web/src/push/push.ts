// Web Push: register the service worker, subscribe on a user gesture, send the subscription to the API.
// Returns what happened so the UI can say it honestly (iPhone needs Home Screen install; denial leaves the inbox).
import { api } from "../api/client";
import { signal } from "../api/inspector";

export type PushState = "on" | "denied" | "unsupported" | "error";

export function pushSupported(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function pushPermission(): NotificationPermission | "unsupported" {
  return pushSupported() ? Notification.permission : "unsupported";
}

function urlB64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator)) return null;
  try {
    return await navigator.serviceWorker.register("/sw.js");
  } catch {
    return null;
  }
}

export async function enablePush(): Promise<PushState> {
  if (!pushSupported()) return "unsupported";
  try {
    const perm = await Notification.requestPermission();
    if (perm !== "granted") return "denied";
    const reg = (await registerServiceWorker()) ?? (await navigator.serviceWorker.ready);
    const { public_key } = await api.vapidKey();
    if (!public_key) return "unsupported";
    const sub =
      (await reg.pushManager.getSubscription()) ??
      (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8Array(public_key) }));
    const json = sub.toJSON() as { endpoint: string; keys: { p256dh: string; auth: string } };
    await api.subscribePush({ endpoint: json.endpoint, keys: json.keys });
    signal("push:enabled");
    return "on";
  } catch {
    return "error";
  }
}
