<template>
  <div class="ui-auth-page flex items-center">
    <div class="ui-auth-stage">
      <section class="ui-auth-spotlight relative space-y-6">
        <div class="relative space-y-3">
          <span class="ui-chip-strong w-fit">{{ t("forgotPassword.kicker") }}</span>
          <h1 class="ui-display max-w-lg text-4xl font-semibold text-white">{{ t("forgotPassword.title") }}</h1>
          <p class="max-w-md text-sm text-slate-300">{{ t("forgotPassword.description") }}</p>
        </div>

        <div class="grid gap-3">
          <article class="ui-orbit-card ui-reveal" :style="{ '--ui-delay': '0ms' }">
            <p class="ui-kicker">{{ t("common.signIn") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("forgotPassword.identifier") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("forgotPassword.description") }}</p>
          </article>
          <article class="ui-orbit-card ui-reveal" :style="{ '--ui-delay': '56ms' }">
            <p class="ui-kicker">{{ t("common.workspace") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("forgotPassword.sendResetLink") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("forgotPassword.backTo") }}</p>
          </article>
        </div>
      </section>

      <div class="ui-auth-card ui-reveal space-y-6" :style="{ '--ui-delay': '80ms' }">
        <div class="ui-hero-ribbon space-y-3 text-center">
          <p class="ui-kicker">{{ t("forgotPassword.kicker") }}</p>
          <h2 class="ui-display text-2xl font-semibold text-white">{{ t("forgotPassword.title") }}</h2>
          <p class="text-sm text-slate-300">{{ t("forgotPassword.description") }}</p>
        </div>

        <form class="space-y-4" novalidate @submit.prevent="submit">
          <label class="block space-y-1 text-sm text-slate-200">
            {{ t("forgotPassword.identifier") }}
            <input
              v-model="identifier"
              type="text"
              autocomplete="username"
              class="ui-input"
              :class="identifierError ? 'border-red-400' : ''"
              :aria-invalid="identifierError ? 'true' : undefined"
              aria-describedby="forgot-identifier-error"
              aria-required="true"
              @input="identifierError = ''"
            />
            <p v-if="identifierError" id="forgot-identifier-error" class="text-xs text-red-300" role="alert">{{ identifierError }}</p>
          </label>
          <button
            type="submit"
            :disabled="submitting"
            class="ui-btn-primary ui-press w-full justify-center disabled:opacity-60"
          >
            {{ submitting ? t("forgotPassword.sending") : t("forgotPassword.sendResetLink") }}
          </button>
          <div v-if="message" role="status" class="flex items-start gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3">
            <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm text-emerald-200">{{ message }}</p>
          </div>
          <div v-if="error" role="alert" class="flex items-start gap-2 rounded-2xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
            <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm text-red-300">{{ error }}</p>
          </div>
        </form>

        <div class="ui-section-band flex flex-wrap items-baseline gap-x-1 text-xs text-slate-300">
          <span>{{ t("forgotPassword.backTo") }}</span>
          <RouterLink class="text-[var(--color-secondary)] hover:underline" :to="signinLink">{{ t("forgotPassword.signInLink") }}</RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";

const route = useRoute();
const { t } = useI18n();
const identifier = ref("");
const submitting = ref(false);
const message = ref("");
const error = ref("");
const identifierError = ref("");

const signinLink = computed(() => {
  const next = typeof route.query.next === "string" ? route.query.next : "";
  return next ? { name: "signin", query: { next } } : { name: "signin" };
});

const submit = async () => {
  identifierError.value = "";
  if (!identifier.value.trim()) {
    identifierError.value = t("forgotPassword.identifierRequired");
    return;
  }
  submitting.value = true;
  message.value = "";
  error.value = "";
  try {
    const { data } = await api.post("/password-reset/request/", { identifier: identifier.value });
    message.value = data?.detail || t("forgotPassword.successFallback");
    if (data?.debug_reset_url) {
      message.value += ` (${t("forgotPassword.debugUrlPrefix")}: ${data.debug_reset_url})`;
    }
  } catch (err) {
    error.value = err?.response?.data?.detail || t("forgotPassword.requestFailed");
  } finally {
    submitting.value = false;
  }
};
</script>
