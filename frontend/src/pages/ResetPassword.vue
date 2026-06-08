<template>
  <div class="ui-auth-page flex items-center">
    <div class="ui-auth-stage">
      <section class="ui-auth-spotlight relative space-y-6" aria-labelledby="reset-spotlight-heading">
        <div class="relative space-y-3">
          <span class="ui-chip-strong w-fit">{{ t("resetPassword.kicker") }}</span>
          <h1 id="reset-spotlight-heading" class="ui-display max-w-lg text-4xl font-semibold text-white">{{ t("resetPassword.title") }}</h1>
          <p class="max-w-md text-sm text-slate-300">{{ t("resetPassword.description") }}</p>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <article class="ui-orbit-card ui-reveal" :style="{ '--ui-delay': '0ms' }">
            <p class="ui-kicker">{{ t("resetPassword.token") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("resetPassword.spotlightSecureTitle") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("resetPassword.spotlightSecureBody") }}</p>
          </article>
          <article class="ui-orbit-card ui-reveal" :style="{ '--ui-delay': '56ms' }">
            <p class="ui-kicker">{{ t("resetPassword.newPassword") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("resetPassword.spotlightSimpleTitle") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("resetPassword.spotlightSimpleBody") }}</p>
          </article>
        </div>
      </section>

      <main>
        <div class="ui-auth-card ui-reveal space-y-6" :style="{ '--ui-delay': '80ms' }">
          <div class="space-y-2 text-center">
            <p class="ui-kicker">{{ t("resetPassword.kicker") }}</p>
            <h2 class="ui-display text-2xl font-semibold tracking-tight text-white">{{ t("resetPassword.title") }}</h2>
            <p class="text-sm leading-relaxed text-slate-300">{{ t("resetPassword.description") }}</p>
          </div>

          <form class="space-y-5" novalidate @submit.prevent="submit">
            <label class="block space-y-1.5 text-sm font-medium text-slate-200">
              {{ t("resetPassword.token") }}
              <input
                id="reset-token-input"
                v-model="token"
                type="text"
                autocomplete="one-time-code"
                class="ui-input mt-1 font-normal"
                :class="fieldErrors.token ? 'border-red-400' : ''"
                :aria-invalid="fieldErrors.token ? 'true' : undefined"
                :aria-describedby="fieldErrors.token ? 'reset-token-error' : undefined"
                aria-required="true"
                @input="fieldErrors.token = ''"
              />
              <p v-if="fieldErrors.token" id="reset-token-error" class="text-xs font-normal text-red-300" role="alert">{{ fieldErrors.token }}</p>
            </label>

            <label class="block space-y-1.5 text-sm font-medium text-slate-200">
              {{ t("resetPassword.newPassword") }}
              <input
                id="reset-password-input"
                v-model="password"
                type="password"
                autocomplete="new-password"
                class="ui-input mt-1 font-normal"
                :class="fieldErrors.password ? 'border-red-400' : ''"
                :aria-invalid="fieldErrors.password ? 'true' : undefined"
                :aria-describedby="fieldErrors.password ? 'reset-password-error' : undefined"
                aria-required="true"
                @input="fieldErrors.password = ''"
              />
              <p v-if="fieldErrors.password" id="reset-password-error" class="text-xs font-normal text-red-300" role="alert">{{ fieldErrors.password }}</p>
            </label>

            <div class="space-y-3 pt-1">
              <button
                type="submit"
                :disabled="submitting"
                :aria-busy="submitting ? 'true' : undefined"
                class="ui-btn-primary ui-press w-full justify-center disabled:opacity-60"
              >
                {{ submitting ? t("resetPassword.resetting") : t("resetPassword.reset") }}
              </button>

              <div v-if="message" role="alert" class="flex items-start gap-2.5 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3">
                <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/></svg>
                <p class="flex-1 text-sm text-emerald-200">{{ message }}</p>
              </div>

              <div v-if="error" role="alert" class="flex items-start gap-2.5 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
                <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
                <p class="flex-1 text-sm text-red-300">{{ error }}</p>
              </div>
            </div>
          </form>

          <div class="ui-section-band flex flex-wrap items-baseline gap-x-1 text-xs text-slate-300">
            <span>{{ t("resetPassword.continueTo") }}</span>
            <RouterLink
              class="text-[var(--color-secondary)] underline-offset-2 hover:underline focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:underline"
              :to="signinLink"
            >{{ t("resetPassword.signInLink") }}</RouterLink>
          </div>
        </div>
      </main>
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
