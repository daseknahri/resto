/**
 * useInstallPrompt — PWA "Add to Home Screen" prompt.
 *
 * Captures the `beforeinstallprompt` event so we can show our own install
 * button rather than relying on the browser's default chrome.
 *
 * Usage:
 *   const { canInstall, install } = useInstallPrompt();
 *   // Show button when canInstall.value === true
 *   // Call install() on button click
 */

import { ref, readonly } from 'vue';

const _deferred = ref(null); // BeforeInstallPromptEvent
const _canInstall = ref(false);
const _installed = ref(false);
const _isStandalone = ref(
  typeof window !== 'undefined' && (
    window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone === true
  )
);

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    _deferred.value = e;
    _canInstall.value = true;
  });

  window.addEventListener('appinstalled', () => {
    _deferred.value = null;
    _canInstall.value = false;
    _installed.value = true;
    _isStandalone.value = true;
  });
}

export function useInstallPrompt() {
  const install = async () => {
    if (!_deferred.value) return;
    _deferred.value.prompt();
    const { outcome } = await _deferred.value.userChoice;
    if (outcome === 'accepted') {
      _deferred.value = null;
      _canInstall.value = false;
    }
  };

  return {
    canInstall: readonly(_canInstall),
    installed: readonly(_installed),
    isStandalone: readonly(_isStandalone),
    install,
  };
}
