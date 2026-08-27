/* global clients */
import { precacheAndRoute, cleanupOutdatedCaches, createHandlerBoundToURL } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';

// Workbox injects the precache manifest here at build time.
// Includes all Vite-generated JS/CSS chunks, index.html, and icons.
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// SPA shell: serve cached index.html for all navigation requests so the
// app opens instantly on repeat visits even when the network is slow.
// API fetch() calls are not "navigation" requests — they bypass this.
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html')));

// ── Push event ───────────────────────────────────────────────────────────────
self.addEventListener('push', (event) => {
  if (!event.data) return;

  // Default URL is the neutral app root, not an owner-only page: the same
  // /sw.js serves owner, customer, and driver, so a url-less push must never
  // mis-route a customer/driver to /owner/orders.
  let payload = { title: 'New notification', body: '', url: '/' };
  try {
    payload = { ...payload, ...event.data.json() };
  } catch {
    payload.body = event.data.text();
  }

  const targetUrl = payload.url || '/';

  const options = {
    body: payload.body,
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    requireInteraction: false,
    data: { url: targetUrl },
  };

  // Notifications that share a `tag` REPLACE each other, so a static tag made
  // every distinct push overwrite the previous one — during a rush the owner
  // saw only the latest order. Group ONLY when the backend explicitly opts in
  // via `payload.tag`; otherwise OMIT the tag so each push stacks. We do not
  // derive a tag from `payload.url`, because the backend sends the same url
  // for genuinely distinct events (e.g. every new order → /owner/orders), so a
  // url-derived tag would recreate the exact collapse this fixes. `renotify`
  // is only valid alongside a `tag`.
  if (typeof payload.tag === 'string' && payload.tag) {
    options.tag = payload.tag;
    options.renotify = true;
  }

  event.waitUntil(self.registration.showNotification(payload.title, options));
});

// ── Notification click ────────────────────────────────────────────────────────
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || '/';

  event.waitUntil(
    clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          if ('focus' in client) {
            return Promise.resolve(client.navigate(targetUrl)).then((c) => (c || client).focus());
          }
        }
        if (clients.openWindow) return clients.openWindow(targetUrl);
      }),
  );
});
