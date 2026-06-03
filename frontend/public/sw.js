/* eslint-disable */
'use strict';

/**
 * Service Worker — Web Push notification handler for the owner dashboard.
 *
 * This SW is intentionally minimal: it handles push events (showing the OS
 * notification) and notificationclick events (focusing/opening the owner tab).
 *
 * It does NOT implement cache strategies — Vite manages those separately.
 * Registered from usePushNotifications.js at /sw.js (root scope).
 */

// ── Push event ───────────────────────────────────────────────────────────────
self.addEventListener('push', (event) => {
  if (!event.data) return;

  let payload = { title: 'New order', body: '', url: '/owner/orders' };
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
      tag: 'new-order',          // Replace previous unread notification of same tag
      renotify: true,             // Re-alert even if a 'new-order' notification already exists
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
        // Focus any existing app window and navigate it to the target (works for both
        // the owner dashboard and customer-facing pages like /account).
        for (const client of clientList) {
          if ('focus' in client) {
            return Promise.resolve(client.navigate(targetUrl)).then((c) => (c || client).focus());
          }
        }
        // Otherwise open a new window.
        if (clients.openWindow) {
          return clients.openWindow(targetUrl);
        }
      }),
  );
});
