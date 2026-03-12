<template>
  <div class="ui-shell">
    <header class="ui-header">
      <div class="mx-auto w-full max-w-6xl px-4 py-4 ui-fade-up">
        <div class="ui-command-deck space-y-4">
          <div class="relative flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div class="flex min-w-0 items-center gap-3">
              <img
                v-if="tenantLogo"
                :src="tenantLogo"
                :alt="`${tenantName} logo`"
                class="h-10 w-10 shrink-0 rounded-xl border border-slate-700/70 object-cover"
                loading="lazy"
              />
              <div class="min-w-0">
                <p class="ui-kicker">{{ t("ownerLayout.kicker") }}</p>
                <h1 class="ui-display truncate text-2xl font-semibold text-white">{{ tenantName }}</h1>
                <div class="mt-2 flex flex-wrap items-center gap-2">
                  <span class="ui-data-strip">{{ tenant.meta?.slug || "tenant" }}</span>
                  <span v-if="tenant.meta?.plan?.name" class="ui-chip">
                    {{ t("common.plan") }}:
                    <span class="font-semibold text-slate-100">{{ tenant.meta.plan.name }}</span>
                  </span>
                  <span class="rounded-full px-2 py-1 text-[10px] font-semibold" :class="planModeClass">{{ planModeLabel }}</span>
                </div>
              </div>
            </div>

            <div class="flex w-full flex-wrap items-center justify-between gap-2 md:w-auto md:justify-end">
              <LanguageSwitcher />
              <div class="flex items-center gap-2">
                <RouterLink to="/menu" class="ui-btn-outline ui-touch-target hidden md:inline-flex">{{ t("ownerLayout.publicPreview") }}</RouterLink>
                <button class="ui-pill-nav ui-touch-target" @click="signOut">{{ t("common.signOut") }}</button>
              </div>
            </div>
          </div>

          <div class="ui-segmented hidden md:flex">
            <RouterLink to="/owner" class="ui-segmented-button ui-touch-target" :data-active="$route.path === '/owner'">{{ t("ownerLayout.dashboard") }}</RouterLink>
            <RouterLink to="/owner/onboarding" class="ui-segmented-button ui-touch-target" :data-active="$route.path.startsWith('/owner/onboarding')">{{ t("ownerLayout.menuBuilder") }}</RouterLink>
            <RouterLink to="/owner/tables" class="ui-segmented-button ui-touch-target" :data-active="$route.path.startsWith('/owner/tables')">{{ t("ownerLayout.tablesQr") }}</RouterLink>
            <RouterLink to="/owner/reservations" class="ui-segmented-button ui-touch-target" :data-active="$route.path.startsWith('/owner/reservations')">{{ t("ownerLayout.reservations") }}</RouterLink>
            <RouterLink to="/menu" class="ui-segmented-button ui-touch-target" :data-active="$route.path === '/menu'">{{ t("ownerLayout.publicPreview") }}</RouterLink>
          </div>

          <div class="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/80 pt-3">
            <p class="text-xs text-slate-400">{{ t("ownerLayout.setupFlow") }}</p>
            <div class="flex flex-wrap items-center gap-2">
              <span class="ui-chip text-[10px] uppercase tracking-[0.18em] text-slate-300">{{ tenant.meta?.slug || "tenant" }}</span>
              <span class="ui-chip text-[10px] uppercase tracking-[0.18em] text-slate-300">{{ planModeLabel }}</span>
            </div>
          </div>
        </div>
      </div>
    </header>

    <main class="mx-auto w-full max-w-6xl px-4 py-6 pb-28 md:pb-10">
      <RouterView />
    </main>

    <nav class="ui-bottom-dock md:hidden">
      <div class="ui-bottom-dock-grid grid-cols-5">
        <RouterLink to="/owner" class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]">
          {{ t("ownerLayout.dashboard") }}
        </RouterLink>
        <RouterLink to="/owner/onboarding" class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]">
          {{ t("ownerLayout.menuBuilder") }}
        </RouterLink>
        <RouterLink to="/owner/tables" class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]">
          {{ t("ownerLayout.tablesQr") }}
        </RouterLink>
        <RouterLink to="/owner/reservations" class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]">
          {{ t("ownerLayout.reservations") }}
        </RouterLink>
        <RouterLink to="/menu" class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]">
          {{ t("ownerLayout.publicPreview") }}
        </RouterLink>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import LanguageSwitcher from "../components/LanguageSwitcher.vue";
import { useI18n } from "../composables/useI18n";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";

const session = useSessionStore();
const tenant = useTenantStore();
const router = useRouter();
const { t } = useI18n();
const tenantName = computed(() => tenant.meta?.name || t("ownerLayout.fallbackTenantName"));
const tenantLogo = computed(() => String(tenant.meta?.profile?.logo_url || "").trim());
const planModeLabel = computed(() => {
  if (tenant.entitlements?.ordering_mode === "checkout") return t("ownerLayout.checkout");
  if (tenant.entitlements?.ordering_mode === "whatsapp") return t("ownerLayout.whatsapp");
  return t("ownerLayout.browseOnly");
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
