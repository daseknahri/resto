<template>
  <div class="ui-shell">
    <header class="ui-header static md:sticky md:top-0 md:z-30">
      <div class="mx-auto w-full max-w-7xl px-4 py-2 md:py-3 ui-fade-up">
        <div class="ui-workspace-stage p-3 md:p-4">
          <div class="relative flex items-center justify-between gap-2 md:grid md:grid-cols-[minmax(0,1fr)_minmax(420px,2fr)_auto] md:items-center md:gap-4">
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
                </div>
              </div>
            </div>

            <div class="owner-main-nav hidden md:grid">
              <RouterLink to="/owner" class="owner-main-nav-item" :data-active="$route.path === '/owner'">
                {{ t("ownerLayout.dashboard") }}
              </RouterLink>
              <RouterLink to="/owner/onboarding" class="owner-main-nav-item" :data-active="$route.path.startsWith('/owner/onboarding')">
                {{ t("ownerLayout.menuBuilder") }}
              </RouterLink>
              <RouterLink to="/owner/tables" class="owner-main-nav-item" :data-active="$route.path.startsWith('/owner/tables')">
                {{ t("ownerLayout.tablesQr") }}
              </RouterLink>
              <RouterLink to="/owner/reservations" class="owner-main-nav-item" :data-active="$route.path.startsWith('/owner/reservations')">
                {{ t("ownerLayout.reservations") }}
              </RouterLink>
            </div>

            <div class="flex shrink-0 items-center gap-1.5 sm:gap-2">
              <LanguageSwitcher compact dropdown />
              <button class="owner-signout-btn" @click="signOut">{{ t("common.signOut") }}</button>
            </div>
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
          to="/owner/tables"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[11px] leading-tight"
          :data-active="$route.path.startsWith('/owner/tables')"
        >
          {{ t("ownerLayout.tablesQr") }}
        </RouterLink>
        <RouterLink
          to="/owner/reservations"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[11px] leading-tight"
          :data-active="$route.path.startsWith('/owner/reservations')"
        >
          {{ t("ownerLayout.reservations") }}
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

.owner-signout-btn {
  min-height: 2.1rem;
  border-radius: 9999px;
  border: 1px solid rgba(51, 65, 85, 0.85);
  background: rgba(15, 23, 42, 0.6);
  color: rgb(226, 232, 240);
  padding: 0.35rem 0.7rem;
  font-size: 0.75rem;
  font-weight: 600;
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

.owner-signout-btn:hover {
  border-color: var(--color-secondary);
  color: var(--color-secondary);
}

.owner-main-nav {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.5rem;
  border: 1px solid rgba(51, 65, 85, 0.7);
  border-radius: 1rem;
  background: linear-gradient(135deg, rgba(2, 6, 23, 0.86), rgba(3, 15, 35, 0.78));
  padding: 0.4rem;
  box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.15);
}

.owner-main-nav-item {
  min-height: 2.6rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(51, 65, 85, 0.35);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.82rem;
  font-weight: 600;
  color: rgb(203, 213, 225);
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.owner-main-nav-item:hover {
  border-color: rgba(245, 158, 11, 0.55);
  background: rgba(15, 23, 42, 0.72);
  color: rgb(245, 158, 11);
}

.owner-main-nav-item[data-active="true"] {
  border-color: rgba(245, 158, 11, 0.85);
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(245, 158, 11, 0.08));
  color: rgb(245, 158, 11);
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.12) inset;
}
</style>
