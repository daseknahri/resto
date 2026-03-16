<template>
  <div class="ui-shell">
    <header class="ui-header relative z-[2000] overflow-visible md:top-0 md:z-[2000]">
      <div class="mx-auto w-full max-w-7xl px-3 py-1.5 sm:px-4 md:py-3 ui-fade-up">
        <div class="ui-workspace-stage overflow-visible p-2.5 md:p-4 owner-workspace-stage">
          <div class="relative flex items-start justify-between gap-2 md:grid md:grid-cols-[minmax(0,1fr)_minmax(420px,2fr)_auto] md:items-center md:gap-4">
            <div class="flex min-w-0 items-center gap-2.5 md:gap-3">
              <img
                v-if="tenantLogo"
                :src="tenantLogo"
                :alt="`${tenantName} logo`"
                class="h-8 w-8 shrink-0 rounded-xl border border-slate-700/70 object-cover md:h-9 md:w-9"
                loading="lazy"
              />
              <div class="min-w-0">
                <h1 class="ui-display truncate text-base font-semibold text-white sm:text-lg md:text-2xl">{{ tenantName }}</h1>
                <div class="mt-1 flex flex-wrap items-center gap-2">
                  <span class="ui-data-strip hidden sm:inline-flex">{{ tenant.meta?.slug || "tenant" }}</span>
                  <span class="ui-data-strip inline-flex sm:hidden">{{ activeWorkspaceLabel }}</span>
                </div>
              </div>
            </div>

            <div class="owner-main-nav hidden md:grid">
              <RouterLink to="/owner" class="owner-main-nav-item" :data-active="$route.path === '/owner'" active-class="" exact-active-class="">
                <AppIcon name="home" class="owner-nav-icon" />
                <span>{{ t("ownerLayout.dashboard") }}</span>
              </RouterLink>
              <RouterLink
                :to="{ name: 'owner-menu-builder' }"
                class="owner-main-nav-item"
                :data-active="$route.path.startsWith('/owner/menu-builder')"
                active-class=""
                exact-active-class=""
              >
                <AppIcon name="menu" class="owner-nav-icon" />
                <span>{{ t("ownerLayout.menuBuilder") }}</span>
              </RouterLink>
              <RouterLink
                to="/owner/tables"
                class="owner-main-nav-item"
                :data-active="$route.path.startsWith('/owner/tables')"
                active-class=""
                exact-active-class=""
              >
                <AppIcon name="table" class="owner-nav-icon" />
                <span>{{ t("ownerLayout.tablesQr") }}</span>
              </RouterLink>
              <RouterLink
                to="/owner/reservations"
                class="owner-main-nav-item"
                :data-active="$route.path.startsWith('/owner/reservations')"
                active-class=""
                exact-active-class=""
              >
                <AppIcon name="calendar" class="owner-nav-icon" />
                <span>{{ t("ownerLayout.reservations") }}</span>
              </RouterLink>
            </div>

            <div class="flex shrink-0 items-center gap-1.5 sm:gap-2">
              <LanguageSwitcher compact dropdown />
              <div ref="settingsMenuRef" class="relative">
                <button
                  class="owner-settings-trigger"
                  type="button"
                  :aria-expanded="settingsOpen ? 'true' : 'false'"
                  :aria-label="t('common.profile')"
                  @click="toggleSettingsMenu"
                >
                  <AppIcon name="settings" class="owner-settings-icon" />
                </button>
                <transition name="ui-fade">
                  <div v-if="settingsOpen" class="owner-settings-menu">
                    <RouterLink class="owner-settings-item" :to="{ name: 'owner-profile' }" @click="closeSettingsMenu">
                      <AppIcon name="settings" class="owner-settings-item-icon" />
                      <span>{{ t("common.profile") }}</span>
                    </RouterLink>
                    <button class="owner-settings-item owner-settings-item-danger" type="button" @click="handleSignOut">
                      <AppIcon name="logout" class="owner-settings-item-icon" />
                      <span>{{ t("common.signOut") }}</span>
                    </button>
                  </div>
                </transition>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>

    <main class="mx-auto w-full max-w-7xl px-3 py-3 pb-24 sm:px-4 md:py-5 md:pb-10">
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
        <RouterLink
          to="/owner"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[10px] leading-tight"
          :data-active="$route.path === '/owner'"
          active-class=""
          exact-active-class=""
        >
          <AppIcon name="home" class="owner-dock-icon" />
          <span>{{ t("ownerLayout.dashboard") }}</span>
        </RouterLink>
        <RouterLink
          :to="{ name: 'owner-menu-builder' }"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[10px] leading-tight"
          :data-active="$route.path.startsWith('/owner/menu-builder')"
          active-class=""
          exact-active-class=""
        >
          <AppIcon name="menu" class="owner-dock-icon" />
          <span>{{ t("ownerLayout.menuBuilder") }}</span>
        </RouterLink>
        <RouterLink
          to="/owner/tables"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[10px] leading-tight"
          :data-active="$route.path.startsWith('/owner/tables')"
          active-class=""
          exact-active-class=""
        >
          <AppIcon name="table" class="owner-dock-icon" />
          <span>{{ t("ownerLayout.tablesQr") }}</span>
        </RouterLink>
        <RouterLink
          to="/owner/reservations"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[10px] leading-tight"
          :data-active="$route.path.startsWith('/owner/reservations')"
          active-class=""
          exact-active-class=""
        >
          <AppIcon name="calendar" class="owner-dock-icon" />
          <span>{{ t("ownerLayout.reservations") }}</span>
        </RouterLink>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
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
const activeWorkspaceLabel = computed(() => {
  const path = router.currentRoute.value.path || "";
  if (path.startsWith("/owner/menu-builder")) return t("ownerLayout.menuBuilder");
  if (path.startsWith("/owner/profile")) return t("common.profile");
  if (path.startsWith("/owner/tables")) return t("ownerLayout.tablesQr");
  if (path.startsWith("/owner/reservations")) return t("ownerLayout.reservations");
  return t("ownerLayout.dashboard");
});
const settingsOpen = ref(false);
const settingsMenuRef = ref(null);

const signOut = async () => {
  await session.signOut();
  router.push({ name: "home" });
};

const closeSettingsMenu = () => {
  settingsOpen.value = false;
};

const toggleSettingsMenu = () => {
  settingsOpen.value = !settingsOpen.value;
};

const handleSignOut = async () => {
  closeSettingsMenu();
  await signOut();
};

const onDocumentPointerDown = (event) => {
  if (!settingsOpen.value) return;
  const root = settingsMenuRef.value;
  if (root && !root.contains(event.target)) {
    closeSettingsMenu();
  }
};

onMounted(async () => {
  if (!tenant.meta && !tenant.loading) {
    await tenant.fetchMeta();
  }
  if (typeof document !== "undefined") {
    document.addEventListener("pointerdown", onDocumentPointerDown);
  }
});

onBeforeUnmount(() => {
  if (typeof document !== "undefined") {
    document.removeEventListener("pointerdown", onDocumentPointerDown);
  }
});

watch(
  () => router.currentRoute.value.fullPath,
  () => {
    closeSettingsMenu();
  }
);
</script>

<style scoped>
.owner-bottom-dock {
  padding-top: 0.35rem;
  padding-bottom: calc(var(--safe-bottom) + 0.35rem);
}

.owner-dock-link {
  min-height: 2.3rem;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.14rem;
}

.owner-dock-icon {
  width: 0.82rem;
  height: 0.82rem;
}

.owner-settings-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.1rem;
  min-width: 2.1rem;
  border-radius: 9999px;
  border: 1px solid rgba(51, 65, 85, 0.85);
  background: rgba(15, 23, 42, 0.6);
  color: rgb(226, 232, 240);
  padding: 0.35rem;
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

.owner-settings-icon {
  width: 0.85rem;
  height: 0.85rem;
}

.owner-settings-trigger:hover {
  border-color: var(--color-secondary);
  color: var(--color-secondary);
}

.owner-settings-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 0.5rem);
  z-index: 2200;
  min-width: 11rem;
  border-radius: 1rem;
  border: 1px solid rgba(51, 65, 85, 0.85);
  background: linear-gradient(180deg, rgba(2, 6, 23, 0.98), rgba(15, 23, 42, 0.96));
  padding: 0.45rem;
  box-shadow: 0 20px 45px rgba(2, 6, 23, 0.42);
  backdrop-filter: blur(18px);
}

.owner-settings-item {
  width: 100%;
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  border-radius: 0.8rem;
  padding: 0.7rem 0.8rem;
  color: rgb(226, 232, 240);
  font-size: 0.84rem;
  font-weight: 600;
  transition: background 0.2s ease, color 0.2s ease;
}

.owner-settings-item:hover {
  background: rgba(30, 41, 59, 0.92);
  color: var(--color-secondary);
}

.owner-settings-item-danger:hover {
  color: rgb(252, 165, 165);
}

.owner-settings-item-icon {
  width: 0.85rem;
  height: 0.85rem;
  flex-shrink: 0;
}

.owner-workspace-stage {
  z-index: 50;
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
  gap: 0.4rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: rgb(203, 213, 225);
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.owner-nav-icon {
  width: 0.88rem;
  height: 0.88rem;
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

@media (max-width: 640px) {
  .owner-workspace-stage {
    padding: 0.7rem;
  }

  .owner-bottom-dock {
    padding-top: 0.25rem;
    padding-bottom: calc(var(--safe-bottom) + 0.3rem);
  }

  .owner-dock-link {
    min-height: 2.12rem;
    padding-inline: 0.45rem;
    gap: 0.12rem;
    font-size: 0.62rem;
  }

  .owner-dock-icon {
    width: 0.78rem;
    height: 0.78rem;
  }

  .owner-settings-trigger {
    min-height: 1.95rem;
    min-width: 1.95rem;
    padding: 0.28rem;
  }

  .owner-settings-menu {
    min-width: 9.5rem;
    padding: 0.35rem;
    border-radius: 0.9rem;
  }

  .owner-settings-item {
    padding: 0.65rem 0.72rem;
    font-size: 0.8rem;
  }
}
</style>
