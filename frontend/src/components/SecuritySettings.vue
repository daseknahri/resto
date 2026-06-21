<template>
  <section class="space-y-6">
    <div class="ui-section-band">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-300">{{ t("mfa.sectionTitle") }}</h2>
      <p class="mt-1 text-sm text-slate-400">{{ t("mfa.sectionDescription") }}</p>
    </div>

    <!-- ── Loading state ── -->
    <div v-if="initialLoading" class="flex items-center gap-2 text-sm text-slate-400" aria-live="polite">
      <svg aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
      {{ t("common.loading") }}
    </div>

    <template v-else>
      <!-- ── Enrolled state ── -->
      <template v-if="enrolled">
        <div class="flex items-start gap-4 rounded-2xl border border-emerald-500/25 bg-emerald-500/8 px-4 py-4">
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" class="mt-0.5 h-5 w-5 shrink-0 text-emerald-400"><path fill-rule="evenodd" d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z" clip-rule="evenodd"/></svg>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold text-emerald-300">{{ t("mfa.enabledBadge") }}</p>
            <p class="mt-0.5 text-xs text-slate-400">{{ t("mfa.enabledHint") }}</p>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 transition hover:bg-red-500/20 hover:text-red-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/60"
            @click="startDisable"
          >
            {{ t("mfa.disableBtn") }}
          </button>
        </div>

        <!-- Disable confirmation form -->
        <div v-if="showDisable" class="space-y-4 rounded-2xl border border-slate-700/60 bg-slate-900/60 px-4 py-4">
          <p class="text-sm font-semibold text-slate-200">{{ t("mfa.disableConfirmTitle") }}</p>
          <p class="text-xs text-slate-400">{{ t("mfa.disableConfirmHint") }}</p>
          <label class="block space-y-1.5 text-sm font-medium text-slate-200">
            {{ t("mfa.disablePasswordLabel") }}
            <input
              ref="disableInputRef"
              v-model="disableCredential"
              type="password"
              autocomplete="current-password"
              class="ui-input mt-1 font-normal"
              :class="disableError ? 'border-red-400' : ''"
              :aria-invalid="disableError ? 'true' : undefined"
              :aria-describedby="disableError ? 'mfa-disable-error' : undefined"
              :placeholder="t('mfa.disablePasswordPlaceholder')"
              aria-required="true"
              @input="disableError = ''"
            />
            <p v-if="disableError" id="mfa-disable-error" class="text-xs font-normal text-red-300" role="alert">{{ disableError }}</p>
          </label>
          <div class="flex gap-2">
            <button
              type="button"
              :disabled="disabling"
              :aria-busy="disabling"
              class="inline-flex items-center gap-2 rounded-xl border border-red-500/40 bg-red-500/15 px-4 py-2 text-sm font-medium text-red-300 transition hover:bg-red-500/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/60 disabled:opacity-60"
              @click="confirmDisable"
            >
              <svg v-if="disabling" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ disabling ? t("mfa.disabling") : t("mfa.disableConfirmBtn") }}
            </button>
            <button type="button" class="rounded-xl border border-slate-700/60 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500/60" @click="cancelDisable">{{ t("common.cancel") }}</button>
          </div>
        </div>
      </template>

      <!-- ── Not enrolled state ── -->
      <template v-else>
        <!-- Step 0: idle (not started) -->
        <div v-if="step === 'idle'" class="space-y-4">
          <div class="flex items-start gap-4 rounded-2xl border border-slate-700/60 bg-slate-900/40 px-4 py-4">
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" class="mt-0.5 h-5 w-5 shrink-0 text-slate-400"><path fill-rule="evenodd" d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z" clip-rule="evenodd"/></svg>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-slate-200">{{ t("mfa.notEnabledTitle") }}</p>
              <p class="mt-0.5 text-xs text-slate-400">{{ t("mfa.notEnabledHint") }}</p>
            </div>
            <button
              type="button"
              :disabled="setupLoading"
              :aria-busy="setupLoading"
              class="ui-btn-primary ui-press shrink-0 inline-flex items-center gap-2 text-sm disabled:opacity-60"
              @click="startSetup"
            >
              <svg v-if="setupLoading" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ t("mfa.enableBtn") }}
            </button>
          </div>
          <div v-if="setupError" role="alert" class="flex items-start gap-2.5 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
            <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm text-red-300">{{ setupError }}</p>
          </div>
        </div>

        <!-- Step 1: QR scan + code entry -->
        <div v-else-if="step === 'scan'" class="space-y-5">
          <div class="space-y-1">
            <p class="text-sm font-semibold text-slate-200">{{ t("mfa.scanTitle") }}</p>
            <p class="text-xs text-slate-400">{{ t("mfa.scanHint") }}</p>
          </div>

          <!-- QR code rendered from provisioning_uri via qrcode lib -->
          <div class="flex justify-center">
            <div class="rounded-xl bg-white p-3">
              <img
                v-if="qrDataUrl"
                :src="qrDataUrl"
                :alt="t('mfa.qrAlt')"
                width="160"
                height="160"
                class="block"
              />
              <div v-else class="h-40 w-40 flex items-center justify-center text-slate-500 text-xs">
                {{ t("mfa.qrLoading") }}
              </div>
            </div>
          </div>

          <!-- Manual secret for copy-entry -->
          <div class="space-y-1.5">
            <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">{{ t("mfa.manualEntry") }}</p>
            <div class="flex items-center gap-2">
              <code class="flex-1 rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-xs text-slate-200 font-mono break-all select-all">{{ setupSecret }}</code>
              <button
                type="button"
                class="shrink-0 rounded-lg border border-slate-700/60 px-3 py-1.5 text-xs text-slate-300 transition hover:bg-slate-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500/60"
                :aria-label="t('mfa.copySecretAriaLabel')"
                @click="copySecret"
              >
                {{ secretCopied ? t("mfa.copied") : t("common.copy") }}
              </button>
            </div>
          </div>

          <!-- Confirm code input -->
          <label class="block space-y-1.5 text-sm font-medium text-slate-200">
            {{ t("mfa.confirmCodeLabel") }}
            <input
              ref="confirmCodeInputRef"
              v-model="confirmCode"
              type="text"
              inputmode="numeric"
              autocomplete="one-time-code"
              maxlength="6"
              class="ui-input mt-1 font-normal tracking-[0.25em] text-center"
              :class="confirmError ? 'border-red-400' : ''"
              :aria-invalid="confirmError ? 'true' : undefined"
              :aria-describedby="confirmError ? 'mfa-confirm-error' : undefined"
              :placeholder="t('mfa.codePlaceholder')"
              aria-required="true"
              @input="confirmError = ''"
            />
            <p v-if="confirmError" id="mfa-confirm-error" class="text-xs font-normal text-red-300" role="alert">{{ confirmError }}</p>
          </label>

          <div class="flex gap-2">
            <button
              type="button"
              :disabled="confirming"
              :aria-busy="confirming"
              class="ui-btn-primary ui-press inline-flex flex-1 items-center justify-center gap-2 text-sm disabled:opacity-60"
              @click="confirmSetup"
            >
              <svg v-if="confirming" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ confirming ? t("mfa.confirming") : t("mfa.confirmBtn") }}
            </button>
            <button type="button" class="rounded-xl border border-slate-700/60 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500/60" @click="cancelSetup">{{ t("common.cancel") }}</button>
          </div>
        </div>

        <!-- Step 2: Backup codes (shown once after confirm) -->
        <div v-else-if="step === 'backup'" class="space-y-5">
          <div class="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/8 px-4 py-4">
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" class="mt-0.5 h-5 w-5 shrink-0 text-amber-400"><path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0V5.75A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-amber-300">{{ t("mfa.backupCodesTitle") }}</p>
              <p class="mt-0.5 text-xs text-slate-300">{{ t("mfa.backupCodesHint") }}</p>
            </div>
          </div>

          <div class="rounded-2xl border border-slate-700/60 bg-slate-900/60 p-4">
            <ul class="grid grid-cols-2 gap-2" :aria-label="t('mfa.backupCodesListLabel')">
              <li
                v-for="code in backupCodes"
                :key="code"
                class="rounded-lg bg-slate-800/60 px-3 py-2 text-center font-mono text-sm text-slate-200 select-all"
              >
                {{ code }}
              </li>
            </ul>
          </div>

          <button
            type="button"
            class="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-700/60 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500/60"
            @click="copyBackupCodes"
          >
            {{ backupCodesCopied ? t("mfa.copied") : t("mfa.copyBackupCodes") }}
          </button>

          <div class="flex items-start gap-2">
            <input
              id="mfa-saved-confirm"
              v-model="savedConfirmed"
              type="checkbox"
              class="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-800 focus:ring-2 focus:ring-emerald-500/60"
            />
            <label for="mfa-saved-confirm" class="text-sm text-slate-300 cursor-pointer">
              {{ t("mfa.savedConfirmLabel") }}
            </label>
          </div>

          <button
            type="button"
            :disabled="!savedConfirmed"
            class="ui-btn-primary ui-press inline-flex w-full items-center justify-center gap-2 text-sm disabled:opacity-40"
            @click="finishSetup"
          >
            {{ t("mfa.doneBtn") }}
          </button>
        </div>
      </template>
    </template>
  </section>
</template>

<script setup>
import { nextTick, onMounted, ref } from "vue";
import api from "../lib/api";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();

// ── state ──────────────────────────────────────────────────────────────────
const initialLoading = ref(true);
const enrolled = ref(false);
const step = ref("idle"); // 'idle' | 'scan' | 'backup'

// setup flow
const setupLoading = ref(false);
const setupError = ref("");
const setupSecret = ref("");
const qrDataUrl = ref("");
const confirmCode = ref("");
const confirmError = ref("");
const confirming = ref(false);
const secretCopied = ref(false);
const confirmCodeInputRef = ref(null);

// backup codes
const backupCodes = ref([]);
const backupCodesCopied = ref(false);
const savedConfirmed = ref(false);

// disable flow
const showDisable = ref(false);
const disableCredential = ref("");
const disableError = ref("");
const disabling = ref(false);
const disableInputRef = ref(null);

// ── helpers ────────────────────────────────────────────────────────────────
const extractError = (err, fallback) => {
  const data = err?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.non_field_errors) && data.non_field_errors.length) return String(data.non_field_errors[0]);
  if (typeof data === "string" && data.trim()) return data;
  return fallback;
};

const generateQr = async (uri) => {
  if (!uri) return;
  try {
    const { default: QRCode } = await import("qrcode");
    qrDataUrl.value = await QRCode.toDataURL(uri, { width: 160, margin: 1 });
  } catch {
    qrDataUrl.value = "";
  }
};

// ── enrollment probe ───────────────────────────────────────────────────────
// GET /api/mfa/status/ is a pure read: no device is created, no side effects.
onMounted(async () => {
  try {
    const { data } = await api.get("/mfa/status/");
    enrolled.value = data?.enrolled === true;
  } catch {
    // Network / auth error — leave enrolled=false; the user can still try to enable.
    enrolled.value = false;
  } finally {
    initialLoading.value = false;
  }
});

// ── setup flow ─────────────────────────────────────────────────────────────
const startSetup = async () => {
  setupError.value = "";
  setupLoading.value = true;
  try {
    const { data } = await api.post("/mfa/setup/");
    setupSecret.value = data.secret || "";
    await generateQr(data.provisioning_uri);
    step.value = "scan";
    nextTick(() => confirmCodeInputRef.value?.focus());
  } catch (err) {
    if (err?.response?.status === 409) {
      enrolled.value = true;
      return;
    }
    if (err?.response?.status === 403) {
      setupError.value = t("mfa.errorForbidden");
      return;
    }
    setupError.value = extractError(err, t("mfa.setupFailed"));
  } finally {
    setupLoading.value = false;
  }
};

const cancelSetup = () => {
  step.value = "idle";
  setupError.value = "";
  confirmCode.value = "";
  confirmError.value = "";
  setupSecret.value = "";
  qrDataUrl.value = "";
};

const confirmSetup = async () => {
  confirmError.value = "";
  if (!confirmCode.value.trim()) {
    confirmError.value = t("mfa.codeRequired");
    return;
  }
  confirming.value = true;
  try {
    const { data } = await api.post("/mfa/confirm/", { code: confirmCode.value.trim() });
    backupCodes.value = data.backup_codes || [];
    step.value = "backup";
  } catch (err) {
    if (err?.response?.status === 409) {
      confirmError.value = t("mfa.errorAlreadyConfirmed");
      return;
    }
    confirmError.value = extractError(err, t("mfa.confirmFailed"));
  } finally {
    confirming.value = false;
  }
};

const copySecret = async () => {
  try {
    await navigator.clipboard.writeText(setupSecret.value);
    secretCopied.value = true;
    setTimeout(() => { secretCopied.value = false; }, 2000);
  } catch {
    // silently fail — clipboard may be unavailable
  }
};

// ── backup codes step ──────────────────────────────────────────────────────
const copyBackupCodes = async () => {
  try {
    await navigator.clipboard.writeText(backupCodes.value.join("\n"));
    backupCodesCopied.value = true;
    setTimeout(() => { backupCodesCopied.value = false; }, 2000);
  } catch {
    // silently fail
  }
};

const finishSetup = () => {
  enrolled.value = true;
  step.value = "idle";
  backupCodes.value = [];
  savedConfirmed.value = false;
  confirmCode.value = "";
  setupSecret.value = "";
  qrDataUrl.value = "";
};

// ── disable flow ───────────────────────────────────────────────────────────
const startDisable = () => {
  showDisable.value = true;
  disableCredential.value = "";
  disableError.value = "";
  nextTick(() => disableInputRef.value?.focus());
};

const cancelDisable = () => {
  showDisable.value = false;
  disableCredential.value = "";
  disableError.value = "";
};

const confirmDisable = async () => {
  disableError.value = "";
  if (!disableCredential.value.trim()) {
    disableError.value = t("mfa.disableCredentialRequired");
    return;
  }
  disabling.value = true;
  try {
    await api.post("/mfa/disable/", { password: disableCredential.value });
    enrolled.value = false;
    showDisable.value = false;
    disableCredential.value = "";
  } catch (err) {
    disableError.value = extractError(err, t("mfa.disableFailed"));
  } finally {
    disabling.value = false;
  }
};
</script>
