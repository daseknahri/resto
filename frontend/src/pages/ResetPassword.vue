<template>
  <div class="ui-auth-page flex items-center">
    <div class="ui-auth-stage">
      <section class="ui-auth-spotlight relative space-y-6">
        <div class="relative space-y-3">
          <span class="ui-chip-strong w-fit">{{ t("resetPassword.kicker") }}</span>
          <h1 class="ui-display max-w-lg text-4xl font-semibold text-white">{{ t("resetPassword.title") }}</h1>
          <p class="max-w-md text-sm text-slate-300">{{ t("resetPassword.description") }}</p>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <article class="ui-orbit-card">
            <p class="ui-kicker">{{ t("resetPassword.token") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("resetPassword.title") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("resetPassword.description") }}</p>
          </article>
          <article class="ui-orbit-card">
            <p class="ui-kicker">{{ t("resetPassword.newPassword") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("resetPassword.reset") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("resetPassword.continueTo") }}</p>
          </article>
        </div>
      </section>

      <div class="ui-auth-card space-y-6">
        <div class="ui-hero-ribbon space-y-3 text-center">
          <p class="ui-kicker">{{ t("resetPassword.kicker") }}</p>
          <h2 class="ui-display text-2xl font-semibold text-white">{{ t("resetPassword.title") }}</h2>
          <p class="text-sm text-slate-300">{{ t("resetPassword.description") }}</p>
        </div>

        <form class="space-y-4" @submit.prevent="submit">
          <label class="space-y-1 text-sm text-slate-200">
            {{ t("resetPassword.token") }}
            <input
              v-model="token"
              class="ui-input"
              required
            />
          </label>
          <label class="space-y-1 text-sm text-slate-200">
            {{ t("resetPassword.newPassword") }}
            <input
              v-model="password"
              type="password"
              minlength="8"
              autocomplete="new-password"
              class="ui-input"
              required
            />
          </label>
          <button
            type="submit"
            :disabled="submitting"
            class="ui-btn-primary w-full justify-center disabled:opacity-60"
          >
            {{ submitting ? t("resetPassword.resetting") : t("resetPassword.reset") }}
          </button>
          <p v-if="message" class="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">{{ message }}</p>
          <p v-if="error" class="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{{ error }}</p>
        </form>

        <div class="ui-section-band text-xs text-slate-300">
          {{ t("resetPassword.continueTo") }}
          <RouterLink class="ml-1 text-[var(--color-secondary)] hover:underline" :to="signinLink">{{ t("resetPassword.signInLink") }}</RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";

const route = useRoute();
const { t } = useI18n();
const token = ref("");
const password = ref("");
const submitting = ref(false);
const message = ref("");
const error = ref("");

const signinLink = computed(() => {
  const next = typeof route.query.next === "string" ? route.query.next : "";
  return next ? { name: "signin", query: { next } } : { name: "signin" };
});

onMounted(() => {
  if (typeof route.query.token === "string" && route.query.token.trim()) {
    token.value = route.query.token.trim();
  }
});

const submit = async () => {
  submitting.value = true;
  message.value = "";
  error.value = "";
  try {
    const { data } = await api.post("/password-reset/confirm/", { token: token.value, password: password.value });
    message.value = data?.detail || t("resetPassword.successFallback");
  } catch (err) {
    error.value = err?.response?.data?.detail || t("resetPassword.failed");
  } finally {
    submitting.value = false;
  }
};
</script>
