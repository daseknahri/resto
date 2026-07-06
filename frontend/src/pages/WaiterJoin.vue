<template>
  <div class="ui-auth-page flex min-h-dvh flex-col items-center justify-center gap-8 px-4 py-10">
    <!-- ── Branding ──────────────────────────────────────────────────────────── -->
    <div class="text-center space-y-2 ui-reveal">
      <div
        class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-amber-500/20 bg-amber-500/10 shadow-lg shadow-amber-900/20"
        aria-hidden="true"
      >
        <!-- Serving-tray silhouette -->
        <svg class="h-8 w-8 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
          <ellipse cx="12" cy="10" rx="9" ry="2.2" stroke-linecap="round" />
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 10c0 4.418 4.03 8 9 8s9-3.582 9-8" />
          <line x1="12" y1="2" x2="12" y2="7.8" stroke-linecap="round" />
        </svg>
      </div>
      <p class="ui-kicker">{{ t('waiterJoin.kicker') }}</p>
      <h1 class="text-2xl font-bold text-white tracking-tight">{{ tenantName }}</h1>
    </div>

    <!-- ── Card ─────────────────────────────────────────────────────────────── -->
    <div class="ui-auth-card w-full max-w-sm space-y-5 ui-reveal" style="--ui-delay: 60ms">

      <!-- Step 1 — Install (hidden once already running standalone) -->
      <template v-if="!isStandalone">
        <section class="space-y-3">
          <div class="flex items-center gap-3">
            <span class="ui-step-badge" aria-hidden="true">1</span>
            <h2 class="text-sm font-semibold text-slate-100">{{ t('waiterJoin.installTitle') }}</h2>
          </div>
          <p class="text-xs leading-relaxed text-slate-400 ps-1">{{ t('waiterJoin.installHint') }}</p>

          <!-- Android / Chrome: native A2HS prompt -->
          <button
            v-if="canInstall"
            class="ui-btn-primary ui-press w-full justify-center ui-touch-target"
            @click="install"
          >
            {{ t('waiterJoin.installCta') }}
          </button>

          <!-- iOS / Firefox / other: manual instructions -->
          <div v-else class="rounded-2xl border border-slate-700/40 bg-slate-800/50 p-4 space-y-2.5">
            <p class="text-xs font-semibold text-slate-200">{{ t('waiterJoin.iosHint') }}</p>
            <ol class="list-decimal space-y-1.5 ps-4 text-xs text-slate-400 leading-relaxed">
              <li>{{ t('waiterJoin.iosStep1') }}</li>
              <li>{{ t('waiterJoin.iosStep2') }}</li>
              <li>{{ t('waiterJoin.iosStep3') }}</li>
            </ol>
          </div>
        </section>

        <!-- Divider -->
        <div class="flex items-center gap-3">
          <span class="flex-1 border-t border-slate-800" />
          <span class="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            {{ t('waiterJoin.thenStep') }}
          </span>
          <span class="flex-1 border-t border-slate-800" />
        </div>

        <!-- Step 2 label -->
        <div class="flex items-center gap-3 -mb-1">
          <span class="ui-step-badge" aria-hidden="true">2</span>
          <h2 class="text-sm font-semibold text-slate-100">{{ t('waiterJoin.signInTitle') }}</h2>
        </div>
      </template>

      <!-- Already installed in standalone mode -->
      <div
        v-else
        class="flex items-center gap-2.5 rounded-2xl border border-emerald-500/25 bg-emerald-500/8 px-3 py-3 text-xs text-emerald-300"
      >
        <svg class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
        </svg>
        <span class="font-medium">{{ t('waiterJoin.alreadyInstalled') }}</span>
      </div>

      <!-- ── Sign-in form ───────────────────────────────────────────────────── -->
      <form v-if="!mfaRequired && !forcePasswordChangeRequired" class="space-y-4" novalidate @submit.prevent="submit">
        <label class="block space-y-1.5 text-sm font-medium text-slate-200">
          {{ t('signIn.identifier') }}
          <input
            v-model="email"
            type="email"
            autocomplete="username"
            inputmode="email"
            class="ui-input ui-touch-target mt-1"
            :class="{ 'border-red-400': fieldErrors.email }"
            :aria-invalid="fieldErrors.email ? 'true' : undefined"
            @input="fieldErrors.email = ''"
          />
          <p v-if="fieldErrors.email" class="text-xs text-red-300 mt-1" role="alert">{{ fieldErrors.email }}</p>
        </label>

        <label class="block space-y-1.5 text-sm font-medium text-slate-200">
          {{ t('signIn.password') }}
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            class="ui-input ui-touch-target mt-1"
            :class="{ 'border-red-400': fieldErrors.password }"
            :aria-invalid="fieldErrors.password ? 'true' : undefined"
            @input="fieldErrors.password = ''"
          />
          <p v-if="fieldErrors.password" class="text-xs text-red-300 mt-1" role="alert">{{ fieldErrors.password }}</p>
        </label>

        <button
          type="submit"
          :disabled="loading || success"
          :aria-busy="loading"
          class="ui-btn-primary ui-press inline-flex w-full items-center justify-center gap-2 ui-touch-target disabled:opacity-60"
        >
          <svg v-if="loading" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ loading ? t('signIn.signingIn') : t('waiterJoin.signInCta') }}
        </button>

        <!-- Error -->
        <div
          v-if="error"
          role="alert"
          class="flex items-start gap-2.5 rounded-2xl border border-red-500/30 bg-red-500/8 px-3 py-3"
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
          class="flex items-center gap-2.5 rounded-2xl border border-emerald-500/25 bg-emerald-500/8 px-3 py-3 text-sm text-emerald-300"
        >
          <svg class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
          <span class="font-medium">{{ t('waiterJoin.successRedirecting') }}</span>
        </div>
      </form>

      <!-- ── Forced password-change step (freshly-invited staff) ─────────────── -->
      <form v-else-if="forcePasswordChangeRequired" class="space-y-4" novalidate @submit.prevent="submitForcePasswordChange">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t('forcePasswordChange.kicker') }}</p>
          <h2 class="text-sm font-semibold text-slate-100">{{ t('forcePasswordChange.title') }}</h2>
          <p class="text-xs leading-relaxed text-slate-400">{{ t('forcePasswordChange.description') }}</p>
        </div>

        <label class="block space-y-1.5 text-sm font-medium text-slate-200">
          {{ t('forcePasswordChange.currentLabel') }}
          <input
            v-model="forcePwForm.current"
            type="password"
            autocomplete="current-password"
            class="ui-input ui-touch-target mt-1"
            :disabled="forcePwForm.loading"
          />
        </label>

        <label class="block space-y-1.5 text-sm font-medium text-slate-200">
          {{ t('forcePasswordChange.newLabel') }}
          <input
            v-model="forcePwForm.next"
            type="password"
            autocomplete="new-password"
            class="ui-input ui-touch-target mt-1"
            :disabled="forcePwForm.loading"
          />
        </label>

        <label class="block space-y-1.5 text-sm font-medium text-slate-200">
          {{ t('forcePasswordChange.confirmLabel') }}
          <input
            v-model="forcePwForm.confirm"
            type="password"
            autocomplete="new-password"
            class="ui-input ui-touch-target mt-1"
            :disabled="forcePwForm.loading"
          />
        </label>

        <p v-if="forcePwForm.error" class="text-xs text-red-300" role="alert">{{ forcePwForm.error }}</p>

        <button
          type="submit"
          :disabled="forcePwForm.loading || !forcePwForm.current || !forcePwForm.next || !forcePwForm.confirm"
          :aria-busy="forcePwForm.loading"
          class="ui-btn-primary ui-press inline-flex w-full items-center justify-center gap-2 ui-touch-target disabled:opacity-60"
        >
          <svg v-if="forcePwForm.loading" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ forcePwForm.loading ? t('forcePasswordChange.submitting') : t('forcePasswordChange.submitBtn') }}
        </button>

        <!-- Success flash -->
        <div
          v-if="success"
          role="status"
          class="flex items-center gap-2.5 rounded-2xl border border-emerald-500/25 bg-emerald-500/8 px-3 py-3 text-sm text-emerald-300"
        >
          <svg class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
          <span class="font-medium">{{ t('waiterJoin.successRedirecting') }}</span>
        </div>
      </form>

      <!-- ── MFA verification step ───────────────────────────────────────────── -->
      <form v-else class="space-y-4" novalidate @submit.prevent="submitMfa">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t('mfa.stepKicker') }}</p>
          <h2 class="text-sm font-semibold text-slate-100">{{ t('mfa.stepTitle') }}</h2>
          <p class="text-xs leading-relaxed text-slate-400">{{ t('mfa.stepDescription') }}</p>
        </div>

        <label v-if="!useBackupCode" class="block space-y-1.5 text-sm font-medium text-slate-200">
          {{ t('mfa.codeLabel') }}
          <input
            v-model="mfaCode"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            class="ui-input ui-touch-target mt-1"
            :class="{ 'border-red-400': mfaError }"
            :aria-invalid="mfaError ? 'true' : undefined"
            :placeholder="t('mfa.codePlaceholder')"
            @input="mfaError = ''"
          />
        </label>

        <label v-else class="block space-y-1.5 text-sm font-medium text-slate-200">
          {{ t('mfa.backupCodeLabel') }}
          <input
            v-model="mfaBackupCode"
            type="text"
            autocomplete="off"
            class="ui-input ui-touch-target mt-1"
            :class="{ 'border-red-400': mfaError }"
            :aria-invalid="mfaError ? 'true' : undefined"
            :placeholder="t('mfa.backupCodePlaceholder')"
            @input="mfaError = ''"
          />
        </label>
        <p v-if="mfaError" class="text-xs text-red-300 mt-1" role="alert">{{ mfaError }}</p>

        <button
          type="submit"
          :disabled="loading || success"
          :aria-busy="loading"
          class="ui-btn-primary ui-press inline-flex w-full items-center justify-center gap-2 ui-touch-target disabled:opacity-60"
        >
          <svg v-if="loading" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ loading ? t('mfa.verifying') : t('mfa.verifyBtn') }}
        </button>

        <div class="flex items-center justify-between gap-3 text-xs">
          <button type="button" class="text-slate-400 underline-offset-2 hover:underline" @click="toggleBackupCode">
            {{ useBackupCode ? t('mfa.useTotpCode') : t('mfa.useBackupCode') }}
          </button>
          <button type="button" class="text-slate-400 underline-offset-2 hover:underline" @click="backToLogin">
            {{ t('mfa.backToLogin') }}
          </button>
        </div>

        <!-- Success flash -->
        <div
          v-if="success"
          role="status"
          class="flex items-center gap-2.5 rounded-2xl border border-emerald-500/25 bg-emerald-500/8 px-3 py-3 text-sm text-emerald-300"
        >
          <svg class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
          <span class="font-medium">{{ t('waiterJoin.successRedirecting') }}</span>
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
import api from "../lib/api";

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

// MFA state — mirrors SignIn.vue's handling of the 202/mfa_required response.
const mfaRequired = ref(false);
const mfaCode = ref("");
const mfaBackupCode = ref("");
const mfaError = ref("");
const useBackupCode = ref(false);

// U4: forced password-change state — a freshly-invited staff member (server-side
// must_change_password=True) must set their own password before landing in the app.
const forcePasswordChangeRequired = ref(false);
const forcePwForm = ref({ current: "", next: "", confirm: "", loading: false, error: "" });

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
    const result = await session.signIn(email.value.trim(), password.value);
    if (result && result.mfaRequired) {
      // Second factor required — do NOT flash success or redirect yet.
      mfaRequired.value = true;
      mfaCode.value = "";
      mfaBackupCode.value = "";
      mfaError.value = "";
      useBackupCode.value = false;
      return;
    }
    completeSignIn(result);
  } catch {
    error.value = session.error || t("signIn.failed");
  } finally {
    loading.value = false;
  }
};

// U4: shared post-authentication gate — if the server flagged this account as
// needing a forced password change, show that step instead of redirecting.
// Only once that step succeeds does the staff member land in the app.
const completeSignIn = (user) => {
  if (user && user.must_change_password) {
    forcePasswordChangeRequired.value = true;
    forcePwForm.value = { current: "", next: "", confirm: "", loading: false, error: "" };
    return;
  }
  success.value = true;
  // Replace so the join page isn't in history — staff should land in the waiter app
  router.replace({ name: "waiter" });
};

const toggleBackupCode = () => {
  useBackupCode.value = !useBackupCode.value;
  mfaError.value = "";
  mfaCode.value = "";
  mfaBackupCode.value = "";
};

const backToLogin = () => {
  mfaRequired.value = false;
  mfaCode.value = "";
  mfaBackupCode.value = "";
  mfaError.value = "";
  useBackupCode.value = false;
};

const submitMfa = async () => {
  mfaError.value = "";
  const codeVal = useBackupCode.value ? mfaBackupCode.value.trim() : mfaCode.value.trim();
  if (!codeVal) {
    mfaError.value = t("mfa.codeRequired");
    return;
  }
  loading.value = true;
  try {
    const payload = useBackupCode.value ? { backup_code: codeVal } : { code: codeVal };
    const user = await session.verifyMfa(payload);
    completeSignIn(user);
  } catch {
    mfaError.value = session.error || t("mfa.invalidCode");
  } finally {
    loading.value = false;
  }
};

const submitForcePasswordChange = async () => {
  forcePwForm.value.error = "";
  if (!forcePwForm.value.current || !forcePwForm.value.next || !forcePwForm.value.confirm) return;
  if (forcePwForm.value.next !== forcePwForm.value.confirm) {
    forcePwForm.value.error = t("forcePasswordChange.confirmMismatch");
    return;
  }
  forcePwForm.value.loading = true;
  try {
    await api.post("/staff/change-password/", {
      current_password: forcePwForm.value.current,
      new_password: forcePwForm.value.next,
    });
    success.value = true;
    router.replace({ name: "waiter" });
  } catch (err) {
    const data = err?.response?.data;
    const msg = (typeof data?.detail === "string" && data.detail)
      || (Array.isArray(data?.detail) && data.detail[0])
      || t("forcePasswordChange.errorGeneric");
    forcePwForm.value.error = msg;
  } finally {
    forcePwForm.value.loading = false;
  }
};
</script>
