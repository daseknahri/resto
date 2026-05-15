<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/85 p-3 backdrop-blur-sm sm:items-center sm:p-5"
      @click.self="$emit('close')"
    >
      <div class="w-full max-w-md rounded-2xl border border-slate-700/70 bg-slate-950 shadow-2xl shadow-black/50">
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
          <!-- Description -->
          <p class="text-sm text-slate-400">{{ t("customerAuth.description") }}</p>

          <!-- Google One-Tap (env-gated) -->
          <div v-if="googleClientId" id="customer-google-signin" class="flex justify-center"></div>

          <div v-if="googleClientId" class="flex items-center gap-3">
            <div class="flex-1 border-t border-slate-800" />
            <span class="text-xs text-slate-500">{{ t("customerAuth.or") }}</span>
            <div class="flex-1 border-t border-slate-800" />
          </div>

          <!-- Phone OTP flow -->
          <div v-if="otpStep === 'phone'" class="space-y-3">
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
                :disabled="requestingOtp"
                @keydown.enter.prevent="requestOtp"
              />
              <p v-if="phoneError" class="text-xs text-red-300">{{ phoneError }}</p>
            </label>
            <button
              class="ui-btn-primary w-full justify-center"
              :disabled="requestingOtp || !phone"
              @click="requestOtp"
            >
              <AppIcon v-if="!requestingOtp" name="chat" class="h-3.5 w-3.5" />
              {{ requestingOtp ? t("customerAuth.sending") : t("customerAuth.sendCode") }}
            </button>
          </div>

          <!-- OTP verification flow -->
          <div v-else-if="otpStep === 'verify'" class="space-y-3">
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
                :disabled="verifyingOtp"
                @keydown.enter.prevent="verifyOtp"
              />
              <p v-if="otpError" class="text-xs text-red-300">{{ otpError }}</p>
            </label>
            <label v-if="!customerStore.isAuthenticated" class="block space-y-1">
              <span class="text-xs text-slate-400">{{ t("customerAuth.nameOptional") }}</span>
              <input
                v-model.trim="name"
                type="text"
                autocomplete="name"
                maxlength="80"
                class="ui-input"
                :placeholder="t('customerAuth.namePlaceholder')"
                :disabled="verifyingOtp"
              />
            </label>
            <button
              class="ui-btn-primary w-full justify-center"
              :disabled="verifyingOtp || otpCode.length < 4"
              @click="verifyOtp"
            >
              {{ verifyingOtp ? t("customerAuth.verifying") : t("customerAuth.verify") }}
            </button>
            <button class="ui-btn-outline w-full justify-center text-xs" :disabled="requestingOtp" @click="backToPhone">
              {{ t("customerAuth.changePhone") }}
            </button>
          </div>

          <!-- General error -->
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

const emit = defineEmits(["close", "authenticated"]);

const { t } = useI18n();
const customerStore = useCustomerStore();

const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

// Phone OTP state
const otpStep = ref("phone"); // 'phone' | 'verify'
const phone = ref("");
const otpCode = ref("");
const name = ref("");
const requestingOtp = ref(false);
const verifyingOtp = ref(false);
const phoneError = ref("");
const otpError = ref("");
const generalError = ref("");
const otpInputRef = ref(null);

const requestOtp = async () => {
  phoneError.value = "";
  generalError.value = "";
  if (!phone.value) {
    phoneError.value = t("customerAuth.phoneRequired");
    return;
  }
  requestingOtp.value = true;
  try {
    await api.post("/customer/auth/phone/request/", { phone: phone.value });
    otpStep.value = "verify";
    await nextTick();
    otpInputRef.value?.focus();
  } catch (err) {
    const detail = err?.response?.data?.detail;
    phoneError.value = detail || t("customerAuth.sendError");
  } finally {
    requestingOtp.value = false;
  }
};

const verifyOtp = async () => {
  otpError.value = "";
  generalError.value = "";
  if (!otpCode.value) {
    otpError.value = t("customerAuth.otpRequired");
    return;
  }
  verifyingOtp.value = true;
  try {
    const res = await api.post("/customer/auth/phone/verify/", {
      phone: phone.value,
      code: otpCode.value,
      name: name.value,
    });
    customerStore.setCustomer(res.data.customer);
    emit("authenticated", res.data.customer);
    emit("close");
  } catch (err) {
    const code = err?.response?.data?.code;
    const detail = err?.response?.data?.detail;
    if (code === "otp_expired") {
      otpError.value = t("customerAuth.otpExpired");
      otpStep.value = "phone";
    } else if (code === "invalid_code") {
      otpError.value = t("customerAuth.otpInvalid");
    } else if (code === "too_many_attempts") {
      otpError.value = t("customerAuth.tooManyAttempts");
      otpStep.value = "phone";
    } else {
      otpError.value = detail || t("customerAuth.verifyError");
    }
  } finally {
    verifyingOtp.value = false;
  }
};

const backToPhone = () => {
  otpStep.value = "phone";
  otpCode.value = "";
  otpError.value = "";
};

// ── Google One-Tap ────────────────────────────────────────────────────────────
let googleScriptEl = null;

const handleGoogleCredential = async (response) => {
  generalError.value = "";
  try {
    const res = await api.post("/customer/auth/google/", { credential: response.credential });
    customerStore.setCustomer(res.data.customer);
    emit("authenticated", res.data.customer);
    emit("close");
  } catch (err) {
    const detail = err?.response?.data?.detail;
    generalError.value = detail || t("customerAuth.googleError");
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
  // Load Google Identity Services script if not already loaded
  if (!window.google?.accounts?.id) {
    await new Promise((resolve) => {
      googleScriptEl = document.createElement("script");
      googleScriptEl.src = "https://accounts.google.com/gsi/client";
      googleScriptEl.async = true;
      googleScriptEl.defer = true;
      googleScriptEl.onload = resolve;
      googleScriptEl.onerror = resolve; // don't block if GSI unavailable
      document.head.appendChild(googleScriptEl);
    });
  }
  await nextTick();
  initGoogleOneTap();
});

onUnmounted(() => {
  // Cancel any pending One-Tap prompt
  try {
    if (window.google?.accounts?.id) {
      window.google.accounts.id.cancel();
    }
  } catch {
    // ignore
  }
});
</script>
