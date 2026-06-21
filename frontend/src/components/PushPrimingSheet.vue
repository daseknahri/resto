<template>
  <Teleport to="body">
    <Transition name="ui-fade">
      <div
        v-if="visible"
        class="fixed inset-0 z-[60] flex items-end justify-center bg-slate-950/80 p-3 backdrop-blur-sm sm:items-center sm:p-5"
        @click.self="dismiss"
      >
        <div
          ref="sheetRef"
          role="dialog"
          aria-modal="true"
          aria-labelledby="push-prime-title"
          aria-describedby="push-prime-body"
          class="ui-reveal w-full max-w-sm rounded-3xl border border-slate-800 bg-slate-900 p-6 text-center shadow-2xl shadow-slate-950/60"
          @keydown.esc="dismiss"
        >
          <!-- Bell illustration -->
          <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--color-secondary)]/30 bg-[var(--color-secondary)]/12">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="h-7 w-7 text-[var(--color-secondary)]" aria-hidden="true">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
          </div>

          <h2 id="push-prime-title" class="ui-display mt-4 text-lg font-semibold text-white">
            {{ t("pushPrime.title") }}
          </h2>
          <p id="push-prime-body" class="mt-2 text-sm leading-relaxed text-slate-400">
            {{ t("pushPrime.body") }}
          </p>

          <div class="mt-6 space-y-2.5">
            <button
              type="button"
              class="ui-btn-primary inline-flex w-full items-center justify-center gap-2 py-3 text-sm font-semibold disabled:opacity-50"
              :disabled="accepting"
              :aria-busy="accepting"
              @click="accept"
            >
              <svg v-if="accepting" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3" /></svg>
              {{ t("pushPrime.allow") }}
            </button>
            <button
              type="button"
              class="ui-btn-outline w-full justify-center py-2.5 text-sm"
              :disabled="accepting"
              @click="dismiss"
            >
              {{ t("pushPrime.later") }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { nextTick, ref } from "vue";
import { useI18n } from "../composables/useI18n";
import { useCustomerPush } from "../composables/useCustomerPush";

// localStorage flag so a dismissed soft-ask doesn't nag the user again for a while.
const _DISMISS_KEY = "push_prime_dismissed_at";
// Don't re-show the soft-ask for 30 days after a dismissal.
const _DISMISS_COOLDOWN_MS = 30 * 24 * 60 * 60 * 1000;

const { t } = useI18n();
const { supported, permission, subscribe, checkEnabled } = useCustomerPush();

const visible = ref(false);
const accepting = ref(false);
const sheetRef = ref(null);

const _recentlyDismissed = () => {
  try {
    const at = parseInt(localStorage.getItem(_DISMISS_KEY) || "0", 10);
    return at > 0 && Date.now() - at < _DISMISS_COOLDOWN_MS;
  } catch {
    return false;
  }
};

// Gate: only soft-ask when push is supported, the OS prompt has never been
// answered (permission === 'default'), the deployment has push enabled, and the
// user hasn't recently dismissed this sheet. Mirrors the blueprint's contract.
const maybeShow = async () => {
  if (visible.value) return;
  if (!supported) return;
  if (permission.value !== "default") return;
  if (_recentlyDismissed()) return;
  // Confirm the deployment actually has VAPID push configured before nudging.
  const enabled = await checkEnabled();
  if (!enabled) return;
  // Re-check permission — checkEnabled awaited a round-trip.
  if (permission.value !== "default") return;
  visible.value = true;
  await nextTick();
  sheetRef.value?.focus?.();
};

const dismiss = () => {
  visible.value = false;
  try {
    localStorage.setItem(_DISMISS_KEY, String(Date.now()));
  } catch {
    /* storage unavailable */
  }
};

// On accept → fire the real native OS permission prompt via the shared composable.
const accept = async () => {
  if (accepting.value) return;
  accepting.value = true;
  try {
    await subscribe();
  } finally {
    accepting.value = false;
    // Whatever the user chose at the OS prompt, the soft-ask is done. Persist so
    // we don't show it again (permission is no longer 'default' on a decision).
    dismiss();
  }
};

// The parent triggers the soft-ask at a high-intent moment (post-checkout) via
// this exposed method; the sheet never opens itself on mount.
defineExpose({ maybeShow });
</script>
