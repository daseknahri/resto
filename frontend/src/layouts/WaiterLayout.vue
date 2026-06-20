<template>
  <div class="ui-shell">
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[9999] focus:rounded-lg focus:bg-slate-900 focus:px-4 focus:py-2 focus:text-sm focus:text-white focus:outline-none focus:ring-2 focus:ring-brand-secondary">{{ t('common.skipToMain') }}</a>
    <!-- Sticky top bar -->
    <header class="ui-header z-[2000]">
      <div class="mx-auto flex w-full max-w-2xl items-center justify-between gap-3 px-3 py-2 ui-fade-up">
        <!-- Left: restaurant logo + name + waiter badge -->
        <div class="flex min-w-0 items-center gap-2.5">
          <img
            v-if="tenantLogo"
            :src="tenantLogo"
            :alt="`${tenantName} logo`"
            class="h-8 w-8 shrink-0 rounded-xl border border-slate-700/70 object-cover shadow-sm shadow-black/20"
            loading="eager"
            decoding="async"
            @error="$event.target.style.display='none'"
          />
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold leading-tight text-slate-100">{{ tenantName }}</p>
            <p class="ui-kicker mt-0.5 text-[10px] leading-none">{{ t('waiterLayout.role') }}</p>
          </div>
        </div>

        <!-- Right: connectivity + queue indicators + controls -->
        <div class="flex shrink-0 items-center gap-1.5">
          <!-- Connectivity status (single live region for queue + online state) -->
          <span class="flex items-center gap-1.5" role="status" aria-live="polite">
            <!-- Offline queue indicator -->
            <span
              v-show="waiter.queueLength > 0"
              class="ui-chip-strong inline-flex items-center gap-1 px-2 py-1 text-[10px] font-semibold"
            >
              <span class="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400 animate-pulse" aria-hidden="true" />
              {{ t('waiterLayout.queued', { count: waiter.queueLength }) }}
            </span>
            <!-- Live / offline dot -->
            <span
              class="inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] font-medium transition-colors"
              :class="waiter.isOnline
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                : 'border-slate-700/60 bg-slate-800/40 text-slate-500'"
            >
              <span
                :class="waiter.isOnline ? 'ui-live-dot bg-emerald-400' : 'h-2 w-2 rounded-full bg-slate-600'"
                aria-hidden="true"
              />
              <span>{{ waiter.isOnline ? t('waiterLayout.live') : t('waiterLayout.offline') }}</span>
            </span>
          </span>

          <!-- Divider -->
          <span class="mx-0.5 h-5 w-px shrink-0 rounded-full bg-slate-700/50" aria-hidden="true" />

          <!-- Language switcher -->
          <LanguageSwitcher compact dropdown />

          <!-- Dark / light toggle -->
          <button
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-slate-700/50 bg-slate-800/50 text-slate-400 transition-colors hover:border-amber-500/40 hover:text-amber-300 ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
            type="button"
            :aria-label="ownerTheme === 'dark' ? t('waiterLayout.themeLight') : t('waiterLayout.themeDark')"
            :title="ownerTheme === 'dark' ? t('waiterLayout.themeLight') : t('waiterLayout.themeDark')"
            @click="toggleTheme"
          >
            <svg v-if="ownerTheme === 'dark'" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-3.5 w-3.5">
              <path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clip-rule="evenodd"/>
            </svg>
            <svg v-else aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-3.5 w-3.5">
              <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"/>
            </svg>
          </button>

          <!-- Back to owner dashboard (owners only) -->
          <RouterLink
            v-if="session.isTenantOwner"
            to="/owner"
            class="ui-pill-nav ui-press ui-touch-target inline-flex items-center text-xs px-2.5 py-1.5"
          >
            {{ t('waiterLayout.ownerView') }}
          </RouterLink>

          <!-- Sign out — always visible to all waiter/staff users -->
          <button
            class="flex h-8 shrink-0 items-center justify-center rounded-xl border border-slate-700/50 bg-slate-800/50 px-2.5 text-xs text-slate-400 transition-colors hover:border-red-500/40 hover:text-red-400 ui-touch-target ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/50"
            type="button"
            @click="handleSignOut"
          >
            {{ t('common.signOut') }}
          </button>
        </div>
      </div>
    </header>

    <!-- Waiter-call bell alerts — a table needs service. Section-filtered server-side. -->
    <div v-if="waiterCallsPending.length" class="mx-auto w-full max-w-2xl px-3 pt-2">
      <div role="alert" class="ui-panel border border-amber-500/40 bg-amber-500/10 p-3 space-y-2">
        <div class="flex items-center gap-2 text-sm font-semibold text-amber-300">
          <span class="relative flex h-2.5 w-2.5">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
            <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-400" />
          </span>
          {{ t('ownerLayout.waiterCallBannerTitle', { count: waiterCallsPending.length }) }}
        </div>
        <ul class="space-y-1.5 list-none p-0">
          <li
            v-for="call in waiterCallsPending"
            :key="call.id"
            class="flex items-center justify-between gap-3 rounded-lg border border-amber-500/20 bg-slate-900/40 px-3 py-2"
          >
            <div class="min-w-0 text-sm">
              <span class="font-semibold text-white">{{ call.table_label || t('ownerLayout.waiterCallTableUnknown') }}</span>
              <span v-if="call.note" class="text-slate-300"> — {{ call.note }}</span>
            </div>
            <button
              type="button"
              class="shrink-0 rounded-lg border border-amber-500/40 px-3 py-1.5 text-xs font-semibold text-amber-200 transition hover:bg-amber-500/15 ui-press ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
              @click="acknowledgeWaiterCall(call.id)"
            >
              {{ t('ownerLayout.waiterCallAcknowledge') }}
            </button>
          </li>
        </ul>
      </div>
    </div>

    <!-- Page content -->
    <main id="main-content" tabindex="-1" class="mx-auto w-full max-w-2xl px-3 pb-24 pt-4">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, computed } from "vue";
import { useRouter } from "vue-router";
import LanguageSwitcher from "../components/LanguageSwitcher.vue";
import { useI18n } from "../composables/useI18n";
import { useOwnerTheme } from "../composables/useOwnerTheme";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";
import { useWaiterStore } from "../stores/waiter";
import { useWaiterCalls } from "../composables/useWaiterCalls";

const { t } = useI18n();
const router = useRouter();
const session = useSessionStore();
const tenant = useTenantStore();
const waiter = useWaiterStore();

// Waiter-call bell alerts — a table pressed the QR "call waiter" bell. These were
// previously visible ONLY to the owner; floor staff now see + acknowledge them here.
// The list is section-filtered server-side, so a waiter sees only their own tables.
const { pending: waiterCallsPending, load: loadWaiterCalls, acknowledge: acknowledgeWaiterCall } = useWaiterCalls();
let _waiterCallsTimer = null;
const _onWaiterCallsVisibility = () => {
  if (document.visibilityState === "visible") loadWaiterCalls();
};

// Reuse the staff workspace theme (same ui-* primitives + light CSS as the owner area).
const { theme: ownerTheme, toggleTheme, activate: activateTheme, deactivate: deactivateTheme } = useOwnerTheme();

const tenantName = computed(() => tenant.meta?.name || "Restaurant");
const tenantLogo = computed(() => tenant.meta?.logo_url || "");

const handleSignOut = async () => {
  await session.signOut();
  router.push({ name: "signin" });
};

onMounted(() => {
  activateTheme(); // paint the saved dark/light choice onto <html>
  waiter.setupConnectivityListeners();
  loadWaiterCalls();
  // Poll frequently — a bell-call is urgent; visibilitychange catches up instantly
  // when the waiter switches back to the app.
  _waiterCallsTimer = setInterval(loadWaiterCalls, 12000);
  document.addEventListener("visibilitychange", _onWaiterCallsVisibility);
});

onUnmounted(() => {
  deactivateTheme(); // strip data-owner-theme so other areas stay un-themed
  waiter.teardownConnectivityListeners();
  if (_waiterCallsTimer) clearInterval(_waiterCallsTimer);
  document.removeEventListener("visibilitychange", _onWaiterCallsVisibility);
});
</script>
