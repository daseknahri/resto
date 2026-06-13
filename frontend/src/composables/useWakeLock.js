import { onActivated, onDeactivated, onMounted, onUnmounted, ref } from "vue";

/**
 * Screen Wake Lock composable.
 *
 * - Feature-detects navigator.wakeLock before any call.
 * - Requests a 'screen' lock when the page is visible.
 * - Re-acquires on visibilitychange — the browser auto-releases the lock
 *   when the tab is hidden, so we must re-request on each show.
 * - KeepAlive-correct: releases on onDeactivated (navigating away should not
 *   keep another page's screen awake), re-acquires on onActivated. For a
 *   non-KeepAlive host these two hooks simply never fire.
 * - Releases and cleans up on component unmount.
 *
 * Usage:
 *   useWakeLock();   // call inside setup(), no return value needed
 */
export function useWakeLock() {
  const supported = typeof navigator !== "undefined" && "wakeLock" in navigator;
  const active = ref(false);
  let sentinel = null;
  let acquiring = false; // in-flight guard: onMounted + onActivated both fire on first mount

  const acquire = async () => {
    if (!supported) return;
    if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
    if (sentinel || acquiring) return; // already held or a request is in flight
    acquiring = true;
    try {
      sentinel = await navigator.wakeLock.request("screen");
      active.value = true;
      sentinel.addEventListener("release", () => {
        sentinel = null;
        active.value = false;
      });
    } catch {
      // SecurityError (feature policy) or NotAllowedError — silently ignore
      sentinel = null;
      active.value = false;
    } finally {
      acquiring = false;
    }
  };

  const release = async () => {
    if (sentinel) {
      try {
        await sentinel.release();
      } catch {
        /* ignore */
      }
      sentinel = null;
      active.value = false;
    }
  };

  const onVisibilityChange = () => {
    if (typeof document !== "undefined" && document.visibilityState === "visible") {
      // Re-acquire after tab becomes visible — the browser released it while hidden
      acquire();
    }
  };

  onMounted(() => {
    acquire();
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", onVisibilityChange);
    }
  });

  // KeepAlive: give the lock back while this page is parked behind another.
  onActivated(acquire);
  onDeactivated(release);

  onUnmounted(() => {
    release();
    if (typeof document !== "undefined") {
      document.removeEventListener("visibilitychange", onVisibilityChange);
    }
  });

  return { supported, active, acquire, release };
}
