/**
 * useCustomerPush — Web Push subscription management for platform CUSTOMERS.
 *
 * Mirrors usePushNotifications (owner) but talks to the /customer/ endpoints and uses
 * its own localStorage key, so customer and owner subscriptions are independent. Used to
 * nudge a customer to approve a pending wallet charge even when the app is backgrounded.
 *
 * Shares the same VAPID setup as the owner push (one key pair per deployment).
 */

import { ref, readonly } from 'vue';
import api from '../lib/api';

const _SW_PATH = '/sw.js';
const _LS_KEY = 'customer_push_subscribed';

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

function _urlB64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

async function _checkEnabled() {
  if (_enabled.value) return true;
  try {
    const { data } = await api.get('/customer/push-vapid-key/');
    _enabled.value = !!data?.enabled;
  } catch {
    _enabled.value = false;
  }
  return _enabled.value;
}

export function useCustomerPush() {
  const subscribe = async () => {
    if (!_supported || _loading.value) return;
    _loading.value = true;
    try {
      const { data: vapidData } = await api.get('/customer/push-vapid-key/');
      if (!vapidData?.enabled || !vapidData.public_key) return;
      _enabled.value = true;

      const reg = await navigator.serviceWorker.register(_SW_PATH, { scope: '/' });
      await navigator.serviceWorker.ready;

      const perm = await Notification.requestPermission();
      _permission.value = perm;
      if (perm !== 'granted') return;

      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: _urlB64ToUint8Array(vapidData.public_key),
        });
      }

      const json = sub.toJSON();
      await api.post('/customer/push-subscribe/', {
        endpoint: json.endpoint,
        p256dh: json.keys.p256dh,
        auth: json.keys.auth,
      });

      _subscribed.value = true;
      localStorage.setItem(_LS_KEY, '1');
    } catch (err) {
      console.warn('[customer-push] subscribe failed:', err);
    } finally {
      _loading.value = false;
    }
  };

  const unsubscribe = async () => {
    if (!_supported || _loading.value) return;
    _loading.value = true;
    try {
      const reg = await navigator.serviceWorker.getRegistration(_SW_PATH);
      if (reg) {
        const sub = await reg.pushManager.getSubscription();
        if (sub) {
          await api.delete('/customer/push-subscribe/', {
            data: { endpoint: sub.endpoint },
          }).catch(() => {});
          await sub.unsubscribe();
        }
      }
      _subscribed.value = false;
      localStorage.removeItem(_LS_KEY);
    } catch (err) {
      console.warn('[customer-push] unsubscribe failed:', err);
    } finally {
      _loading.value = false;
    }
  };

  // Re-subscribe silently on load when the customer previously opted in (browser push
  // subscriptions can expire). Call once from CustomerLayout on mount.
  const autoRestore = async () => {
    if (!_supported) return;
    if (Notification.permission !== 'granted') return;
    if (localStorage.getItem(_LS_KEY) !== '1') return;
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
