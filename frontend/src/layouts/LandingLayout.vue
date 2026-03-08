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
            <p class="truncate text-xs uppercase tracking-[0.24em] text-slate-400">Resto Menu</p>
            <p class="ui-display truncate text-base font-semibold text-slate-100">Restaurant SaaS</p>
          </div>
        </RouterLink>

        <nav class="hidden items-center gap-4 lg:flex">
          <RouterLink class="ui-top-link" to="/">Landing</RouterLink>
          <RouterLink class="ui-top-link" to="/menu">Live demo</RouterLink>
          <RouterLink class="ui-top-link" to="/get-started">Get started</RouterLink>
          <RouterLink class="ui-top-link" to="/contact">Contact</RouterLink>
        </nav>

        <div class="flex items-center gap-2">
          <RouterLink v-if="session.isPlatformAdmin" to="/admin-console" class="ui-btn-outline ui-touch-target hidden text-sm md:inline-flex">Admin</RouterLink>
          <RouterLink v-if="session.canEditTenantMenu" to="/owner" class="ui-btn-outline ui-touch-target hidden text-sm md:inline-flex">Workspace</RouterLink>
          <RouterLink v-if="!session.isAuthenticated" to="/signin" class="ui-btn-primary ui-touch-target text-sm">Sign in</RouterLink>
          <button v-else class="ui-btn-outline ui-touch-target text-sm" @click="signOut">Sign out</button>
        </div>
      </div>
      <div class="ui-divider"></div>
      <div class="mx-auto flex w-full max-w-6xl items-center gap-2 overflow-x-auto px-4 py-2 text-xs lg:hidden ui-safe-bottom">
        <RouterLink class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs" to="/">Landing</RouterLink>
        <RouterLink class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs" to="/menu">Demo</RouterLink>
        <RouterLink class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs" to="/get-started">Lead form</RouterLink>
        <RouterLink class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs" to="/contact">Contact</RouterLink>
        <RouterLink v-if="session.isPlatformAdmin" class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs" to="/admin-console">Admin</RouterLink>
      </div>
    </header>

    <main class="mx-auto w-full max-w-6xl ui-fade-up">
      <RouterView />
    </main>

    <footer class="ui-footer">
      <div class="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3">
        <p>&copy; {{ year }} Resto Menu SaaS</p>
        <div class="flex items-center gap-4">
          <RouterLink class="ui-top-link" to="/privacy">Privacy</RouterLink>
          <RouterLink class="ui-top-link" to="/terms">Terms</RouterLink>
          <RouterLink class="ui-top-link" to="/contact">Contact</RouterLink>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useSessionStore } from "../stores/session";

const router = useRouter();
const session = useSessionStore();
const year = new Date().getFullYear();

const logoStyle = computed(() => ({
  background: "linear-gradient(135deg, var(--color-primary), var(--color-secondary))",
}));

const signOut = async () => {
  await session.signOut();
  router.push({ name: "home" });
};
</script>
