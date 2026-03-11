<template>
  <div class="ui-auth-page flex items-center">
    <div class="ui-auth-card space-y-6">
      <div class="space-y-2 text-center">
        <p class="ui-kicker">{{ t("forgotPassword.kicker") }}</p>
        <h1 class="text-2xl font-semibold text-white">{{ t("forgotPassword.title") }}</h1>
        <p class="text-sm text-slate-300">{{ t("forgotPassword.description") }}</p>
      </div>

      <form class="space-y-4" @submit.prevent="submit">
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("forgotPassword.identifier") }}
          <input
            v-model="identifier"
            autocomplete="username"
            class="ui-input"
            required
          />
        </label>
        <button
          type="submit"
          :disabled="submitting"
          class="ui-btn-primary w-full justify-center disabled:opacity-60"
        >
          {{ submitting ? t("forgotPassword.sending") : t("forgotPassword.sendResetLink") }}
        </button>
        <p v-if="message" class="text-sm text-emerald-400">{{ message }}</p>
        <p v-if="error" class="text-sm text-red-400">{{ error }}</p>
      </form>

      <p class="text-xs text-slate-400">
        {{ t("forgotPassword.backTo") }}
        <RouterLink class="text-[var(--color-secondary)] hover:underline" :to="signinLink">{{ t("forgotPassword.signInLink") }}</RouterLink>
      </p>
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

const signinLink = computed(() => {
  const next = typeof route.query.next === "string" ? route.query.next : "";
  return next ? { name: "signin", query: { next } } : { name: "signin" };
});

const submit = async () => {
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
