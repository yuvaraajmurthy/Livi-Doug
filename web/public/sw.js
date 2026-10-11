// Compass service worker: shows Web Push notifications and opens the right screen when one is tapped.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));

self.addEventListener("push", event => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: "Compass", body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "Compass";
  const options = {
    body: data.body || "",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    tag: data.tag || "compass",
    data: { url: data.url || "/next" },
  };
  event.waitUntil(
    self.registration.showNotification(title, options).then(() =>
      self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(clients => {
        for (const c of clients) c.postMessage({ source: "compass-sw", kind: "push-received", title, tag: options.tag });
      }),
    ),
  );
});

self.addEventListener("notificationclick", event => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/next";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(clients => {
      for (const c of clients) {
        if ("focus" in c) {
          c.navigate(url).catch(() => {});
          return c.focus();
        }
      }
      return self.clients.openWindow(url);
    }),
  );
});
