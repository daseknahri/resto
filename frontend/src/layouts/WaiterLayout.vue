<template>
  <div class="ui-shell">
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[9999] focus:rounded-lg focus:bg-slate-900 focus:px-4 focus:py-2 focus:text-sm focus:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-secondary">{{ t('common.skipToMain') }}</a>
    <!-- Sticky top bar -->
    <header class="ui-header z-[2000]">
      <div class="mx-auto flex w-full max-w-2xl items-center justify-between gap-3 px-3 py-2.5 ui-fade-up">
        <!-- Left: restaurant name + waiter badge -->
        <div class="flex min-w-0 items-center gap-2.5">
          <img
            v-if="tenantLogo"
            :src="tenantLogo"
            :alt="`${tenantName} logo`"
            class="h-7 w-7 shrink-0 rounded-xl border border-slate-700/70 object-cover"
            loading="eager"
            decoding="async"
            @error="$event.target.style.display='none'"
          />
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold text-slate-100">{{ tenantName }}</p>
            <p class="ui-kicker text-[10px]">{{ t('waiterLayout.role') }}</p>
          </div>
        </div>

        <!-- Right: connectivity dot + pending badge + sign-out -->
        <div class="flex shrink-0 items-center gap-2">
          <!-- Connectivity status (single live region for queue + online state) -->
          <span class="flex items-center gap-2" role="status" aria-live="polite">
            <!-- Offline queue indicator -->
            <span
              v-show="waiter.queueLength > 0"
              class="ui-chip-strong inline-flex items-center gap-1 px-2 py-0.5 text-[10px]"
            >
              <span class="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400 animate-pulse" aria-hidden="true" />
              {{ t('waiterLayout.queued', { count: waiter.queueLength }) }}
            </span>
            <!-- Live / offline dot -->
            <span
              class="flex items-center gap-1 text-[10px] font-medium"
              :class="waiter.isOnline ? 'text-emerald-400' : 'text-slate-500'"
            >
              <span
                :class="waiter.isOnline ? 'ui-live-dot bg-emerald-400' : 'h-2 w-2 rounded-full bg-slate-600'"
                aria-hidden="true"
              />
              <span>{{ waiter.isOnline ? t('waiterLayout.live') : t('waiterLayout.offline') }}</span>
            </span>
          </span>
          <!-- Language switcher -->
          <LanguageSwitcher compact dropdown />
          <!-- Dark / light toggle -->
          <button
            class="ui-touch-target flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-slate-700/60 bg-slate-800/60 text-slate-400 transition-colors hover:border-amber-500/40 hover:text-amber-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 ui-press"
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
          <!-- Sign out -->
          <button
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center text-xs px-2.5 py-1.5 hover:border-red-500/40 hover:text-red-300"
            type="button"
            @click="handleSignOut"
          >
            {{ t('waiterLayout.signOut') }}
          </button>
        </div>
      </div>
    </header>

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

const { t } = useI18n();
const router = useRouter();
const session = useSessionStore();
const tenant = useTenantStore();
const waiter = useWaiterStore();

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
});

onUnmounted(() => {
  deactivateTheme(); // strip data-owner-theme so other areas stay un-themed
  waiter.teardownConnectivityListeners();
});
</script>
