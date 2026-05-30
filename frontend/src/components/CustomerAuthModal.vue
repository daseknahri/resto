<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/85 p-3 backdrop-blur-sm sm:items-center sm:p-5"
      @click.self="$emit('close')"
      @keydown.esc.window="$emit('close')"
    >
      <div role="dialog" aria-modal="true" class="w-full max-w-md rounded-2xl border border-slate-700/70 bg-slate-950 shadow-2xl shadow-black/50">
        <!-- Header -->
        <div class="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
          <div>
            <p class="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              {{ t("customerAuth.kicker") }}
            </p>
            <h2 class="text-base font-semibold text-slate-100">{{ t("customerAuth.title") }}</h2>
          </div>
          <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="$emit('close')">
            <AppIcon name="close" class="h-3.5 w-3.5" />
            {{ t("common.close") }}
          </button>
        </div>

        <div class="space-y-4 p-4">
          <p class="text-sm text-slate-400">{{ t("customerAuth.description") }}</p>

          <!-- Google One-Tap (env-gated) -->
          <div v-if="googleClientId" id="customer-google-signin" class="flex justify-center"></div>
          <div v-if="googleClientId" class="flex items-center gap-3">
            <div class="flex-1 border-t border-slate-800" />
            <span class="text-xs text-slate-500">{{ t("customerAuth.or") }}</span>
            <div class="flex-1 border-t border-slate-800" />
          </div>

          <!-- ── Phone entry step ── -->
          <div v-if="step === 'phone'" class="space-y-3">
            <label class="block space-y-1">
              <span class="text-xs text-slate-400">{{ t("customerAuth.phoneLabel") }}</span>
              <input
                v-model.trim="phone"
                type="tel"
                inputmode="tel"
                autocomplete="tel"
                maxlength="30"
                class="ui-input"
                :placeholder="t('customerAuth.phonePlaceholder')"
                :disabled="requesting"
                @keydown.enter.prevent="requestOtp"
              />
              <p v-if="phoneError" class="text-xs text-red-300">{{ phoneError }}</p>
            </label>
            <button
              class="ui-btn-primary w-full justify-center"
              :disabled="requesting || !phone"
              @click="requestOtp"
            >
              <AppIcon v-if="!requesting" name="chat" class="h-3.5 w-3.5" />
              {{ requesting ? t("customerAuth.sending") : t("customerAuth.sendCode") }}
            </button>
          </div>

          <!-- ── OTP verify step ── -->
          <div v-else-if="step === 'verify'" class="space-y-3">
            <p class="text-sm text-slate-300">
              {{ t("customerAuth.codeSentTo", { phone }) }}
            </p>
            <label class="block space-y-1">
              <span class="text-xs text-slate-400">{{ t("customerAuth.otpLabel") }}</span>
              <input
                ref="otpInputRef"
                v-model.trim="otpCode"
                type="text"
                inputmode="numeric"
                autocomplete="one-time-code"
                maxlength="6"
                class="ui-input text-center text-xl font-mono tracking-widest"
                :placeholder="t('customerAuth.otpPlaceholder')"
                :disabled="verifying"
                @keydown.enter.prevent="verifyOtp"
              />
              <p v-if="otpError" class="text-xs text-red-300">{{ otpError }}</p>
            </label>
            <button
              class="ui-btn-primary w-full justify-center"
              :disabled="verifying || otpCode.length < 4"
              @click="verifyOtp"
            >
              {{ verifying ? t("customerAuth.verifying") : t("customerAuth.verify") }}
            </button>
            <button
              class="ui-btn-outline w-full justify-center text-xs"
              :disabled="requesting"
              @click="backToPhone"
            >
              {{ t("customerAuth.changePhone") }}
            </button>
            <button
              class="text-xs text-slate-400 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50 transition"
              :disabled="requesting || resendSeconds > 0"
              @click="requestOtp"
            >
              {{ resendSeconds > 0 ? t("customerAuth.resendIn", { seconds: resendSeconds }) : t("customerAuth.resendCode") }}
            </button>
          </div>

          <!-- ── Name setup step (first sign-up only) ── -->
          <div v-else-if="step === 'setup'" class="space-y-3">
            <div class="space-y-0.5">
              <p class="text-sm font-semibold text-slate-100">{{ t("customerAuth.nameSetupTitle") }}</p>
              <p class="text-xs text-slate-400">{{ t("customerAuth.nameSetupHint") }}</p>
            </div>
            <input
              ref="nameInputRef"
              v-model.trim="setupName"
              type="text"
              autocomplete="name"
              maxlength="80"
              class="ui-input"
              :placeholder="t('customerAuth.namePlaceholder')"
              :disabled="savingName"
              @keydown.enter.prevent="saveName"
            />
            <button
              class="ui-btn-primary w-full justify-center"
              :disabled="savingName || !setupName"
              @click="saveName"
            >
              {{ savingName ? t("customerAuth.saving") : t("customerAuth.nameSetupSave") }}
            </button>
            <button
              class="text-xs text-slate-400 hover:text-slate-200 transition w-full text-center"
              @click="skipName"
            >
              {{ t("customerAuth.nameSetupSkip") }}
            </button>
          </div>

          <p v-if="generalError" class="text-xs text-red-300">{{ generalError }}</p>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref } from "vue";
import AppIcon from "./AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useCustomerStore } from "../stores/customer";
import api from "../lib/api";

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
    // First-time sign-up: no name yet → go to name setup step
    if (!customer.name) {
      _pendingCustomer = customer;
      step.value = "setup";
      await nextTick();
      nameInputRef.value?.focus();
    } else {
      emit("authenticated", customer);
      emit("close");
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

const saveName = async () => {
  if (!setupName.value || savingName.value) return;
  savingName.value = true;
  try {
    const res = await api.patch("/customer/profile/", { name: setupName.value });
    customerStore.setCustomer(res.data.customer);
    emit("authenticated", res.data.customer);
    emit("close");
  } catch {
    // Save failed — still close with the original customer
    emit("authenticated", _pendingCustomer);
    emit("close");
  } finally {
    savingName.value = false;
  }
};

const skipName = () => {
  emit("authenticated", _pendingCustomer);
  emit("close");
};

const backToPhone = () => {
  step.value    = "phone";
  otpCode.value = "";
  otpError.value = "";
};

// ── Google One-Tap ─────────────────────────────────────────────────────────────
let googleScriptEl = null;

const handleGoogleCredential = async (response) => {
  generalError.value = "";
  try {
    const res = await api.post("/customer/auth/google/", { credential: response.credential });
    customerStore.setCustomer(res.data.customer);
    emit("authenticated", res.data.customer);
    emit("close");
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
  clearInterval(resendTimer);
  try { window.google?.accounts?.id?.cancel(); } catch {}
});
</script>
