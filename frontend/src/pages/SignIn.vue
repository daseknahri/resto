<template>
  <div class="ui-auth-page flex items-center">
    <div class="ui-auth-card space-y-6">
      <div class="space-y-2 text-center">
        <p class="ui-kicker">{{ t("signIn.kicker") }}</p>
        <h1 class="ui-display text-2xl font-semibold text-white">{{ t("signIn.title") }}</h1>
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
        <p v-if="error" class="text-sm text-red-400">{{ error }}</p>
      </form>

      <div class="space-y-2 rounded-2xl border border-slate-700/70 bg-slate-950/50 px-4 py-3 text-xs text-slate-300">
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
