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

          <!-- Tab switcher: Phone | Email -->
          <div class="flex rounded-full border border-slate-700/70 bg-slate-900/50 p-0.5">
            <button
              class="flex-1 rounded-full px-3 py-1.5 text-xs font-semibold transition"
              :class="activeTab === 'phone' ? 'bg-[var(--color-secondary)] text-slate-950' : 'text-slate-400 hover:text-slate-200'"
              @click="switchTab('phone')"
            >
              {{ t("customerAuth.tabPhone") }}
            </button>
            <button
              class="flex-1 rounded-full px-3 py-1.5 text-xs font-semibold transition"
              :class="activeTab === 'email' ? 'bg-[var(--color-secondary)] text-slate-950' : 'text-slate-400 hover:text-slate-200'"
              @click="switchTab('email')"
            >
              {{ t("customerAuth.tabEmail") }}
            </button>
          </div>

          <!-- ── PHONE TAB ── -->
          <template v-if="activeTab === 'phone'">
            <!-- Phone entry step -->
            <div v-if="phoneStep === 'phone'" class="space-y-3">
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

            <!-- Phone OTP verify step -->
            <div v-else-if="phoneStep === 'verify'" class="space-y-3">
              <p class="text-sm text-slate-300">
                {{ t("customerAuth.codeSentTo", { phone }) }}
              </p>
              <label class="block space-y-1">
                <span class="text-xs text-slate-400">{{ t("customerAuth.otpLabel") }}</span>
                <input
                  ref="phoneOtpInputRef"
                  v-model.trim="phoneOtpCode"
                  type="text"
                  inputmode="numeric"
                  autocomplete="one-time-code"
                  maxlength="6"
                  class="ui-input text-center text-xl font-mono tracking-widest"
                  :placeholder="t('customerAuth.otpPlaceholder')"
                  :disabled="verifyingOtp"
                  @keydown.enter.prevent="verifyPhoneOtp"
                />
                <p v-if="phoneOtpError" class="text-xs text-red-300">{{ phoneOtpError }}</p>
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
                :disabled="verifyingOtp || phoneOtpCode.length < 4"
                @click="verifyPhoneOtp"
              >
                {{ verifyingOtp ? t("customerAuth.verifying") : t("customerAuth.verify") }}
              </button>
              <button class="ui-btn-outline w-full justify-center text-xs" :disabled="requestingOtp" @click="backToPhone">
                {{ t("customerAuth.changePhone") }}
              </button>
            </div>
          </template>

          <!-- ── EMAIL TAB ── -->
          <template v-else-if="activeTab === 'email'">
            <!-- Email entry step -->
            <div v-if="emailStep === 'email'" class="space-y-3">
              <label class="block space-y-1">
                <span class="text-xs text-slate-400">{{ t("customerAuth.emailLabel") }}</span>
                <input
                  v-model.trim="email"
                  type="email"
                  inputmode="email"
                  autocomplete="email"
                  maxlength="254"
                  class="ui-input"
                  :placeholder="t('customerAuth.emailPlaceholder')"
                  :disabled="requestingEmailOtp"
                  @keydown.enter.prevent="requestEmailOtp"
                />
                <p v-if="emailError" class="text-xs text-red-300">{{ emailError }}</p>
              </label>
              <button
                class="ui-btn-primary w-full justify-center"
                :disabled="requestingEmailOtp || !email"
                @click="requestEmailOtp"
              >
                <AppIcon v-if="!requestingEmailOtp" name="chat" class="h-3.5 w-3.5" />
                {{ requestingEmailOtp ? t("customerAuth.sending") : t("customerAuth.sendCode") }}
              </button>
            </div>

            <!-- Email OTP verify step -->
            <div v-else-if="emailStep === 'verify'" class="space-y-3">
              <p class="text-sm text-slate-300">
                {{ t("customerAuth.emailCodeSentTo", { email }) }}
              </p>
              <label class="block space-y-1">
                <span class="text-xs text-slate-400">{{ t("customerAuth.otpLabel") }}</span>
                <input
                  ref="emailOtpInputRef"
                  v-model.trim="emailOtpCode"
                  type="text"
                  inputmode="numeric"
                  autocomplete="one-time-code"
                  maxlength="6"
                  class="ui-input text-center text-xl font-mono tracking-widest"
                  :placeholder="t('customerAuth.otpPlaceholder')"
                  :disabled="verifyingEmailOtp"
                  @keydown.enter.prevent="verifyEmailOtp"
                />
                <p v-if="emailOtpError" class="text-xs text-red-300">{{ emailOtpError }}</p>
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
                  :disabled="verifyingEmailOtp"
                />
              </label>
              <button
                class="ui-btn-primary w-full justify-center"
                :disabled="verifyingEmailOtp || emailOtpCode.length < 4"
                @click="verifyEmailOtp"
              >
                {{ verifyingEmailOtp ? t("customerAuth.verifying") : t("customerAuth.verify") }}
              </button>
              <button class="ui-btn-outline w-full justify-center text-xs" :disabled="requestingEmailOtp" @click="backToEmail">
                {{ t("customerAuth.useEmail") }}
              </button>
            </div>
          </template>

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

// Tab state
const activeTab = ref("phone"); // 'phone' | 'email'

// Shared name field
const name = ref("");

// General error
const generalError = ref("");

// ── Phone OTP state ───────────────────────────────────────────────────────────
const phoneStep = ref("phone"); // 'phone' | 'verify'
const phone = ref("");
const phoneOtpCode = ref("");
const requestingOtp = ref(false);
const verifyingOtp = ref(false);
const phoneError = ref("");
const phoneOtpError = ref("");
const phoneOtpInputRef = ref(null);

// ── Email OTP state ───────────────────────────────────────────────────────────
const emailStep = ref("email"); // 'email' | 'verify'
const email = ref("");
const emailOtpCode = ref("");
const requestingEmailOtp = ref(false);
const verifyingEmailOtp = ref(false);
const emailError = ref("");
const emailOtpError = ref("");
const emailOtpInputRef = ref(null);

const switchTab = (tab) => {
  activeTab.value = tab;
  generalError.value = "";
};

// ── Phone OTP flow ────────────────────────────────────────────────────────────
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
    phoneStep.value = "verify";
    await nextTick();
    phoneOtpInputRef.value?.focus();
  } catch (err) {
    const detail = err?.response?.data?.detail;
    phoneError.value = detail || t("customerAuth.sendError");
  } finally {
    requestingOtp.value = false;
  }
};

const verifyPhoneOtp = async () => {
  phoneOtpError.value = "";
  generalError.value = "";
  if (!phoneOtpCode.value) {
    phoneOtpError.value = t("customerAuth.otpRequired");
    return;
  }
  verifyingOtp.value = true;
  try {
    const res = await api.post("/customer/auth/phone/verify/", {
      phone: phone.value,
      code: phoneOtpCode.value,
      name: name.value,
    });
    customerStore.setCustomer(res.data.customer);
    emit("authenticated", res.data.customer);
    emit("close");
  } catch (err) {
    const code = err?.response?.data?.code;
    const detail = err?.response?.data?.detail;
    if (code === "otp_expired") {
      phoneOtpError.value = t("customerAuth.otpExpired");
      phoneStep.value = "phone";
    } else if (code === "invalid_code") {
      phoneOtpError.value = t("customerAuth.otpInvalid");
    } else if (code === "too_many_attempts") {
      phoneOtpError.value = t("customerAuth.tooManyAttempts");
      phoneStep.value = "phone";
    } else {
      phoneOtpError.value = detail || t("customerAuth.verifyError");
    }
  } finally {
    verifyingOtp.value = false;
  }
};

const backToPhone = () => {
  phoneStep.value = "phone";
  phoneOtpCode.value = "";
  phoneOtpError.value = "";
};

// ── Email OTP flow ────────────────────────────────────────────────────────────
const requestEmailOtp = async () => {
  emailError.value = "";
  generalError.value = "";
  if (!email.value || !email.value.includes("@")) {
    emailError.value = t("customerAuth.emailRequired");
    return;
  }
  requestingEmailOtp.value = true;
  try {
    await api.post("/customer/auth/email/request/", { email: email.value });
    emailStep.value = "verify";
    await nextTick();
    emailOtpInputRef.value?.focus();
  } catch (err) {
    const detail = err?.response?.data?.detail;
    emailError.value = detail || t("customerAuth.sendError");
  } finally {
    requestingEmailOtp.value = false;
  }
};

const verifyEmailOtp = async () => {
  emailOtpError.value = "";
  generalError.value = "";
  if (!emailOtpCode.value) {
    emailOtpError.value = t("customerAuth.otpRequired");
    return;
  }
  verifyingEmailOtp.value = true;
  try {
    const res = await api.post("/customer/auth/email/verify/", {
      email: email.value,
      code: emailOtpCode.value,
      name: name.value,
    });
    customerStore.setCustomer(res.data.customer);
    emit("authenticated", res.data.customer);
    emit("close");
  } catch (err) {
    const code = err?.response?.data?.code;
    const detail = err?.response?.data?.detail;
    if (code === "otp_expired") {
      emailOtpError.value = t("customerAuth.otpExpired");
      emailStep.value = "email";
    } else if (code === "invalid_code") {
      emailOtpError.value = t("customerAuth.otpInvalid");
    } else if (code === "too_many_attempts") {
      emailOtpError.value = t("customerAuth.tooManyAttempts");
      emailStep.value = "email";
    } else {
      emailOtpError.value = detail || t("customerAuth.verifyError");
    }
  } finally {
    verifyingEmailOtp.value = false;
  }
};

const backToEmail = () => {
  emailStep.value = "email";
  emailOtpCode.value = "";
  emailOtpError.value = "";
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
  try {
    if (window.google?.accounts?.id) {
      window.google.accounts.id.cancel();
    }
  } catch {
    // ignore
  }
});
</script>
