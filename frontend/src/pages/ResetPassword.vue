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

        <form class="space-y-4" novalidate @submit.prevent="submit">
          <label class="space-y-1 text-sm text-slate-200">
            {{ t("resetPassword.token") }}
            <input
              v-model="token"
              type="text"
              autocomplete="one-time-code"
              class="ui-input"
              :class="fieldErrors.token ? 'border-red-400' : ''"
              :aria-invalid="fieldErrors.token ? 'true' : undefined"
              aria-describedby="reset-token-error"
              aria-required="true"
              @input="fieldErrors.token = ''"
            />
            <p v-if="fieldErrors.token" id="reset-token-error" class="text-xs text-red-300">{{ fieldErrors.token }}</p>
          </label>
          <label class="space-y-1 text-sm text-slate-200">
            {{ t("resetPassword.newPassword") }}
            <input
              v-model="password"
              type="password"
              autocomplete="new-password"
              class="ui-input"
              :class="fieldErrors.password ? 'border-red-400' : ''"
              :aria-invalid="fieldErrors.password ? 'true' : undefined"
              aria-describedby="reset-password-error"
              aria-required="true"
              @input="fieldErrors.password = ''"
            />
            <p v-if="fieldErrors.password" id="reset-password-error" class="text-xs text-red-300">{{ fieldErrors.password }}</p>
          </label>
          <button
            type="submit"
            :disabled="submitting"
            class="ui-btn-primary w-full justify-center disabled:opacity-60"
          >
            {{ submitting ? t("resetPassword.resetting") : t("resetPassword.reset") }}
          </button>
          <p v-if="message" role="status" class="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">{{ message }}</p>
          <div v-if="error" role="alert" class="flex items-start gap-2 rounded-2xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
            <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm text-red-300">{{ error }}</p>
          </div>
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
import { computed, onMounted, reactive, ref } from "vue";
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
const fieldErrors = reactive({ token: "", password: "" });

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
  fieldErrors.token = "";
  fieldErrors.password = "";
  if (!token.value.trim()) {
    fieldErrors.token = t("resetPassword.tokenRequired");
    return;
  }
  if (password.value.length < 8) {
    fieldErrors.password = t("resetPassword.passwordTooShort");
    return;
  }
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
