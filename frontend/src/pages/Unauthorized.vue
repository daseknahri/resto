<template>
  <div class="ui-auth-page flex items-center">
    <div class="ui-auth-stage">
      <section class="ui-auth-spotlight relative space-y-6">
        <div class="relative space-y-3">
          <span class="ui-chip-strong w-fit">{{ t("unauthorized.kicker") }}</span>
          <h1 class="ui-display max-w-lg text-4xl font-semibold text-white">{{ t("unauthorized.title") }}</h1>
          <p class="max-w-md text-sm text-slate-300">{{ message }}</p>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <article class="ui-orbit-card">
            <p class="ui-kicker">{{ t("common.workspace") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("unauthorized.title") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ message }}</p>
          </article>
          <article class="ui-orbit-card">
            <p class="ui-kicker">{{ t("common.signIn") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("unauthorized.backToHome") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("unauthorized.kicker") }}</p>
          </article>
        </div>
      </section>

      <div class="ui-auth-card max-w-lg space-y-6">
        <div class="ui-hero-ribbon space-y-3 text-center">
          <p class="ui-kicker">{{ t("unauthorized.kicker") }}</p>
          <h2 class="ui-display text-2xl font-semibold text-white">{{ t("unauthorized.title") }}</h2>
          <p class="text-sm text-slate-300">{{ message }}</p>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <RouterLink
            v-if="showSignIn"
            :to="signInLink"
            class="ui-btn-primary justify-center"
          >
            {{ t("common.signIn") }}
          </RouterLink>
          <RouterLink
            v-if="showAdmin"
            to="/admin-console"
            class="ui-btn-primary justify-center"
          >
            {{ t("unauthorized.goToAdminConsole") }}
          </RouterLink>
          <RouterLink
            v-if="showOnboarding"
            to="/owner/onboarding"
            class="ui-btn-primary justify-center"
          >
            {{ t("unauthorized.goToOnboarding") }}
          </RouterLink>
          <button
            v-if="session.isAuthenticated"
            class="ui-btn-outline justify-center"
            @click="switchAccount"
          >
            {{ t("unauthorized.switchAccount") }}
          </button>
          <RouterLink
            to="/"
            class="ui-btn-outline justify-center"
          >
            {{ t("unauthorized.backToHome") }}
          </RouterLink>
        </div>
      </div>
    </div>
  </div>
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
