<template>
  <div class="ui-auth-page flex items-center">
    <div class="ui-auth-card space-y-6">
      <div class="space-y-2 text-center">
        <p class="ui-kicker">{{ t("activateAccount.kicker") }}</p>
        <h1 class="ui-display text-2xl font-semibold text-white">{{ t("activateAccount.title") }}</h1>
        <p class="text-sm text-slate-300">{{ t("activateAccount.description") }}</p>
      </div>

      <form class="space-y-4" novalidate @submit.prevent="submit">
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("activateAccount.token") }}
          <input
            v-model="token"
            type="text"
            autocomplete="one-time-code"
            class="ui-input"
            :class="fieldErrors.token ? 'border-red-400' : ''"
            @input="fieldErrors.token = ''"
          />
          <p v-if="fieldErrors.token" class="text-xs text-red-300">{{ fieldErrors.token }}</p>
        </label>
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("activateAccount.newPassword") }}
          <input
            v-model="password"
            type="password"
            autocomplete="new-password"
            class="ui-input"
            :class="fieldErrors.password ? 'border-red-400' : ''"
            @input="fieldErrors.password = ''"
          />
          <p v-if="fieldErrors.password" class="text-xs text-red-300">{{ fieldErrors.password }}</p>
        </label>
        <button
          type="submit"
          :disabled="store.submitting"
          class="ui-btn-primary w-full justify-center disabled:opacity-60"
        >
          {{ store.submitting ? t("activateAccount.activating") : t("activateAccount.activate") }}
        </button>
        <div v-if="store.error" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
          <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
          <p class="flex-1 text-sm text-red-300">{{ store.error }}</p>
        </div>
        <p v-if="store.success" class="text-sm text-emerald-400">{{ t("activateAccount.activated") }}</p>
      </form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { useActivationStore } from "../stores/activation";
import { useSessionStore } from "../stores/session";

const route = useRoute();
const router = useRouter();
const store = useActivationStore();
const session = useSessionStore();
const { t } = useI18n();

const token = ref("");
const password = ref("");
const fieldErrors = reactive({ token: "", password: "" });

onMounted(() => {
  if (typeof route.query.token === "string") token.value = route.query.token;
});

const submit = async () => {
  fieldErrors.token = "";
  fieldErrors.password = "";
  if (!token.value.trim()) {
    fieldErrors.token = t("activateAccount.tokenRequired");
    return;
  }
  if (password.value.length < 8) {
    fieldErrors.password = t("activateAccount.passwordTooShort");
    return;
  }
  await store.activate(token.value, password.value);
  if (store.success) {
    try {
      await session.fetchSession(true);
    } catch {
      // Ignore and continue with navigation fallback.
    }
    const next = typeof route.query.next === "string" ? route.query.next : null;
    if (next) {
      router.push(next);
    } else {
      router.push({ name: "onboarding" });
    }
  }
};
</script>
