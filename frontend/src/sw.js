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

  let payload = { title: 'New notification', body: '', url: '/owner/orders' };
  try {
    payload = { ...payload, ...event.data.json() };
  } catch {
    payload.body = event.data.text();
  }

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      tag: 'new-order',
      renotify: true,
      requireInteraction: false,
      data: { url: payload.url || '/owner/orders' },
    }),
  );
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
