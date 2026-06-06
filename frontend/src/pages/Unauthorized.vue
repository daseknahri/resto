<template>
  <main
    class="ui-auth-page flex items-center"
    aria-labelledby="unauthorized-heading"
  >
    <div class="ui-auth-stage">
      <!-- ── Left spotlight column (desktop only) ───────────────── -->
      <section class="ui-auth-spotlight relative space-y-6" aria-hidden="true">
        <div class="ui-reveal relative space-y-3" style="--ui-delay: 0ms">
          <span class="ui-chip-strong w-fit">{{ t("unauthorized.kicker") }}</span>
          <p class="ui-display max-w-lg text-4xl font-semibold text-white">
            {{ t("unauthorized.title") }}
          </p>
          <p class="max-w-md text-sm text-slate-300">{{ t("unauthorized.noPermission") }}</p>
        </div>

        <div class="ui-reveal grid gap-3 sm:grid-cols-2" style="--ui-delay: 60ms">
          <article class="ui-orbit-card">
            <p class="ui-kicker">{{ t("unauthorized.kicker") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("unauthorized.title") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("unauthorized.adminRequired") }}</p>
          </article>
          <article class="ui-orbit-card">
            <p class="ui-kicker">{{ t("common.signIn") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("unauthorized.switchAccount") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("unauthorized.editorRequired") }}</p>
          </article>
        </div>
      </section>

      <!-- ── Auth card ──────────────────────────────────────────── -->
      <div class="ui-auth-card ui-reveal max-w-lg space-y-6" :style="{ '--ui-delay': '80ms' }">
        <!-- Icon + heading -->
        <div class="ui-reveal ui-hero-ribbon space-y-3 text-center" style="--ui-delay: 0ms">
          <!-- Lock icon (decorative) -->
          <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-[var(--color-secondary)]/20 bg-[var(--color-secondary)]/10" aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="h-7 w-7 text-[var(--color-secondary)]"
            >
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>

          <div class="space-y-1">
            <p class="ui-kicker">{{ t("unauthorized.kicker") }}</p>
            <h1
              id="unauthorized-heading"
              class="ui-display text-2xl font-semibold text-white"
            >
              {{ t("unauthorized.title") }}
            </h1>
            <p aria-live="polite" class="text-sm text-slate-300">{{ message }}</p>
          </div>
        </div>

        <!-- Actions -->
        <nav
          class="ui-reveal grid gap-3 sm:grid-cols-2"
          style="--ui-delay: 60ms"
          :aria-label="t('unauthorized.navLabel')"
        >
          <RouterLink
            v-if="showSignIn"
            :to="signInLink"
            class="ui-btn-primary ui-press min-w-[10rem] justify-center ui-touch-target"
          >
            {{ t("common.signIn") }}
          </RouterLink>
          <RouterLink
            v-if="showAdmin"
            to="/admin-console"
            class="ui-btn-outline ui-press min-w-[10rem] justify-center ui-touch-target"
          >
            {{ t("unauthorized.goToAdminConsole") }}
          </RouterLink>
          <RouterLink
            v-if="showOnboarding"
            to="/owner/onboarding"
            class="ui-btn-outline ui-press min-w-[10rem] justify-center ui-touch-target"
          >
            {{ t("unauthorized.goToOnboarding") }}
          </RouterLink>
          <button
            v-if="session.isAuthenticated"
            class="ui-btn-outline ui-press min-w-[10rem] justify-center ui-touch-target"
            @click="switchAccount"
          >
            {{ t("unauthorized.switchAccount") }}
          </button>
          <RouterLink
            to="/"
            class="ui-btn-outline ui-press min-w-[10rem] justify-center ui-touch-target"
          >
            {{ t("unauthorized.backToHome") }}
          </RouterLink>
        </nav>
      </div>
    </div>
  </main>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { useSessionStore } from "../stores/session";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const { t } = useI18n();

const reason = computed(() => (typeof route.query.reason === "string" ? route.query.reason : ""));
const next = computed(() => (typeof route.query.next === "string" ? route.query.next : ""));

const message = computed(() => {
  if (reason.value === "admin") return t("unauthorized.adminRequired");
  if (reason.value === "editor") return t("unauthorized.editorRequired");
  return t("unauthorized.noPermission");
});

const signInLink = computed(() => {
  return next.value ? { name: "signin", query: { next: next.value } } : { name: "signin" };
});

const showSignIn = computed(() => !session.isAuthenticated);
const showAdmin = computed(() => reason.value === "editor" && session.isPlatformAdmin);
const showOnboarding = computed(() => reason.value === "admin" && session.canEditTenantMenu);

const switchAccount = async () => {
  await session.signOut();
  router.push(signInLink.value);
};
</script>
