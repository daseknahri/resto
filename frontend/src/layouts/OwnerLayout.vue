<template>
  <div class="ui-shell">
    <header class="ui-header">
      <div class="mx-auto w-full max-w-7xl px-4 py-4 ui-fade-up">
        <div class="ui-workspace-stage space-y-4">
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
                <p class="mt-3 max-w-2xl text-sm text-slate-300">{{ t("ownerLayout.setupFlow") }}</p>
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

          <div class="ui-context-band space-y-3">
            <div class="grid gap-2 lg:grid-cols-[minmax(0,1.2fr),repeat(3,minmax(0,1fr))]">
              <article class="ui-context-stat min-w-0">
                <p class="ui-kicker">{{ currentSectionLabel }}</p>
                <p class="mt-1 truncate text-sm font-semibold text-white">{{ tenantName }}</p>
                <p class="mt-1 text-xs text-slate-400">{{ t("ownerHome.launchProgress") }} {{ ownerReadinessLabel }}</p>
              </article>
              <article class="ui-context-stat">
                <p class="ui-kicker">{{ t("ownerHome.state") }}</p>
                <p class="mt-1 text-sm font-semibold" :class="workspaceStateClass">{{ workspaceStateLabel }}</p>
                <p class="mt-1 text-xs text-slate-500">{{ tenant.meta?.slug || "tenant" }}</p>
              </article>
              <article class="ui-context-stat">
                <p class="ui-kicker">{{ t("common.plan") }}</p>
                <p class="mt-1 text-sm font-semibold text-white">{{ tenant.meta?.plan?.name || planModeLabel }}</p>
                <p class="mt-1 text-xs text-slate-500">{{ planModeLabel }}</p>
              </article>
              <article class="ui-context-stat">
                <p class="ui-kicker">{{ t("ownerLayout.publicPreview") }}</p>
                <p class="mt-1 truncate text-sm font-semibold text-white">{{ publicMenuLabel }}</p>
                <RouterLink to="/menu" class="mt-2 inline-flex text-xs text-brand-secondary hover:underline">{{ t("ownerLayout.publicPreview") }}</RouterLink>
              </article>
            </div>

            <div class="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/80 pt-3">
              <div class="flex flex-wrap items-center gap-2">
                <span class="ui-route-badge">{{ currentSectionLabel }}</span>
                <RouterLink to="/owner/onboarding" class="ui-btn-primary ui-touch-target px-4 py-2 text-xs md:hidden">
                  {{ t("ownerLayout.menuBuilder") }}
                </RouterLink>
                <RouterLink to="/menu" class="ui-btn-outline ui-touch-target px-4 py-2 text-xs md:hidden">
                  {{ t("ownerLayout.publicPreview") }}
                </RouterLink>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <span class="ui-chip text-[10px] uppercase tracking-[0.18em] text-slate-300">{{ tenant.meta?.slug || "tenant" }}</span>
                <span class="ui-chip text-[10px] uppercase tracking-[0.18em] text-slate-300">{{ planModeLabel }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>

    <main class="mx-auto w-full max-w-7xl px-4 py-6 pb-28 md:pb-10">
      <RouterView v-slot="{ Component, route: viewRoute }">
        <Transition name="ui-route" mode="out-in">
          <div :key="viewRoute.fullPath" class="ui-route-frame">
            <component :is="Component" />
          </div>
        </Transition>
      </RouterView>
    </main>

    <nav class="ui-bottom-dock md:hidden">
      <div class="ui-bottom-dock-grid grid-cols-5">
        <RouterLink to="/owner" class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]" :data-active="$route.path === '/owner'">
          {{ t("ownerLayout.dashboard") }}
        </RouterLink>
        <RouterLink
          to="/owner/onboarding"
          class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]"
          :data-active="$route.path.startsWith('/owner/onboarding')"
        >
          {{ t("ownerLayout.menuBuilder") }}
        </RouterLink>
        <RouterLink to="/owner/tables" class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]" :data-active="$route.path.startsWith('/owner/tables')">
          {{ t("ownerLayout.tablesQr") }}
        </RouterLink>
        <RouterLink
          to="/owner/reservations"
          class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]"
          :data-active="$route.path.startsWith('/owner/reservations')"
        >
          {{ t("ownerLayout.reservations") }}
        </RouterLink>
        <RouterLink to="/menu" class="ui-pill-nav ui-touch-target justify-center text-center text-[11px]" :data-active="$route.path === '/menu'">
          {{ t("ownerLayout.publicPreview") }}
        </RouterLink>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import LanguageSwitcher from "../components/LanguageSwitcher.vue";
import { useI18n } from "../composables/useI18n";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";

const session = useSessionStore();
const tenant = useTenantStore();
const router = useRouter();
const route = useRoute();
const { t } = useI18n();
const tenantName = computed(() => tenant.meta?.name || t("ownerLayout.fallbackTenantName"));
const tenantLogo = computed(() => String(tenant.meta?.profile?.logo_url || "").trim());
const publicMenuLabel = computed(() => (typeof window === "undefined" ? "/menu" : `${window.location.host}/menu`));
const planModeLabel = computed(() => {
  if (tenant.entitlements?.ordering_mode === "checkout") return t("ownerLayout.checkout");
  if (tenant.entitlements?.ordering_mode === "whatsapp") return t("ownerLayout.whatsapp");
  return t("ownerLayout.browseOnly");
});
const currentSectionLabel = computed(() => {
  if (route.path.startsWith("/owner/onboarding")) return t("ownerLayout.menuBuilder");
  if (route.path.startsWith("/owner/tables")) return t("ownerLayout.tablesQr");
  if (route.path.startsWith("/owner/reservations")) return t("ownerLayout.reservations");
  if (route.path === "/menu") return t("ownerLayout.publicPreview");
  return t("ownerLayout.dashboard");
});
const ownerReadinessLabel = computed(() => {
  const profile = tenant.meta?.profile || {};
  const items = [
    Boolean((profile.phone || "").trim() || (profile.whatsapp || "").trim()),
    Boolean((profile.logo_url || "").trim() || (profile.hero_url || "").trim() || profile.primary_color || profile.secondary_color),
    Boolean(profile.is_menu_published),
  ];
  return `${Math.round((items.filter(Boolean).length / items.length) * 100)}%`;
});
const workspaceStateLabel = computed(() => (tenant.meta?.profile?.is_menu_published ? t("ownerHome.published") : t("ownerHome.draft")));
const workspaceStateClass = computed(() => (tenant.meta?.profile?.is_menu_published ? "text-emerald-300" : "text-amber-300"));
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
