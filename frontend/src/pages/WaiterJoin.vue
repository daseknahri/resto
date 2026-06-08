<template>
  <div class="flex min-h-dvh flex-col items-center justify-center bg-slate-950 px-4 py-10 gap-8">
    <!-- ── Branding ──────────────────────────────────────────────────────────── -->
    <div class="text-center space-y-2">
      <div
        class="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/12 ring-1 ring-inset ring-indigo-500/25"
        aria-hidden="true"
      >
        <!-- Serving-tray silhouette -->
        <svg class="h-7 w-7 text-indigo-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
          <ellipse cx="12" cy="10" rx="9" ry="2.2" stroke-linecap="round" />
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 10c0 4.418 4.03 8 9 8s9-3.582 9-8" />
          <line x1="12" y1="2" x2="12" y2="7.8" stroke-linecap="round" />
        </svg>
      </div>
      <p class="text-[11px] font-semibold uppercase tracking-widest text-indigo-400">
        {{ t('waiterJoin.kicker') }}
      </p>
      <h1 class="text-2xl font-bold text-white">{{ tenantName }}</h1>
    </div>

    <!-- ── Card ─────────────────────────────────────────────────────────────── -->
    <div class="w-full max-w-sm space-y-5 rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-2xl backdrop-blur-sm">

      <!-- Step 1 — Install (hidden once already running standalone) -->
      <template v-if="!isStandalone">
        <section class="space-y-3">
          <div class="flex items-center gap-2">
            <span
              class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-[11px] font-bold text-white"
              aria-hidden="true"
            >1</span>
            <h2 class="text-sm font-semibold text-slate-100">{{ t('waiterJoin.installTitle') }}</h2>
          </div>
          <p class="text-xs leading-relaxed text-slate-400">{{ t('waiterJoin.installHint') }}</p>

          <!-- Android / Chrome: native A2HS prompt -->
          <button
            v-if="canInstall"
            class="ui-btn-primary ui-press w-full justify-center"
            @click="install"
          >
            {{ t('waiterJoin.installCta') }}
          </button>

          <!-- iOS / Firefox / other: manual instructions -->
          <div v-else class="rounded-xl border border-slate-700/40 bg-slate-800/50 p-3 space-y-2">
            <p class="text-xs font-medium text-slate-200">{{ t('waiterJoin.iosHint') }}</p>
            <ol class="list-decimal space-y-1 ps-4 text-xs text-slate-400">
              <li>{{ t('waiterJoin.iosStep1') }}</li>
              <li>{{ t('waiterJoin.iosStep2') }}</li>
              <li>{{ t('waiterJoin.iosStep3') }}</li>
            </ol>
          </div>
        </section>

        <!-- Divider -->
        <div class="flex items-center gap-3">
          <span class="flex-1 border-t border-slate-800" />
          <span class="text-[10px] font-semibold uppercase tracking-widest text-slate-600">
            {{ t('waiterJoin.thenStep') }}
          </span>
          <span class="flex-1 border-t border-slate-800" />
        </div>

        <!-- Step 2 label -->
        <div class="flex items-center gap-2 -mb-1">
          <span
            class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-700 text-[11px] font-bold text-slate-300"
            aria-hidden="true"
          >2</span>
          <h2 class="text-sm font-semibold text-slate-100">{{ t('waiterJoin.signInTitle') }}</h2>
        </div>
      </template>

      <!-- Already installed in standalone mode -->
      <div
        v-else
        class="flex items-center gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/8 px-3 py-2.5 text-xs text-emerald-300"
      >
        <svg class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
        </svg>
        <span>{{ t('waiterJoin.alreadyInstalled') }}</span>
      </div>

      <!-- ── Sign-in form ───────────────────────────────────────────────────── -->
      <form class="space-y-4" novalidate @submit.prevent="submit">
        <label class="block space-y-1 text-sm text-slate-200">
          {{ t('signIn.identifier') }}
          <input
            v-model="email"
            type="email"
            autocomplete="username"
            inputmode="email"
            class="ui-input"
            :class="{ 'border-red-400': fieldErrors.email }"
            :aria-invalid="fieldErrors.email ? 'true' : undefined"
            @input="fieldErrors.email = ''"
          />
          <p v-if="fieldErrors.email" class="text-xs text-red-300" role="alert">{{ fieldErrors.email }}</p>
        </label>

        <label class="block space-y-1 text-sm text-slate-200">
          {{ t('signIn.password') }}
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            class="ui-input"
            :class="{ 'border-red-400': fieldErrors.password }"
            :aria-invalid="fieldErrors.password ? 'true' : undefined"
            @input="fieldErrors.password = ''"
          />
          <p v-if="fieldErrors.password" class="text-xs text-red-300" role="alert">{{ fieldErrors.password }}</p>
        </label>

        <button
          type="submit"
          :disabled="loading || success"
          class="ui-btn-primary ui-press w-full justify-center disabled:opacity-60"
        >
          {{ loading ? t('signIn.signingIn') : t('waiterJoin.signInCta') }}
        </button>

        <!-- Error -->
        <div
          v-if="error"
          role="alert"
          class="flex items-start gap-2 rounded-2xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
          </svg>
          <p class="flex-1 text-sm text-red-300">{{ error }}</p>
        </div>

        <!-- Success flash -->
        <div
          v-if="success"
          role="status"
          class="flex items-center gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/8 px-3 py-2.5 text-sm text-emerald-300"
        >
          <svg class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
          {{ t('waiterJoin.successRedirecting') }}
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { useInstallPrompt } from "../composables/useInstallPrompt";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";

const { t } = useI18n();
const router = useRouter();
const session = useSessionStore();
const tenant = useTenantStore();
const { canInstall, isStandalone, install } = useInstallPrompt();

const email = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);
const success = ref(false);
const fieldErrors = reactive({ email: "", password: "" });

const tenantName = computed(() => tenant.meta?.name || t("waiterJoin.kicker"));

onMounted(async () => {
  if (!tenant.meta && !tenant.loading) {
    try {
      await tenant.fetchMeta();
    } catch {
      // best-effort branding — silently ignore
    }
  }
});

const submit = async () => {
  fieldErrors.email = "";
  fieldErrors.password = "";
  error.value = "";

  if (!email.value.trim()) {
    fieldErrors.email = t("signIn.identifierRequired");
    return;
  }
  if (!password.value) {
    fieldErrors.password = t("signIn.passwordRequired");
    return;
  }

  loading.value = true;
  try {
    await session.signIn(email.value.trim(), password.value);
    success.value = true;
    // Replace so the join page isn't in history — staff should land in the waiter app
    router.replace({ name: "waiter" });
  } catch {
    error.value = session.error || t("signIn.failed");
  } finally {
    loading.value = false;
  }
};
</script>
