<template>
  <div class="ui-shell">
    <header class="ui-header">
      <div class="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-4 md:flex-row md:items-center md:justify-between ui-fade-up">
        <div class="flex min-w-0 items-center gap-3">
          <img
            v-if="tenantLogo"
            :src="tenantLogo"
            :alt="`${tenantName} logo`"
            class="h-10 w-10 shrink-0 rounded-xl border border-slate-700/70 object-cover"
            loading="lazy"
          />
          <div class="min-w-0">
          <h1 class="ui-display truncate text-xl font-semibold text-white">{{ tenantName }}</h1>
          <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Owner workspace</p>
          <p v-if="tenant.meta?.plan?.name" class="mt-1 text-xs text-slate-400">
            Plan: <span class="font-semibold text-slate-200">{{ tenant.meta.plan.name }}</span>
            <span class="ml-2 rounded-full px-2 py-0.5 text-[10px] font-semibold" :class="planModeClass">{{ planModeLabel }}</span>
          </p>
          </div>
        </div>

        <div class="ui-scroll-row w-full md:w-auto md:flex md:flex-wrap md:items-center md:gap-2 md:overflow-visible md:pb-0">
          <RouterLink to="/owner" class="ui-pill-nav ui-touch-target">Dashboard</RouterLink>
          <RouterLink to="/owner/onboarding" class="ui-pill-nav ui-touch-target">Menu Builder</RouterLink>
          <RouterLink to="/owner/tables" class="ui-pill-nav ui-touch-target">Tables & QR</RouterLink>
          <RouterLink to="/owner/reservations" class="ui-pill-nav ui-touch-target">Reservations</RouterLink>
          <RouterLink to="/menu" class="ui-pill-nav ui-touch-target">Public Preview</RouterLink>
          <button class="ui-pill-nav ui-touch-target" @click="signOut">Sign out</button>
        </div>
      </div>
      <div class="ui-divider"></div>
      <div class="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-2">
        <p class="text-xs text-slate-400">Setup flow: Branding -> Categories -> Dishes -> Theme -> Publish</p>
        <div class="flex flex-wrap items-center gap-2">
          <span class="ui-chip text-[10px] uppercase tracking-[0.18em] text-slate-300">{{ tenant.meta?.slug || "tenant" }}</span>
          <span class="ui-chip text-[10px] uppercase tracking-[0.18em] text-slate-300">{{ planModeLabel }}</span>
        </div>
      </div>
    </header>

    <main class="mx-auto w-full max-w-6xl px-4 py-6 pb-10">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";

const session = useSessionStore();
const tenant = useTenantStore();
const router = useRouter();
const tenantName = computed(() => tenant.meta?.name || "Your Restaurant");
const tenantLogo = computed(() => String(tenant.meta?.profile?.logo_url || "").trim());
const planModeLabel = computed(() => {
  if (tenant.entitlements?.ordering_mode === "checkout") return "Checkout";
  if (tenant.entitlements?.ordering_mode === "whatsapp") return "WhatsApp";
  return "Browse only";
});
const planModeClass = computed(() => {
  if (tenant.entitlements?.ordering_mode === "checkout") return "bg-emerald-500/20 text-emerald-300";
  if (tenant.entitlements?.ordering_mode === "whatsapp") return "bg-amber-500/20 text-amber-300";
  return "bg-sky-500/20 text-sky-300";
});

const signOut = async () => {
  await session.signOut();
  router.push({ name: "home" });
};

onMounted(async () => {
  if (!tenant.meta && !tenant.loading) {
    await tenant.fetchMeta();
  }
});
</script>
