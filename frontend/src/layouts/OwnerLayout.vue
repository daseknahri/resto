<template>
  <div class="ui-shell">
    <header class="ui-header static md:sticky md:top-0 md:z-30">
      <div class="mx-auto w-full max-w-7xl px-4 py-2 md:py-3 ui-fade-up">
        <div class="ui-workspace-stage space-y-3 p-3 md:p-4">
          <div class="relative flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div class="flex min-w-0 items-center gap-3">
              <img
                v-if="tenantLogo"
                :src="tenantLogo"
                :alt="`${tenantName} logo`"
                class="h-9 w-9 shrink-0 rounded-xl border border-slate-700/70 object-cover"
                loading="lazy"
              />
              <div class="min-w-0">
                <h1 class="ui-display truncate text-xl font-semibold text-white md:text-2xl">{{ tenantName }}</h1>
                <div class="mt-1 flex flex-wrap items-center gap-2">
                  <span class="ui-data-strip hidden sm:inline-flex">{{ tenant.meta?.slug || "tenant" }}</span>
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
                <RouterLink to="/menu" class="ui-btn-outline hidden md:inline-flex">{{ t("ownerLayout.publicPreview") }}</RouterLink>
                <button class="ui-pill-nav" @click="signOut">{{ t("common.signOut") }}</button>
              </div>
            </div>
          </div>

          <div class="ui-segmented hidden md:flex">
            <RouterLink to="/owner" class="ui-segmented-button" :data-active="$route.path === '/owner'">{{ t("ownerLayout.dashboard") }}</RouterLink>
            <RouterLink to="/owner/onboarding" class="ui-segmented-button" :data-active="$route.path.startsWith('/owner/onboarding')">{{ t("ownerLayout.menuBuilder") }}</RouterLink>
            <RouterLink to="/owner/reservations" class="ui-segmented-button" :data-active="$route.path.startsWith('/owner/reservations')">{{ t("ownerLayout.reservations") }}</RouterLink>
            <RouterLink to="/menu" class="ui-segmented-button" :data-active="$route.path === '/menu'">{{ t("ownerLayout.publicPreview") }}</RouterLink>
          </div>
        </div>
      </div>
    </header>

    <main class="mx-auto w-full max-w-7xl px-4 py-4 pb-20 md:py-5 md:pb-10">
      <RouterView v-slot="{ Component, route: viewRoute }">
        <Transition name="ui-route" mode="out-in">
          <div :key="viewRoute.fullPath" class="ui-route-frame">
            <component :is="Component" />
          </div>
        </Transition>
      </RouterView>
    </main>

    <nav class="ui-bottom-dock owner-bottom-dock md:hidden">
      <div class="ui-bottom-dock-grid grid-cols-4">
        <RouterLink to="/owner" class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[11px] leading-tight" :data-active="$route.path === '/owner'">
          {{ t("ownerLayout.dashboard") }}
        </RouterLink>
        <RouterLink
          to="/owner/onboarding"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[11px] leading-tight"
          :data-active="$route.path.startsWith('/owner/onboarding')"
        >
          {{ t("ownerLayout.menuBuilder") }}
        </RouterLink>
        <RouterLink
          to="/owner/reservations"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[11px] leading-tight"
          :data-active="$route.path.startsWith('/owner/reservations')"
        >
          {{ t("ownerLayout.reservations") }}
        </RouterLink>
        <RouterLink to="/menu" class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[11px] leading-tight" :data-active="$route.path === '/menu'">
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

<style scoped>
.owner-bottom-dock {
  padding-top: 0.35rem;
  padding-bottom: calc(var(--safe-bottom) + 0.35rem);
}

.owner-dock-link {
  min-height: 2.2rem;
}
</style>
