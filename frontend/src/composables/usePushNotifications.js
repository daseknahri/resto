/**
 * usePushNotifications — Web Push subscription management for the owner dashboard.
 *
 * Uses the W3C Push API + VAPID. No external paid service needed.
 *
 * VAPID setup (one-time, per deployment):
 *   1. Run the key-generation snippet from backend/menu/push.py
 *   2. Set VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY in Coolify env vars
 *   3. Deploy — the bell icon will appear automatically once the key is set
 */

import { ref, readonly } from 'vue';
import api from '../lib/api';

const _SW_PATH = '/sw.js';
const _LS_KEY = 'owner_push_subscribed';

// ── Module-level singletons so all components share the same state ────────────
const _supported =
  typeof window !== 'undefined' &&
  'serviceWorker' in navigator &&
  'PushManager' in window &&
  'Notification' in window;

const _permission = ref(
  typeof Notification !== 'undefined' ? Notification.permission : 'denied',
);
const _subscribed = ref(
  typeof localStorage !== 'undefined' && localStorage.getItem(_LS_KEY) === '1',
);
const _loading = ref(false);
const _enabled = ref(false); // true once VAPID public key confirmed present

/** Convert a URL-safe base64 string to Uint8Array (required by pushManager.subscribe) */
function _urlB64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

/** Check whether the server has VAPID keys configured (fast, cached). */
async function _checkEnabled() {
  if (_enabled.value) return true;
  try {
    const { data } = await api.get('/owner/push-vapid-key/');
    _enabled.value = !!data?.enabled;
  } catch {
    _enabled.value = false;
  }
  return _enabled.value;
}

export function usePushNotifications() {
  /**
   * Request permission + register SW + subscribe to push + save to backend.
   * Safe to call multiple times — returns early if already subscribed.
   */
  const subscribe = async () => {
    if (!_supported || _loading.value) return;
    _loading.value = true;
    try {
      // 1. Confirm the server has VAPID keys
      const { data: vapidData } = await api.get('/owner/push-vapid-key/');
      if (!vapidData?.enabled || !vapidData.public_key) return;
      _enabled.value = true;

      // 2. Register service worker
      const reg = await navigator.serviceWorker.register(_SW_PATH, { scope: '/' });
      await navigator.serviceWorker.ready;

      // 3. Request OS-level notification permission
      const perm = await Notification.requestPermission();
      _permission.value = perm;
      if (perm !== 'granted') return;

      // 4. Create / retrieve the browser-side push subscription
      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: _urlB64ToUint8Array(vapidData.public_key),
        });
      }

      // 5. Persist to backend
      const json = sub.toJSON();
      await api.post('/owner/push-subscribe/', {
        endpoint: json.endpoint,
        p256dh: json.keys.p256dh,
        auth: json.keys.auth,
      });

      _subscribed.value = true;
      localStorage.setItem(_LS_KEY, '1');
    } catch (err) {
      console.warn('[push] subscribe failed:', err);
    } finally {
      _loading.value = false;
    }
  };

  /** Unsubscribe from push and remove from backend. */
  const unsubscribe = async () => {
    if (!_supported || _loading.value) return;
    _loading.value = true;
    try {
      const reg = await navigator.serviceWorker.getRegistration(_SW_PATH);
      if (reg) {
        const sub = await reg.pushManager.getSubscription();
        if (sub) {
          // Remove from backend first (best-effort)
          await api.delete('/owner/push-subscribe/', {
            data: { endpoint: sub.endpoint },
          }).catch(() => {});
          await sub.unsubscribe();
        }
      }
      _subscribed.value = false;
      localStorage.removeItem(_LS_KEY);
    } catch (err) {
      console.warn('[push] unsubscribe failed:', err);
    } finally {
      _loading.value = false;
    }
  };

  /**
   * Auto-restore subscription on page load when the user previously subscribed.
   * Call this once from OwnerLayout on mount.
   */
  const autoRestore = async () => {
    if (!_supported) return;
    if (Notification.permission !== 'granted') return;
    if (localStorage.getItem(_LS_KEY) !== '1') return;
    // Silently re-subscribe to keep the backend subscription fresh
    // (browser push subscriptions can expire after ~30 days)
    await subscribe();
  };

  return {
    supported: _supported,
    enabled: readonly(_enabled),
    permission: readonly(_permission),
    subscribed: readonly(_subscribed),
    loading: readonly(_loading),
    subscribe,
    unsubscribe,
    autoRestore,
    checkEnabled: _checkEnabled,
  };
}
