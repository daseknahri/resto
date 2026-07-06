<template>
  <div class="ui-auth-page flex items-center">
    <div class="ui-auth-stage">
      <div class="ui-auth-spotlight relative space-y-6" aria-hidden="true">
        <div class="relative space-y-3">
          <span class="ui-chip-strong w-fit">{{ t("signIn.kicker") }}</span>
          <p class="ui-display max-w-lg text-4xl font-semibold text-white">{{ t("signIn.title") }}</p>
          <p class="max-w-md text-sm text-slate-300">{{ t("signIn.description") }}</p>
        </div>

        <div class="relative grid gap-3">
          <div class="ui-orbit-card ui-reveal" :style="{ '--ui-delay': '0ms' }">
            <p class="ui-kicker">{{ t("common.workspace") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("signIn.identifier") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("signIn.firstTime") }}</p>
          </div>
          <div class="ui-orbit-card ui-reveal" :style="{ '--ui-delay': '56ms' }">
            <p class="ui-kicker">{{ t("common.reserve") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("signIn.password") }}</p>
            <p class="mt-1 text-sm text-slate-400">{{ t("signIn.forgotPassword") }}</p>
          </div>
        </div>

        <div class="grid gap-3 sm:grid-cols-3">
          <div class="ui-metric-card ui-reveal" :style="{ '--ui-delay': '28ms' }">
            <p class="ui-kicker">{{ t("common.workspace") }}</p>
            <p class="mt-1 text-xl font-semibold text-white">{{ t("common.owner") }}</p>
          </div>
          <div class="ui-metric-card ui-reveal" :style="{ '--ui-delay': '56ms' }">
            <p class="ui-kicker">{{ t("common.available") }}</p>
            <p class="mt-1 text-xl tabular-nums font-semibold text-white">{{ t("signIn.alwaysOn") }}</p>
          </div>
          <div class="ui-metric-card ui-reveal" :style="{ '--ui-delay': '84ms' }">
            <p class="ui-kicker">{{ t("common.refresh") }}</p>
            <p class="mt-1 text-xl font-semibold text-white">{{ t("signIn.kicker") }}</p>
          </div>
        </div>
      </div>

      <div class="ui-auth-card ui-reveal space-y-6" :style="{ '--ui-delay': '80ms' }">
        <!-- ── MFA verification step ── -->
        <template v-if="mfaRequired">
          <div class="space-y-2 text-center">
            <p class="ui-kicker">{{ t("mfa.stepKicker") }}</p>
            <h1 class="ui-display text-3xl font-semibold tracking-tight text-white">{{ t("mfa.stepTitle") }}</h1>
            <p class="text-sm leading-relaxed text-slate-400">{{ t("mfa.stepDescription") }}</p>
          </div>

          <form class="space-y-5" novalidate @submit.prevent="submitMfa">
            <template v-if="!useBackupCode">
              <label class="block space-y-1.5 text-sm font-medium text-slate-200">
                {{ t("mfa.codeLabel") }}
                <input
                  ref="mfaCodeInputRef"
                  v-model="mfaCode"
                  type="text"
                  inputmode="numeric"
                  autocomplete="one-time-code"
                  maxlength="6"
                  class="ui-input mt-1 font-normal tracking-[0.25em] text-center"
                  :class="mfaError ? 'border-red-400' : ''"
                  :aria-invalid="mfaError ? 'true' : undefined"
                  :aria-describedby="mfaError ? 'mfa-code-error' : undefined"
                  :placeholder="t('mfa.codePlaceholder')"
                  aria-required="true"
                  @input="mfaError = ''"
                />
                <p v-if="mfaError" id="mfa-code-error" class="text-xs font-normal text-red-300" role="alert">{{ mfaError }}</p>
              </label>
            </template>
            <template v-else>
              <label class="block space-y-1.5 text-sm font-medium text-slate-200">
                {{ t("mfa.backupCodeLabel") }}
                <input
                  ref="mfaBackupInputRef"
                  v-model="mfaBackupCode"
                  type="text"
                  autocomplete="off"
                  class="ui-input mt-1 font-normal"
                  :class="mfaError ? 'border-red-400' : ''"
                  :aria-invalid="mfaError ? 'true' : undefined"
                  :aria-describedby="mfaError ? 'mfa-backup-error' : undefined"
                  :placeholder="t('mfa.backupCodePlaceholder')"
                  aria-required="true"
                  @input="mfaError = ''"
                />
                <p v-if="mfaError" id="mfa-backup-error" class="text-xs font-normal text-red-300" role="alert">{{ mfaError }}</p>
              </label>
            </template>

            <div class="space-y-3 pt-1">
              <button
                type="submit"
                :disabled="session.loading"
                :aria-busy="session.loading"
                class="ui-btn-primary ui-press inline-flex w-full items-center justify-center gap-2 disabled:opacity-60"
              >
                <svg v-if="session.loading" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                {{ session.loading ? t("mfa.verifying") : t("mfa.verifyBtn") }}
              </button>

              <button
                type="button"
                class="w-full text-center text-xs text-slate-400 underline-offset-2 hover:text-slate-200 hover:underline focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
                @click="toggleBackupCode"
              >
                {{ useBackupCode ? t("mfa.useTotpCode") : t("mfa.useBackupCode") }}
              </button>

              <div v-if="mfaError && !useBackupCode" class="sr-only" aria-live="assertive">{{ mfaError }}</div>

              <button
                type="button"
                class="w-full text-center text-xs text-slate-500 underline-offset-2 hover:text-slate-300 hover:underline focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
                @click="backToLogin"
              >
                {{ t("mfa.backToLogin") }}
              </button>
            </div>
          </form>
        </template>

        <!-- ── Forced password-change step (freshly-invited staff) ── -->
        <template v-else-if="forcePasswordChangeRequired">
          <div class="space-y-2 text-center">
            <p class="ui-kicker">{{ t("forcePasswordChange.kicker") }}</p>
            <h1 class="ui-display text-3xl font-semibold tracking-tight text-white">{{ t("forcePasswordChange.title") }}</h1>
            <p class="text-sm leading-relaxed text-slate-400">{{ t("forcePasswordChange.description") }}</p>
          </div>

          <form class="space-y-5" novalidate @submit.prevent="submitForcePasswordChange">
            <label class="block space-y-1.5 text-sm font-medium text-slate-200">
              {{ t("forcePasswordChange.currentLabel") }}
              <input
                v-model="forcePwForm.current"
                type="password"
                autocomplete="current-password"
                class="ui-input mt-1 font-normal"
                :disabled="forcePwForm.loading"
                aria-required="true"
              />
            </label>
            <label class="block space-y-1.5 text-sm font-medium text-slate-200">
              {{ t("forcePasswordChange.newLabel") }}
              <input
                v-model="forcePwForm.next"
                type="password"
                autocomplete="new-password"
                class="ui-input mt-1 font-normal"
                :disabled="forcePwForm.loading"
                aria-required="true"
              />
            </label>
            <label class="block space-y-1.5 text-sm font-medium text-slate-200">
              {{ t("forcePasswordChange.confirmLabel") }}
              <input
                v-model="forcePwForm.confirm"
                type="password"
                autocomplete="new-password"
                class="ui-input mt-1 font-normal"
                :disabled="forcePwForm.loading"
                aria-required="true"
              />
            </label>
            <div class="space-y-3 pt-1">
              <button
                type="submit"
                :disabled="forcePwForm.loading"
                :aria-busy="forcePwForm.loading"
                class="ui-btn-primary ui-press inline-flex w-full items-center justify-center gap-2 disabled:opacity-60"
              >
                <svg v-if="forcePwForm.loading" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                {{ forcePwForm.loading ? t("forcePasswordChange.submitting") : t("forcePasswordChange.submitBtn") }}
              </button>
              <div v-if="forcePwForm.error" role="alert" class="flex items-start gap-2.5 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
                <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
                <p class="flex-1 text-sm text-red-300">{{ forcePwForm.error }}</p>
              </div>
            </div>
          </form>
        </template>

        <!-- ── Normal sign-in step ── -->
        <template v-else>
          <div class="space-y-2 text-center">
            <p class="ui-kicker">{{ t("signIn.kicker") }}</p>
            <h1 class="ui-display text-3xl font-semibold tracking-tight text-white">{{ t("signIn.title") }}</h1>
            <p class="text-sm leading-relaxed text-slate-400">{{ t("signIn.description") }}</p>
          </div>

          <!-- Session-expired notice (shown when redirected from a 401) -->
          <div
            v-if="sessionExpired"
            role="alert"
            class="flex items-start gap-2.5 rounded-2xl border border-amber-500/30 bg-amber-500/8 px-4 py-3"
          >
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400"><path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0V5.75A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm font-medium text-amber-300">{{ t("signIn.sessionExpired") }}</p>
          </div>

          <form class="space-y-5" novalidate @submit.prevent="submit">
            <label class="block space-y-1.5 text-sm font-medium text-slate-200">
              {{ t("signIn.identifier") }}
              <input
                v-model="identifier"
                type="text"
                autocomplete="username"
                class="ui-input mt-1 font-normal"
                :class="fieldErrors.identifier ? 'border-red-400' : ''"
                :aria-invalid="fieldErrors.identifier ? 'true' : undefined"
                :aria-describedby="fieldErrors.identifier ? 'signin-identifier-error' : undefined"
                aria-required="true"
                @input="fieldErrors.identifier = ''"
              />
              <p v-if="fieldErrors.identifier" id="signin-identifier-error" class="text-xs font-normal text-red-300" role="alert">{{ fieldErrors.identifier }}</p>
            </label>
            <label class="block space-y-1.5 text-sm font-medium text-slate-200">
              {{ t("signIn.password") }}
              <input
                v-model="password"
                type="password"
                autocomplete="current-password"
                class="ui-input mt-1 font-normal"
                :class="fieldErrors.password ? 'border-red-400' : ''"
                :aria-invalid="fieldErrors.password ? 'true' : undefined"
                :aria-describedby="fieldErrors.password ? 'signin-password-error' : undefined"
                aria-required="true"
                @input="fieldErrors.password = ''"
              />
              <p v-if="fieldErrors.password" id="signin-password-error" class="text-xs font-normal text-red-300" role="alert">{{ fieldErrors.password }}</p>
            </label>
            <div class="space-y-3 pt-1">
              <button
                type="submit"
                :disabled="session.loading"
                :aria-busy="session.loading"
                class="ui-btn-primary ui-press inline-flex w-full items-center justify-center gap-2 disabled:opacity-60"
              >
                <svg v-if="session.loading" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                {{ session.loading ? t("signIn.signingIn") : t("common.signIn") }}
              </button>
              <div v-if="error" role="alert" class="flex items-start gap-2.5 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
                <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
                <p class="flex-1 text-sm text-red-300">{{ error }}</p>
              </div>
            </div>
          </form>

          <div class="ui-section-band space-y-2.5 text-xs text-slate-400">
            <p class="text-xs font-semibold uppercase tracking-wide text-slate-300">{{ t("signIn.firstTime") }}</p>
            <p class="leading-relaxed">
              {{ t("signIn.firstTime") }}
              <RouterLink :to="activateLink" class="ms-1 font-medium text-[var(--color-secondary)] underline-offset-2 hover:underline focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:underline">{{ t("signIn.activationLink") }}</RouterLink>
            </p>
            <p class="leading-relaxed">
              {{ t("signIn.forgotPassword") }}
              <RouterLink :to="forgotPasswordLink" class="ms-1 font-medium text-[var(--color-secondary)] underline-offset-2 hover:underline focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:underline">{{ t("signIn.resetHere") }}</RouterLink>
            </p>
          </div>

          <!-- Customer hint — helps a consumer who landed on the wrong sign-in page -->
          <p class="text-center text-xs text-slate-500">
            {{ t("signIn.customerHint") }}
            <RouterLink :to="{ name: 'customer-account' }" class="ms-1 font-medium text-[var(--color-secondary)] underline-offset-2 hover:underline focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:underline">{{ t("signIn.customerHintCta") }}</RouterLink>
          </p>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { currentHostname, isPlatformPublicHost } from "../lib/runtimeHost";
import { useSessionStore } from "../stores/session";
import api from "../lib/api";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const { t } = useI18n();

// Show an amber notice when api.js redirected here after a 401 (session expired)
const sessionExpired = computed(() => route.query.expired === "1");

const identifier = ref("");
const password = ref("");
const error = ref("");
const fieldErrors = reactive({ identifier: "", password: "" });

// MFA state
const mfaRequired = ref(false);
const mfaCode = ref("");
const mfaBackupCode = ref("");
const mfaError = ref("");
const useBackupCode = ref(false);
const mfaCodeInputRef = ref(null);
const mfaBackupInputRef = ref(null);

// U4: forced password-change state — a freshly-invited staff member (server-side
// must_change_password=True) must set their own password before landing in the app.
const forcePasswordChangeRequired = ref(false);
const forcePwForm = ref({ current: "", next: "", confirm: "", loading: false, error: "" });
let pendingPostLoginUser = null;

const activateLink = computed(() => {
  const next = typeof route.query.next === "string" ? route.query.next : "";
  return next ? { name: "activate", query: { next } } : { name: "activate" };
});

const forgotPasswordLink = computed(() => {
  const next = typeof route.query.next === "string" ? route.query.next : "";
  return next ? { name: "forgot-password", query: { next } } : { name: "forgot-password" };
});

const fallbackRoute = () => {
  if (session.isPlatformAdmin) return { name: "admin-console" };
  if (session.isTenantStaff) return { name: "waiter" };
  if (session.canEditTenantMenu) return { name: "owner-home" };
  return { name: "home" };
};

const redirectOwnerToTenantHost = (user) => {
  if (typeof window === "undefined") return false;
  const host = currentHostname();
  const tenantSlug = String(user?.tenant?.slug || "").trim().toLowerCase();
  if (!tenantSlug || !isPlatformPublicHost(host)) return false;
  const targetHost = `${tenantSlug}.${host}`;
  const next = typeof route.query.next === "string" && route.query.next ? route.query.next : "/owner";
  window.location.assign(`${window.location.protocol}//${targetHost}${next}`);
  return true;
};

const doPostLoginRedirect = (user) => {
  if (session.canEditTenantMenu && redirectOwnerToTenantHost(user)) {
    return;
  }
  const next = typeof route.query.next === "string" ? route.query.next : "";
  if (next) {
    router.push(next);
  } else {
    router.push(fallbackRoute());
  }
};

const submit = async () => {
  fieldErrors.identifier = "";
  fieldErrors.password = "";
  error.value = "";
  if (!identifier.value.trim()) {
    fieldErrors.identifier = t("signIn.identifierRequired");
    return;
  }
  if (!password.value) {
    fieldErrors.password = t("signIn.passwordRequired");
    return;
  }
  try {
    const result = await session.signIn(identifier.value, password.value);
    if (result && result.mfaRequired) {
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
  }
};

// U4: shared post-authentication gate — if the server flagged this account as
// needing a forced password change, show that step instead of redirecting.
// Only once that step succeeds does the user reach doPostLoginRedirect.
const completeSignIn = (user) => {
  if (user && user.must_change_password) {
    pendingPostLoginUser = user;
    forcePasswordChangeRequired.value = true;
    forcePwForm.value = { current: "", next: "", confirm: "", loading: false, error: "" };
    return;
  }
  doPostLoginRedirect(user);
};

// Focus the code input when MFA step appears or when toggling backup code
watch(mfaRequired, (val) => {
  if (val) {
    nextTick(() => mfaCodeInputRef.value?.focus());
  }
});

watch(useBackupCode, (val) => {
  nextTick(() => {
    if (val) {
      mfaBackupInputRef.value?.focus();
    } else {
      mfaCodeInputRef.value?.focus();
    }
  });
});

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
  try {
    const payload = useBackupCode.value ? { backup_code: codeVal } : { code: codeVal };
    const user = await session.verifyMfa(payload);
    completeSignIn(user);
  } catch {
    mfaError.value = session.error || t("mfa.invalidCode");
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
    const user = pendingPostLoginUser;
    pendingPostLoginUser = null;
    doPostLoginRedirect(user);
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
