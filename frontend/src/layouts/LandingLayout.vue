<template>
  <div class="ui-shell">
    <div class="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div class="absolute -left-32 -top-20 h-72 w-72 rounded-full bg-amber-400/10 blur-3xl"></div>
      <div class="absolute -right-20 top-10 h-72 w-72 rounded-full bg-teal-400/10 blur-3xl"></div>
    </div>

    <header class="ui-header ui-fade-up relative z-[2000] overflow-visible">
      <div class="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <RouterLink to="/" class="flex min-w-0 items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-2xl text-sm font-bold text-slate-950 shadow-lg shadow-black/30" :style="logoStyle">
            RM
          </div>
          <div class="min-w-0">
            <p class="truncate text-xs uppercase tracking-[0.24em] text-slate-400">{{ t("landingLayout.kicker") }}</p>
            <p class="ui-display truncate text-base font-semibold text-slate-100">{{ t("landingLayout.title") }}</p>
          </div>
        </RouterLink>

        <nav class="hidden items-center gap-2 rounded-full border border-slate-800/80 bg-slate-950/65 px-2 py-1.5 shadow-lg shadow-black/20 lg:flex">
          <RouterLink class="ui-pill-nav whitespace-nowrap" to="/" :data-active="$route.path === '/'" active-class="" exact-active-class="">{{ t("common.landing") }}</RouterLink>
          <RouterLink class="ui-pill-nav whitespace-nowrap" to="/menu" :data-active="$route.path === '/menu'" active-class="" exact-active-class="">{{ t("common.liveDemo") }}</RouterLink>
          <RouterLink class="ui-pill-nav whitespace-nowrap" to="/get-started" :data-active="$route.path === '/get-started'" active-class="" exact-active-class="">{{ t("common.getStarted") }}</RouterLink>
          <RouterLink class="ui-pill-nav whitespace-nowrap" to="/contact" :data-active="$route.path === '/contact'" active-class="" exact-active-class="">{{ t("common.contact") }}</RouterLink>
        </nav>

        <div class="flex items-center gap-2">
          <div class="hidden items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-[11px] font-medium text-emerald-100 xl:inline-flex">
            <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
            {{ t("home.heroLive") }}
          </div>
          <LanguageSwitcher dropdown />
          <RouterLink v-if="session.isPlatformAdmin" to="/admin-console" class="ui-btn-outline ui-touch-target hidden text-sm md:inline-flex">{{ t("common.admin") }}</RouterLink>
          <RouterLink
            v-if="session.canEditTenantMenu"
            to="/owner"
            class="ui-btn-outline ui-touch-target inline-flex text-[11px] sm:text-sm"
          >
            {{ t("common.workspace") }}
          </RouterLink>
          <RouterLink v-if="!session.isAuthenticated" to="/signin" class="ui-btn-primary ui-touch-target text-[11px] sm:text-sm px-3 py-1.5 sm:px-5 sm:py-2.5">{{ t("common.signIn") }}</RouterLink>
          <button v-else class="ui-btn-outline ui-touch-target text-[11px] sm:text-sm px-3 py-1.5 sm:px-5 sm:py-2.5" @click="signOut">
            {{ t("common.signOut") }}
          </button>
        </div>
      </div>
      <div class="ui-divider"></div>
    </header>

    <nav class="ui-bottom-dock lg:hidden">
      <div class="ui-bottom-dock-grid grid-cols-4">
        <RouterLink class="ui-pill-nav justify-center px-2 py-1 text-center text-[10px] leading-tight" to="/" :data-active="$route.path === '/'" active-class="" exact-active-class="">
          {{ t("common.landing") }}
        </RouterLink>
        <RouterLink class="ui-pill-nav justify-center px-2 py-1 text-center text-[10px] leading-tight" to="/menu" :data-active="$route.path === '/menu'" active-class="" exact-active-class="">
          {{ t("common.demo") }}
        </RouterLink>
        <RouterLink class="ui-pill-nav justify-center px-2 py-1 text-center text-[10px] leading-tight" to="/get-started" :data-active="$route.path === '/get-started'" active-class="" exact-active-class="">
          {{ t("common.getStarted") }}
        </RouterLink>
        <RouterLink class="ui-pill-nav justify-center px-2 py-1 text-center text-[10px] leading-tight" to="/contact" :data-active="$route.path === '/contact'" active-class="" exact-active-class="">
          {{ t("common.contact") }}
        </RouterLink>
      </div>
    </nav>

    <main class="mx-auto w-full max-w-6xl ui-fade-up">
      <RouterView v-slot="{ Component, route: viewRoute }">
        <Transition name="ui-route" mode="out-in">
          <div :key="viewRoute.fullPath" class="ui-route-frame">
            <component :is="Component" />
          </div>
        </Transition>
      </RouterView>
    </main>

    <footer class="ui-footer">
      <div class="mx-auto grid w-full max-w-6xl gap-4 rounded-[1.8rem] border border-slate-800/80 bg-slate-950/55 p-4 shadow-xl shadow-black/25 md:grid-cols-[minmax(0,1.1fr),auto,auto] md:items-start">
        <div class="space-y-2">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-2xl text-sm font-bold text-slate-950 shadow-lg shadow-black/30" :style="logoStyle">
              RM
            </div>
            <div>
              <p class="ui-kicker">{{ t("landingLayout.kicker") }}</p>
              <p class="ui-display text-lg font-semibold text-white">{{ t("landingLayout.footerTitle") }}</p>
            </div>
          </div>
          <p class="max-w-xl text-sm text-slate-400">
            {{ t("home.heroSubtitle") }}
          </p>
          <div class="flex flex-wrap gap-2">
            <span class="ui-chip">{{ t("home.stats.launchTimeValue") }}</span>
            <span class="ui-chip">{{ t("home.stats.interfacesValue") }}</span>
            <span class="ui-chip">{{ supportEmail }}</span>
          </div>
        </div>

        <div class="space-y-3">
          <p class="ui-kicker">{{ t("common.getStarted") }}</p>
          <div class="flex flex-col gap-2 text-sm">
            <RouterLink class="ui-top-link" to="/get-started">{{ t("common.getStarted") }}</RouterLink>
            <RouterLink class="ui-top-link" to="/menu">{{ t("common.liveDemo") }}</RouterLink>
            <RouterLink class="ui-top-link" to="/contact">{{ t("common.contact") }}</RouterLink>
          </div>
        </div>

        <div class="space-y-3">
          <p class="ui-kicker">{{ t("common.status") }}</p>
          <div class="flex flex-col gap-2 text-sm">
            <RouterLink class="ui-top-link" to="/privacy">{{ t("common.privacy") }}</RouterLink>
            <RouterLink class="ui-top-link" to="/terms">{{ t("common.terms") }}</RouterLink>
            <span class="text-slate-500">&copy; {{ year }}</span>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import LanguageSwitcher from "../components/LanguageSwitcher.vue";
import { useI18n } from "../composables/useI18n";
import { useSessionStore } from "../stores/session";

const router = useRouter();
const session = useSessionStore();
const { t } = useI18n();
const year = new Date().getFullYear();
const supportEmail = import.meta.env.VITE_CONTACT_EMAIL || "contact@kepoli.com";

const logoStyle = computed(() => ({
  background: "linear-gradient(135deg, var(--color-primary), var(--color-secondary))",
}));

const signOut = async () => {
  await session.signOut();
  router.push({ name: "home" });
};
</script>
