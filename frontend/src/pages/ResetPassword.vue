<template>
  <div class="ui-auth-page flex items-center">
    <div class="ui-auth-card space-y-6">
      <div class="space-y-2 text-center">
        <p class="ui-kicker">{{ t("resetPassword.kicker") }}</p>
        <h1 class="text-2xl font-semibold text-white">{{ t("resetPassword.title") }}</h1>
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
        <p v-if="message" class="text-sm text-emerald-400">{{ message }}</p>
        <p v-if="error" class="text-sm text-red-400">{{ error }}</p>
      </form>

      <p class="text-xs text-slate-400">
        {{ t("resetPassword.continueTo") }}
        <RouterLink class="text-[var(--color-secondary)] hover:underline" :to="signinLink">{{ t("resetPassword.signInLink") }}</RouterLink>
      </p>
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
