<template>
  <div class="ui-auth-page flex items-center">
    <div class="ui-auth-stage">
      <section class="ui-auth-spotlight relative space-y-6">
        <div class="relative space-y-3">
          <span class="ui-chip-strong w-fit">{{ t("signIn.kicker") }}</span>
          <h1 class="ui-display max-w-lg text-4xl font-semibold text-white">{{ t("signIn.title") }}</h1>
          <p class="max-w-md text-sm text-slate-300">{{ t("signIn.description") }}</p>
        </div>

        <div class="relative grid gap-3">
          <article class="ui-orbit-card">
            <p class="ui-kicker">{{ t("common.workspace") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("signIn.identifier") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("signIn.firstTime") }}</p>
          </article>
          <article class="ui-orbit-card">
            <p class="ui-kicker">{{ t("common.reserve") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("signIn.password") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("signIn.forgotPassword") }}</p>
          </article>
        </div>

        <div class="grid gap-3 sm:grid-cols-3">
          <article class="ui-metric-card">
            <p class="text-xs uppercase tracking-[0.2em] text-slate-500">{{ t("common.workspace") }}</p>
            <p class="mt-1 text-xl font-semibold text-white">Owner</p>
          </article>
          <article class="ui-metric-card">
            <p class="text-xs uppercase tracking-[0.2em] text-slate-500">{{ t("common.available") }}</p>
            <p class="mt-1 text-xl font-semibold text-white">24/7</p>
          </article>
          <article class="ui-metric-card">
            <p class="text-xs uppercase tracking-[0.2em] text-slate-500">{{ t("common.refresh") }}</p>
            <p class="mt-1 text-xl font-semibold text-white">{{ t("signIn.kicker") }}</p>
          </article>
        </div>
      </section>

      <div class="ui-auth-card space-y-6">
        <div class="ui-hero-ribbon space-y-3 text-center">
          <p class="ui-kicker">{{ t("signIn.kicker") }}</p>
          <h2 class="ui-display text-2xl font-semibold text-white">{{ t("signIn.title") }}</h2>
          <p class="text-sm text-slate-300">{{ t("signIn.description") }}</p>
        </div>

        <form class="space-y-4" @submit.prevent="submit">
          <label class="space-y-1 text-sm text-slate-200">
            {{ t("signIn.identifier") }}
            <input
              v-model="identifier"
              autocomplete="username"
              class="ui-input"
              required
            />
          </label>
          <label class="space-y-1 text-sm text-slate-200">
            {{ t("signIn.password") }}
            <input
              v-model="password"
              type="password"
              autocomplete="current-password"
              class="ui-input"
              required
            />
          </label>
          <button
            type="submit"
            :disabled="session.loading"
            class="ui-btn-primary w-full justify-center disabled:opacity-60"
          >
            {{ session.loading ? t("signIn.signingIn") : t("common.signIn") }}
          </button>
          <p v-if="error" class="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{{ error }}</p>
        </form>

        <div class="ui-section-band space-y-3 text-xs text-slate-300">
          <p class="font-medium text-slate-100">{{ t("signIn.firstTime") }}</p>
          <p>
            {{ t("signIn.firstTime") }}
            <RouterLink :to="activateLink" class="text-[var(--color-secondary)] hover:underline">{{ t("signIn.activationLink") }}</RouterLink>
          </p>
          <p>
            {{ t("signIn.forgotPassword") }}
            <RouterLink :to="forgotPasswordLink" class="text-[var(--color-secondary)] hover:underline">{{ t("signIn.resetHere") }}</RouterLink>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { useSessionStore } from "../stores/session";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const { t } = useI18n();

const identifier = ref("");
const password = ref("");
const error = ref("");

const activateLink = computed(() => {
  const next = typeof route.query.next === "string" ? route.query.next : "";
  return next ? { name: "activate", query: { next } } : { name: "activate" };
});

const forgotPasswordLink = computed(() => {
  const next = typeof route.query.next === "string" ? route.query.next : "";
  return next ? { name: "forgot-password", query: { next } } : { name: "forgot-password" };
});

const fallbackRoute = () => {
  if (session.isPlatformAdmin) return { name: "admin-console" };
  if (session.canEditTenantMenu) return { name: "owner-home" };
  return { name: "home" };
};

const submit = async () => {
  error.value = "";
  try {
    await session.signIn(identifier.value, password.value);
    const next = typeof route.query.next === "string" ? route.query.next : "";
    if (next) {
      router.push(next);
    } else {
      router.push(fallbackRoute());
    }
  } catch {
    error.value = session.error || t("signIn.failed");
  }
};
</script>
