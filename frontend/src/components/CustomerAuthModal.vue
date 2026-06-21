<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/85 p-3 backdrop-blur-sm sm:items-center sm:p-5"
      @click.self="$emit('close')"
    >
      <div
        ref="dialogRef"
        role="dialog"
        aria-modal="true"
        aria-labelledby="customer-auth-dialog-title"
        class="ui-auth-card ui-reveal max-h-[92vh] w-full overflow-y-auto"
      >
        <!-- Header — negative margins bleed to card edge since ui-auth-card provides p-6 -->
        <div class="-mx-6 -mt-6 mb-2 flex items-center justify-between gap-3 border-b border-slate-800 px-6 py-3">
          <div>
            <p class="ui-kicker">{{ t("customerAuth.kicker") }}</p>
            <h2 id="customer-auth-dialog-title" class="ui-display text-base font-semibold text-white leading-tight">
              {{ t("customerAuth.title") }}
            </h2>
          </div>
          <button
            class="ui-btn-outline ui-press ui-touch-target gap-1.5 px-3 text-xs"
            @click="$emit('close')"
          >
            <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ t("common.close") }}
          </button>
        </div>

        <div v-if="!showWelcome" class="space-y-4">
          <p class="ui-subtle">{{ t("customerAuth.description") }}</p>

          <!-- Google One-Tap (env-gated) -->
          <div v-if="googleClientId" id="customer-google-signin" class="flex justify-center"></div>
          <div v-if="googleClientId" class="flex items-center gap-3">
            <div class="ui-divider flex-1" />
            <span class="text-xs text-slate-500">{{ t("customerAuth.or") }}</span>
            <div class="ui-divider flex-1" />
          </div>

          <!-- ── Phone entry step ── -->
          <div v-if="step === 'phone'" class="space-y-3">
            <label class="block space-y-1.5">
              <span class="text-xs text-slate-400">{{ t("customerAuth.phoneLabel") }}</span>
              <input
                v-model.trim="phone"
                type="tel"
                inputmode="tel"
                autocomplete="tel"
                maxlength="30"
                class="ui-input ui-touch-target"
                :placeholder="t('customerAuth.phonePlaceholder')"
                :disabled="requesting"
                :aria-invalid="phoneError ? 'true' : undefined"
                aria-describedby="auth-phone-error"
                aria-required="true"
                @keydown.enter.prevent="requestOtp"
              />
            </label>
            <p
              v-if="phoneError"
              id="auth-phone-error"
              class="text-xs text-red-300"
              role="alert"
            >
              {{ phoneError }}
            </p>
            <button
              class="ui-btn-primary ui-touch-target w-full gap-1.5"
              :disabled="requesting || !phone"
              @click="requestOtp"
            >
              <AppIcon v-if="!requesting" name="chat" class="h-3.5 w-3.5" aria-hidden="true" />
              {{ requesting ? t("customerAuth.sending") : t("customerAuth.sendCode") }}
            </button>
          </div>

          <!-- ── OTP verify step ── -->
          <div v-else-if="step === 'verify'" class="space-y-3">
            <p class="ui-subtle">{{ t("customerAuth.codeSentTo", { phone }) }}</p>
            <label class="block space-y-1.5">
              <span class="text-xs text-slate-400">{{ t("customerAuth.otpLabel") }}</span>
              <input
                ref="otpInputRef"
                v-model.trim="otpCode"
                type="text"
                inputmode="numeric"
                autocomplete="one-time-code"
                maxlength="6"
                class="ui-input ui-touch-target text-center text-xl font-mono tracking-widest"
                :placeholder="t('customerAuth.otpPlaceholder')"
                :disabled="verifying"
                :aria-invalid="otpError ? 'true' : undefined"
                aria-describedby="auth-otp-error"
                aria-required="true"
                @keydown.enter.prevent="verifyOtp"
              />
            </label>
            <p
              v-if="otpError"
              id="auth-otp-error"
              class="text-xs text-red-300"
              role="alert"
            >
              {{ otpError }}
            </p>
            <button
              class="ui-btn-primary ui-touch-target w-full"
              :disabled="verifying || otpCode.length < 4"
              @click="verifyOtp"
            >
              {{ verifying ? t("customerAuth.verifying") : t("customerAuth.verify") }}
            </button>
            <button
              class="ui-btn-outline ui-touch-target w-full text-xs"
              :disabled="requesting"
              @click="backToPhone"
            >
              {{ t("customerAuth.changePhone") }}
            </button>
            <button
              class="ui-press ui-touch-target w-full text-center text-xs text-slate-400 transition hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="requesting || resendSeconds > 0"
              @click="requestOtp"
            >
              {{ resendSeconds > 0 ? t("customerAuth.resendIn", { seconds: resendSeconds }) : t("customerAuth.resendCode") }}
            </button>
            <span class="sr-only" aria-live="polite" aria-atomic="true">
              {{ resendSeconds > 0 ? t("customerAuth.resendIn", { seconds: resendSeconds }) : "" }}
            </span>
          </div>

          <!-- ── Name setup step (first sign-up only) ── -->
          <div v-else-if="step === 'setup'" class="space-y-3">
            <label class="block space-y-1.5">
              <div class="space-y-0.5">
                <span class="text-sm font-semibold text-slate-100">{{ t("customerAuth.nameSetupTitle") }}</span>
                <p id="auth-name-hint" class="ui-subtle text-xs">{{ t("customerAuth.nameSetupHint") }}</p>
              </div>
              <input
                ref="nameInputRef"
                v-model.trim="setupName"
                type="text"
                autocomplete="name"
                maxlength="80"
                class="ui-input ui-touch-target"
                aria-describedby="auth-name-hint"
                aria-required="true"
                :placeholder="t('customerAuth.namePlaceholder')"
                :disabled="savingName"
                @keydown.enter.prevent="saveName"
              />
            </label>
            <button
              class="ui-btn-primary ui-touch-target w-full"
              :disabled="savingName || !setupName"
              @click="saveName"
            >
              {{ savingName ? t("customerAuth.saving") : t("customerAuth.nameSetupSave") }}
            </button>
            <button
              class="ui-press ui-touch-target w-full text-center text-xs text-slate-400 transition hover:text-slate-200"
              @click="skipName"
            >
              {{ t("customerAuth.nameSetupSkip") }}
            </button>
          </div>

          <div
            v-if="generalError"
            class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
            role="alert"
          >
            <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
            <p class="flex-1 text-sm text-red-300">{{ generalError }}</p>
          </div>
        </div>
        <div v-else class="space-y-4 py-4 text-center">
          <h3 class="ui-display text-lg font-semibold text-white">{{ t("customerAuth.welcomeTitle", { platform: PLATFORM_NAME }) }}</h3>
          <p class="ui-subtle">{{ t("customerAuth.welcomeBody") }}</p>
          <button class="ui-btn-primary ui-press w-full px-4 py-2.5 text-sm" @click="dismissWelcome">
            {{ t("customerAuth.welcomeExplore") }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from "vue";

const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');
import AppIcon from "./AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useCustomerStore } from "../stores/customer";
import api from "../lib/api";
import { PLATFORM_NAME } from "../lib/brand";

defineProps({
  initialTab: { type: String, default: "phone" }, // kept for backward compat, ignored
});

const emit = defineEmits(["close", "authenticated"]);

const { t } = useI18n();
const customerStore = useCustomerStore();

const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

const step        = ref("phone"); // 'phone' | 'verify' | 'setup'
const phone       = ref("");
const otpCode     = ref("");
const setupName   = ref("");
const requesting  = ref(false);
const verifying   = ref(false);
const savingName  = ref(false);
const phoneError  = ref("");
const otpError    = ref("");
const generalError = ref("");
const resendSeconds = ref(0);
const otpInputRef  = ref(null);
const nameInputRef = ref(null);
const dialogRef    = ref(null);
const triggerEl    = ref(null);

// First sign-in welcome (one-time). After the FIRST successful auth we show a
// brief super-app welcome instead of closing immediately; a localStorage flag
// makes it appear only once. Auth always completes first (we emit
// "authenticated" before deciding), so the welcome never blocks sign-in. If a
// parent closes the modal on "authenticated", the welcome simply doesn't show.
const WELCOME_KEY = "kepoli.customer.welcomed";
const showWelcome = ref(false);
const _alreadyWelcomed = () => {
  try { return localStorage.getItem(WELCOME_KEY) === "1"; } catch (e) { void e; return true; }
};
const finishAuth = (customer) => {
  emit("authenticated", customer);
  if (_alreadyWelcomed()) emit("close");
  else showWelcome.value = true;
};
const dismissWelcome = () => {
  try { localStorage.setItem(WELCOME_KEY, "1"); } catch (e) { void e; }
  showWelcome.value = false;
  emit("close");
};

const trapFocus = (e) => {
  // Escape closes the modal from anywhere on the page (WCAG 2.1 §4.1.3 / ARIA dialog pattern)
  if (e.key === 'Escape') { e.preventDefault(); emit('close'); return; }
  if (!dialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(dialogRef.value.querySelectorAll(FOCUSABLE));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

// Holds the verified customer while waiting for name setup
let _pendingCustomer = null;

let resendTimer = null;

const startResendCountdown = () => {
  resendSeconds.value = 60;
  clearInterval(resendTimer);
  resendTimer = setInterval(() => {
    if (--resendSeconds.value <= 0) {
      clearInterval(resendTimer);
      resendTimer = null;
    }
  }, 1000);
};

const requestOtp = async () => {
  phoneError.value = "";
  otpError.value = "";
  generalError.value = "";
  if (!phone.value) {
    phoneError.value = t("customerAuth.phoneRequired");
    return;
  }
  if (step.value === "verify") otpCode.value = "";
  requesting.value = true;
  try {
    await api.post("/customer/auth/phone/request/", { phone: phone.value });
    step.value = "verify";
    startResendCountdown();
    await nextTick();
    otpInputRef.value?.focus();
  } catch (err) {
    phoneError.value = err?.response?.data?.detail || t("customerAuth.sendError");
  } finally {
    requesting.value = false;
  }
};

const verifyOtp = async () => {
  otpError.value = "";
  generalError.value = "";
  if (!otpCode.value) {
    otpError.value = t("customerAuth.otpRequired");
    return;
  }
  verifying.value = true;
  try {
    const res = await api.post("/customer/auth/phone/verify/", {
      phone: phone.value,
      code: otpCode.value,
    });
    const customer = res.data.customer;
    customerStore.setCustomer(customer);
    _linkPendingReferral();
    // First-time sign-up: no name yet → go to name setup step
    if (!customer.name) {
      _pendingCustomer = customer;
      step.value = "setup";
      await nextTick();
      nameInputRef.value?.focus();
    } else {
      finishAuth(customer);
    }
  } catch (err) {
    const code   = err?.response?.data?.code;
    const detail = err?.response?.data?.detail;
    if (code === "otp_expired" || code === "too_many_attempts") {
      otpError.value = code === "otp_expired" ? t("customerAuth.otpExpired") : t("customerAuth.tooManyAttempts");
      step.value = "phone";
    } else if (code === "invalid_code") {
      otpError.value = t("customerAuth.otpInvalid");
    } else {
      otpError.value = detail || t("customerAuth.verifyError");
    }
  } finally {
    verifying.value = false;
  }
};

// Auto-submit OTP once the customer has typed all 6 digits — no extra tap needed.
// The Verify button stays visible for paste / retry flows.
watch(otpCode, (val) => {
  if (step.value === 'verify' && val.length === 6 && !verifying.value) {
    verifyOtp();
  }
});

const saveName = async () => {
  if (!setupName.value || savingName.value) return;
  savingName.value = true;
  try {
    const res = await api.patch("/customer/profile/", { name: setupName.value });
    customerStore.setCustomer(res.data.customer);
    finishAuth(res.data.customer);
  } catch {
    // Save failed — still close with the original customer
    finishAuth(_pendingCustomer);
  } finally {
    savingName.value = false;
  }
};

const skipName = () => {
  finishAuth(_pendingCustomer);
};

const backToPhone = () => {
  step.value    = "phone";
  otpCode.value = "";
  otpError.value = "";
};

// After any successful auth, silently link a pending referral code if one was
// stored by App.vue when the user landed on the site via a referral link.
const _linkPendingReferral = async () => {
  let code;
  try { code = localStorage.getItem("pending_referral_code"); } catch (e) { void e; }
  if (!code) return;
  try {
    await api.post("/customer/link-referral/", { code });
  } catch (e) {
    void e; // Non-fatal — already linked or invalid code; swallow silently.
  } finally {
    try { localStorage.removeItem("pending_referral_code"); } catch (e) { void e; }
  }
};

// ── Google One-Tap ─────────────────────────────────────────────────────────────
let googleScriptEl = null;

const handleGoogleCredential = async (response) => {
  generalError.value = "";
  try {
    const res = await api.post("/customer/auth/google/", { credential: response.credential });
    customerStore.setCustomer(res.data.customer);
    _linkPendingReferral();
    finishAuth(res.data.customer);
  } catch (err) {
    generalError.value = err?.response?.data?.detail || t("customerAuth.googleError");
  }
};

const initGoogleOneTap = () => {
  if (!googleClientId || typeof window === "undefined") return;
  if (!window.google?.accounts?.id) return;
  window.google.accounts.id.initialize({
    client_id: googleClientId,
    callback: handleGoogleCredential,
    context: "signin",
  });
  const container = document.getElementById("customer-google-signin");
  if (container) {
    window.google.accounts.id.renderButton(container, {
      theme: "filled_black",
      size: "large",
      width: container.offsetWidth || 300,
      text: "signin_with",
      shape: "pill",
    });
  }
};

onMounted(async () => {
  // Save the element that triggered the dialog so we can restore focus on close
  triggerEl.value = document.activeElement;
  document.addEventListener('keydown', trapFocus);
  await nextTick();
  // Move focus into the dialog — first focusable element (phone input or close button)
  dialogRef.value?.querySelector(FOCUSABLE)?.focus();

  if (!googleClientId) return;
  if (!window.google?.accounts?.id) {
    await new Promise((resolve) => {
      googleScriptEl = document.createElement("script");
      googleScriptEl.src = "https://accounts.google.com/gsi/client";
      googleScriptEl.async = true;
      googleScriptEl.defer = true;
      googleScriptEl.onload = resolve;
      googleScriptEl.onerror = resolve;
      document.head.appendChild(googleScriptEl);
    });
  }
  await nextTick();
  initGoogleOneTap();
});

onUnmounted(() => {
  document.removeEventListener('keydown', trapFocus);
  clearInterval(resendTimer);
  // Restore focus to the element that opened this dialog (ARIA dialog pattern)
  triggerEl.value?.focus();
  try { window.google?.accounts?.id?.cancel(); } catch { /* best-effort: ignore failures */ }
});
</script>
