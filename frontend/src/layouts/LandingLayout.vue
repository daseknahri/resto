<template>
  <div class="ui-shell">
    <div class="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div class="absolute -left-32 -top-20 h-72 w-72 rounded-full bg-amber-400/10 blur-3xl"></div>
      <div class="absolute -right-20 top-10 h-72 w-72 rounded-full bg-teal-400/10 blur-3xl"></div>
    </div>

    <header class="ui-header ui-fade-up">
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

        <nav class="hidden items-center gap-4 lg:flex">
          <RouterLink class="ui-top-link" to="/">{{ t("common.landing") }}</RouterLink>
          <RouterLink class="ui-top-link" to="/menu">{{ t("common.liveDemo") }}</RouterLink>
          <RouterLink class="ui-top-link" to="/get-started">{{ t("common.getStarted") }}</RouterLink>
          <RouterLink class="ui-top-link" to="/contact">{{ t("common.contact") }}</RouterLink>
        </nav>

        <div class="flex items-center gap-2">
          <LanguageSwitcher />
          <RouterLink v-if="session.isPlatformAdmin" to="/admin-console" class="ui-btn-outline ui-touch-target hidden text-sm md:inline-flex">{{ t("common.admin") }}</RouterLink>
          <RouterLink v-if="session.canEditTenantMenu" to="/owner" class="ui-btn-outline ui-touch-target hidden text-sm md:inline-flex">{{ t("common.workspace") }}</RouterLink>
          <RouterLink v-if="!session.isAuthenticated" to="/signin" class="ui-btn-primary ui-touch-target text-sm">{{ t("common.signIn") }}</RouterLink>
          <button v-else class="ui-btn-outline ui-touch-target text-sm" @click="signOut">{{ t("common.signOut") }}</button>
        </div>
      </div>
      <div class="ui-divider"></div>
      <div class="mx-auto flex w-full max-w-6xl items-center gap-2 overflow-x-auto px-4 py-2 text-xs lg:hidden ui-safe-bottom">
        <RouterLink class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs" to="/">{{ t("common.landing") }}</RouterLink>
        <RouterLink class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs" to="/menu">{{ t("common.demo") }}</RouterLink>
        <RouterLink class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs" to="/get-started">{{ t("common.getStarted") }}</RouterLink>
        <RouterLink class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs" to="/contact">{{ t("common.contact") }}</RouterLink>
        <RouterLink v-if="session.isPlatformAdmin" class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs" to="/admin-console">{{ t("common.admin") }}</RouterLink>
      </div>
    </header>

    <main class="mx-auto w-full max-w-6xl ui-fade-up">
      <RouterView />
    </main>

    <footer class="ui-footer">
      <div class="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3">
        <p>&copy; {{ year }} {{ t("landingLayout.footerTitle") }}</p>
        <div class="flex items-center gap-4">
          <RouterLink class="ui-top-link" to="/privacy">{{ t("common.privacy") }}</RouterLink>
          <RouterLink class="ui-top-link" to="/terms">{{ t("common.terms") }}</RouterLink>
          <RouterLink class="ui-top-link" to="/contact">{{ t("common.contact") }}</RouterLink>
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

const logoStyle = computed(() => ({
  background: "linear-gradient(135deg, var(--color-primary), var(--color-secondary))",
}));

const signOut = async () => {
  await session.signOut();
  router.push({ name: "home" });
};
</script>
