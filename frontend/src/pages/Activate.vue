<template>
  <div class="ui-auth-page flex items-center">
    <main class="ui-auth-stage">
      <section class="ui-auth-spotlight relative space-y-6" aria-labelledby="activate-spotlight-heading">
        <div class="relative space-y-3">
          <span class="ui-chip-strong w-fit">{{ t("activateAccount.kicker") }}</span>
          <h1 id="activate-spotlight-heading" class="ui-display max-w-lg text-4xl font-semibold text-white">{{ t("activateAccount.title") }}</h1>
          <p class="max-w-md text-sm text-slate-300">{{ t("activateAccount.description") }}</p>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <article class="ui-orbit-card ui-reveal" :style="{ '--ui-delay': '0ms' }">
            <p class="ui-kicker">{{ t("activateAccount.token") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("activateAccount.title") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("activateAccount.description") }}</p>
          </article>
          <article class="ui-orbit-card ui-reveal" :style="{ '--ui-delay': '56ms' }">
            <p class="ui-kicker">{{ t("activateAccount.newPassword") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("activateAccount.activate") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("activateAccount.newPasswordHint") }}</p>
          </article>
        </div>
      </section>

      <div>
        <div class="ui-auth-card ui-reveal space-y-6" :style="{ '--ui-delay': '80ms' }">
          <div class="ui-hero-ribbon space-y-3 text-center">
            <p class="ui-kicker">{{ t("activateAccount.kicker") }}</p>
            <h2 class="ui-display text-2xl font-semibold text-white">{{ t("activateAccount.title") }}</h2>
            <p class="text-sm text-slate-300">{{ t("activateAccount.description") }}</p>
          </div>

          <form class="space-y-4" novalidate @submit.prevent="submit">
            <div class="space-y-1">
              <label class="block text-sm text-slate-200" for="activate-token-input">
                {{ t("activateAccount.token") }}
              </label>
              <input
                id="activate-token-input"
                v-model="token"
                type="text"
                autocomplete="one-time-code"
                class="ui-input"
                :class="fieldErrors.token ? 'border-red-400' : ''"
                :aria-invalid="fieldErrors.token ? 'true' : undefined"
                :aria-describedby="fieldErrors.token ? 'activate-token-error' : undefined"
                aria-required="true"
                @input="fieldErrors.token = ''"
              />
              <p v-if="fieldErrors.token" id="activate-token-error" class="text-xs text-red-300" role="alert">{{ fieldErrors.token }}</p>
            </div>

            <div class="space-y-1">
              <label class="block text-sm text-slate-200" for="activate-password-input">
                {{ t("activateAccount.newPassword") }}
              </label>
              <input
                id="activate-password-input"
                v-model="password"
                type="password"
                autocomplete="new-password"
                class="ui-input"
                :class="fieldErrors.password ? 'border-red-400' : ''"
                :aria-invalid="fieldErrors.password ? 'true' : undefined"
                :aria-describedby="fieldErrors.password ? 'activate-password-error' : undefined"
                aria-required="true"
                @input="fieldErrors.password = ''"
              />
              <p v-if="fieldErrors.password" id="activate-password-error" class="text-xs text-red-300" role="alert">{{ fieldErrors.password }}</p>
            </div>

            <button
              type="submit"
              :disabled="store.submitting"
              :aria-busy="store.submitting"
              class="ui-btn-primary ui-press ui-touch-target inline-flex w-full items-center justify-center gap-2 disabled:opacity-60"
            >
              <svg v-if="store.submitting" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ store.submitting ? t("activateAccount.activating") : t("activateAccount.activate") }}
            </button>

            <div aria-live="polite" aria-atomic="true" class="empty:hidden">
              <div v-if="store.success" class="flex items-start gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3">
                <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/></svg>
                <p class="flex-1 text-sm text-emerald-200">{{ t("activateAccount.activated") }}</p>
              </div>
            </div>

            <div v-if="store.error" role="alert" class="flex items-start gap-2 rounded-2xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
              <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
              <p class="flex-1 text-sm text-red-300">{{ store.error }}</p>
            </div>
          </form>
        </div>
      </div>
    </main>
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
