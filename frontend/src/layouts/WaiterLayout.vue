<template>
  <div class="ui-shell">
    <!-- Sticky top bar -->
    <header class="sticky top-0 z-[2000] border-b border-slate-700/60 bg-slate-900/95 backdrop-blur-sm">
      <div class="mx-auto flex w-full max-w-2xl items-center justify-between gap-3 px-3 py-2.5">
        <!-- Left: restaurant name + waiter badge -->
        <div class="flex min-w-0 items-center gap-2.5">
          <img
            v-if="tenantLogo"
            :src="tenantLogo"
            :alt="`${tenantName} logo`"
            class="h-7 w-7 shrink-0 rounded-lg border border-slate-700/70 object-cover"
            loading="eager"
            decoding="async"
            @error="$event.target.style.display='none'"
          />
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold text-slate-100">{{ tenantName }}</p>
            <p class="text-[10px] font-medium uppercase tracking-widest text-slate-400">{{ t('waiterLayout.role') }}</p>
          </div>
        </div>

        <!-- Right: connectivity dot + pending badge + sign-out -->
        <div class="flex shrink-0 items-center gap-2">
          <!-- Offline queue indicator -->
          <span
            v-if="waiter.queueLength > 0"
            class="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
            {{ t('waiterLayout.queued', { count: waiter.queueLength }) }}
          </span>
          <!-- Live / offline dot -->
          <span class="flex items-center gap-1 text-[10px] font-medium" :class="waiter.isOnline ? 'text-emerald-400' : 'text-slate-500'">
            <span
              class="h-2 w-2 rounded-full"
              :class="waiter.isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'"
            />
            {{ waiter.isOnline ? t('waiterLayout.live') : t('waiterLayout.offline') }}
          </span>
          <!-- Back to owner dashboard (owners only) -->
          <RouterLink
            v-if="session.isTenantOwner"
            to="/owner"
            class="rounded-lg border border-slate-700/60 bg-slate-800/60 px-2.5 py-1.5 text-xs text-slate-400 hover:border-slate-500 hover:text-slate-300 transition-colors"
          >
            {{ t('waiterLayout.ownerView') }}
          </RouterLink>
          <!-- Sign out -->
          <button
            class="rounded-lg border border-slate-700/60 bg-slate-800/60 px-2.5 py-1.5 text-xs text-slate-400 hover:border-red-500/40 hover:text-red-300 transition-colors"
            @click="handleSignOut"
          >
            {{ t('waiterLayout.signOut') }}
          </button>
        </div>
      </div>
    </header>

    <!-- Page content -->
    <main class="mx-auto w-full max-w-2xl px-3 pb-24 pt-4">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, computed } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";
import { useWaiterStore } from "../stores/waiter";

const { t } = useI18n();
const router = useRouter();
const session = useSessionStore();
const tenant = useTenantStore();
const waiter = useWaiterStore();

const tenantName = computed(() => tenant.meta?.name || "Restaurant");
const tenantLogo = computed(() => tenant.meta?.logo_url || "");

const handleSignOut = async () => {
  await session.signOut();
  router.push({ name: "signin" });
};

onMounted(() => {
  waiter.setupConnectivityListeners();
});

onUnmounted(() => {
  waiter.teardownConnectivityListeners();
});
</script>
