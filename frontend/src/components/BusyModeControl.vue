<template>
  <div :class="compact ? 'contents' : ''">
  <!-- Compact variant: single topbar button (OwnerKitchen) — opens the shared sheet -->
  <button
    v-if="compact"
    type="button"
    class="kitchen-fs-btn ui-press px-2.5 text-[11px] font-bold uppercase tracking-wide focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
    :class="active ? 'kitchen-filter-btn--active' : ''"
    :aria-pressed="active"
    :aria-label="t('busyMode.title')"
    @click="paused ? resumeNow() : (sheetOpen = true)"
  >
    <template v-if="paused">{{ t('busyMode.resumingIn', { time: pauseCountdownLabel }) }}</template>
    <template v-else-if="extraActive">{{ t('busyMode.busyShort', { min: extraMinutes }) }}</template>
    <template v-else>{{ t('busyMode.title') }}</template>
  </button>

  <!-- Full card variant (OwnerHome) -->
  <div
    v-else
    class="rounded-2xl border px-3.5 py-2.5"
    :class="active
      ? 'border-amber-500/50 bg-amber-500/10'
      : 'border-slate-800 bg-slate-950/40'"
    role="region"
    :aria-label="t('busyMode.title')"
  >
    <!-- Header row: status + primary toggle -->
    <div class="flex items-center justify-between gap-3">
      <div class="min-w-0 leading-snug">
        <p
          class="flex items-center gap-1.5 text-xs font-semibold"
          :class="paused ? 'text-amber-300' : (extraActive ? 'text-amber-200' : 'text-emerald-200')"
          aria-live="polite"
        >
          <span
            class="inline-flex h-2 w-2 shrink-0 rounded-full"
            :class="active ? 'bg-amber-400' : 'bg-emerald-400'"
            aria-hidden="true"
          />
          <template v-if="paused">{{ t('busyMode.pausedStatus') }}</template>
          <template v-else-if="extraActive">{{ t('busyMode.busyStatus', { min: extraMinutes }) }}</template>
          <template v-else>{{ t('busyMode.normalStatus') }}</template>
        </p>
        <!-- Live countdown while paused -->
        <p v-if="paused" class="text-[11px] text-amber-400/90" aria-live="polite">
          {{ t('busyMode.resumingIn', { time: pauseCountdownLabel }) }}
        </p>
        <p v-else class="text-[11px] text-slate-500">{{ t('busyMode.hint') }}</p>
      </div>

      <!-- Resume-now (when paused) OR open-sheet button -->
      <button
        v-if="paused"
        type="button"
        class="ui-touch-target inline-flex shrink-0 items-center gap-1 rounded-full border border-emerald-500/50 px-3 py-1 text-[11px] font-semibold text-emerald-300 transition-colors hover:bg-emerald-500/10 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
        :disabled="saving"
        :aria-busy="saving"
        @click="resumeNow"
      >
        <svg v-if="saving" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
        {{ t('busyMode.resumeNow') }}
      </button>
      <button
        v-else
        type="button"
        class="ui-touch-target inline-flex shrink-0 items-center gap-1 rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
        :class="extraActive
          ? 'border-amber-500/50 text-amber-300 hover:bg-amber-500/10'
          : 'border-slate-700 text-slate-300 hover:border-slate-500 hover:bg-slate-800/40'"
        @click="sheetOpen = true"
      >
        {{ t('busyMode.manage') }}
      </button>
    </div>

    <!-- Active extra-quote chip with clear (shown inline when not paused) -->
    <div v-if="!paused && extraActive" class="mt-2 flex items-center justify-between gap-2">
      <span class="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2.5 py-1 text-[11px] font-semibold text-amber-300">
        {{ t('busyMode.extraChip', { min: extraMinutes }) }} · {{ extraCountdownLabel }}
      </span>
      <button
        type="button"
        class="rounded-full border border-slate-700 px-2.5 py-1 text-[11px] font-medium text-slate-400 transition-colors hover:border-slate-500 hover:text-slate-200 disabled:opacity-50"
        :disabled="saving"
        @click="clearExtra"
      >
        {{ t('busyMode.clearExtra') }}
      </button>
    </div>
  </div>

  <!-- ── Busy-mode sheet (shared by both variants) ───────────────────────── -->
  <Teleport to="body">
      <div
        v-if="sheetOpen"
        class="fixed inset-0 z-[60] flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4"
        role="dialog"
        aria-modal="true"
        :aria-label="t('busyMode.title')"
        @click.self="sheetOpen = false"
      >
        <div class="w-full max-w-md space-y-4 rounded-t-3xl border border-slate-800 bg-slate-950 p-5 shadow-2xl sm:rounded-3xl">
          <div class="flex items-center justify-between gap-2">
            <h2 class="text-base font-semibold text-slate-100">{{ t('busyMode.title') }}</h2>
            <button
              type="button"
              class="ui-touch-target rounded-full p-1 text-slate-400 hover:text-slate-200"
              :aria-label="t('common.close')"
              @click="sheetOpen = false"
            >
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-5 w-5"><path d="M5 5l10 10M15 5L5 15"/></svg>
            </button>
          </div>

          <!-- Pause new orders -->
          <section class="space-y-2">
            <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">{{ t('busyMode.pauseSectionTitle') }}</p>
            <p class="text-[11px] text-slate-500">{{ t('busyMode.pauseSectionHint') }}</p>
            <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <button
                v-for="preset in pausePresets"
                :key="preset.minutes ?? 'manual'"
                type="button"
                class="ui-touch-target rounded-xl border border-amber-500/40 px-3 py-2 text-xs font-semibold text-amber-300 transition-colors hover:bg-amber-500/10 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/60"
                :disabled="saving"
                @click="pauseFor(preset.minutes)"
              >
                {{ preset.label }}
              </button>
            </div>
          </section>

          <!-- Slow the kitchen -->
          <section class="space-y-2">
            <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">{{ t('busyMode.slowSectionTitle') }}</p>
            <p class="text-[11px] text-slate-500">{{ t('busyMode.slowSectionHint') }}</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="mins in extraPresets"
                :key="mins"
                type="button"
                class="ui-touch-target rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/60"
                :class="extraActive && extraMinutes === mins
                  ? 'border-amber-400 bg-amber-500/20 text-amber-200'
                  : 'border-slate-700 text-slate-300 hover:border-amber-500/50 hover:text-amber-300'"
                :disabled="saving"
                @click="setExtra(mins)"
              >
                +{{ mins }} {{ t('busyMode.minShort') }}
              </button>
              <button
                v-if="extraActive"
                type="button"
                class="ui-touch-target rounded-full border border-slate-700 px-3.5 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:border-slate-500 hover:text-slate-200 disabled:opacity-50"
                :disabled="saving"
                @click="clearExtra"
              >
                {{ t('busyMode.clearExtra') }}
              </button>
            </div>
          </section>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useI18n } from "../composables/useI18n";
import { useNowTicker } from "../composables/useNowTicker";
import api from "../lib/api";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";
import { bustCache } from "../lib/staleCache";

defineProps({
  // Compact = a single topbar button (OwnerKitchen). Default = full card (OwnerHome).
  compact: { type: Boolean, default: false },
});

const { t } = useI18n();
const tenant = useTenantStore();
const toast = useToastStore();
// Tick every 10s so the live countdown stays fresh without being wasteful.
const { now } = useNowTicker(10_000);

const profile = computed(() => tenant.meta?.profile || {});
const sheetOpen = ref(false);
const saving = ref(false);

// How long a busy-extra bump lasts when the owner picks one. The pause has
// explicit presets; the kitchen-slowdown auto-clears after this window so a
// quote bump is never left on by accident either.
const EXTRA_WINDOW_MINUTES = 60;

const extraPresets = [10, 20];
const pausePresets = computed(() => [
  { minutes: 15, label: t("busyMode.preset15") },
  { minutes: 30, label: t("busyMode.preset30") },
  { minutes: 60, label: t("busyMode.preset60") },
  { minutes: null, label: t("busyMode.presetManual") },
]);

// ── Derived live state (re-evaluated against the ticking `now`) ──────────────
const pausedUntilMs = computed(() => {
  const raw = profile.value?.orders_paused_until;
  if (!raw) return 0;
  const ms = new Date(raw).getTime();
  return Number.isFinite(ms) ? ms : 0;
});
const paused = computed(() => pausedUntilMs.value > now.value);

const extraMinutes = computed(() => Number(profile.value?.busy_extra_minutes || 0) || 0);
const extraUntilMs = computed(() => {
  const raw = profile.value?.busy_extra_until;
  if (!raw) return 0;
  const ms = new Date(raw).getTime();
  return Number.isFinite(ms) ? ms : 0;
});
const extraActive = computed(() => extraMinutes.value > 0 && extraUntilMs.value > now.value);
const active = computed(() => paused.value || extraActive.value);

const fmtCountdown = (targetMs) => {
  const remainingMs = Math.max(0, targetMs - now.value);
  const totalMin = Math.ceil(remainingMs / 60_000);
  if (totalMin >= 60) {
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    return m ? `${h}h ${m}m` : `${h}h`;
  }
  return t("busyMode.minutesShort", { count: totalMin });
};
const pauseCountdownLabel = computed(() => fmtCountdown(pausedUntilMs.value));
const extraCountdownLabel = computed(() => fmtCountdown(extraUntilMs.value));

// ── Mutations ───────────────────────────────────────────────────────────────
const patchProfile = async (payload, successKey, tone = "info") => {
  if (saving.value) return false;
  saving.value = true;
  try {
    await api.patch("/profile/", payload);
    tenant.mergeProfile(payload);
    bustCache("meta");
    if (successKey) toast.show(t(successKey), tone);
    return true;
  } catch {
    toast.show(t("busyMode.saveFailed"), "error");
    return false;
  } finally {
    saving.value = false;
  }
};

const pauseFor = async (minutes) => {
  // `null` minutes = "Until I resume": pause far out (24h); owner taps Resume now.
  const ms = minutes == null ? 24 * 60 * 60_000 : minutes * 60_000;
  const until = new Date(Date.now() + ms).toISOString();
  const ok = await patchProfile({ orders_paused_until: until }, "busyMode.pausedToast", "info");
  if (ok) sheetOpen.value = false;
};

const resumeNow = async () => {
  await patchProfile({ orders_paused_until: null }, "busyMode.resumedToast", "success");
};

const setExtra = async (mins) => {
  const until = new Date(Date.now() + EXTRA_WINDOW_MINUTES * 60_000).toISOString();
  const ok = await patchProfile(
    { busy_extra_minutes: mins, busy_extra_until: until },
    "busyMode.extraSetToast",
    "info",
  );
  if (ok) sheetOpen.value = false;
};

const clearExtra = async () => {
  await patchProfile(
    { busy_extra_minutes: 0, busy_extra_until: null },
    "busyMode.extraClearedToast",
    "success",
  );
};
</script>
