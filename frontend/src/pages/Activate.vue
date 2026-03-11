<template>
  <div class="ui-auth-page flex items-center">
    <div class="ui-auth-card space-y-6">
      <div class="space-y-2 text-center">
        <p class="ui-kicker">{{ t("activateAccount.kicker") }}</p>
        <h1 class="ui-display text-2xl font-semibold text-white">{{ t("activateAccount.title") }}</h1>
        <p class="text-sm text-slate-300">{{ t("activateAccount.description") }}</p>
      </div>

      <form class="space-y-4" @submit.prevent="submit">
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("activateAccount.token") }}
          <input v-model="token" class="ui-input" required />
        </label>
        <label class="space-y-1 text-sm text-slate-200">
          {{ t("activateAccount.newPassword") }}
          <input v-model="password" type="password" class="ui-input" required minlength="8" />
        </label>
        <button
          type="submit"
          :disabled="store.submitting"
          class="ui-btn-primary w-full justify-center disabled:opacity-60"
        >
          {{ store.submitting ? t("activateAccount.activating") : t("activateAccount.activate") }}
        </button>
        <p v-if="store.error" class="text-sm text-red-400">{{ store.error }}</p>
        <p v-if="store.success" class="text-sm text-emerald-400">{{ t("activateAccount.activated") }}</p>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
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

onMounted(() => {
  if (typeof route.query.token === "string") token.value = route.query.token;
});

const submit = async () => {
  await store.activate(token.value, password.value);
  if (store.success) {
    try {
      await session.fetchSession(true);
    } catch (e) {
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
