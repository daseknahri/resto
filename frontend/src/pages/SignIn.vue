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
        <div class="space-y-3 text-center">
          <p class="ui-kicker">{{ t("signIn.kicker") }}</p>
          <h1 class="ui-display text-2xl font-semibold text-white">{{ t("signIn.title") }}</h1>
          <p class="text-sm text-slate-300">{{ t("signIn.description") }}</p>
        </div>

        <!-- Session-expired notice (shown when redirected from a 401) -->
        <div
          v-if="sessionExpired"
          role="alert"
          class="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2.5"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400"><path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0V5.75A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
          <p class="flex-1 text-sm text-amber-300">{{ t("signIn.sessionExpired") }}</p>
        </div>

        <form class="space-y-4" novalidate @submit.prevent="submit">
          <label class="block space-y-1 text-sm text-slate-200">
            {{ t("signIn.identifier") }}
            <input
              v-model="identifier"
              type="text"
              autocomplete="username"
              class="ui-input"
              :class="fieldErrors.identifier ? 'border-red-400' : ''"
              :aria-invalid="fieldErrors.identifier ? 'true' : undefined"
              :aria-describedby="fieldErrors.identifier ? 'signin-identifier-error' : undefined"
              aria-required="true"
              @input="fieldErrors.identifier = ''"
            />
            <p v-if="fieldErrors.identifier" id="signin-identifier-error" class="text-xs text-red-300" role="alert">{{ fieldErrors.identifier }}</p>
          </label>
          <label class="block space-y-1 text-sm text-slate-200">
            {{ t("signIn.password") }}
            <input
              v-model="password"
              type="password"
              autocomplete="current-password"
              class="ui-input"
              :class="fieldErrors.password ? 'border-red-400' : ''"
              :aria-invalid="fieldErrors.password ? 'true' : undefined"
              :aria-describedby="fieldErrors.password ? 'signin-password-error' : undefined"
              aria-required="true"
              @input="fieldErrors.password = ''"
            />
            <p v-if="fieldErrors.password" id="signin-password-error" class="text-xs text-red-300" role="alert">{{ fieldErrors.password }}</p>
          </label>
          <button
            type="submit"
            :disabled="session.loading"
            class="ui-btn-primary ui-press w-full justify-center disabled:opacity-60"
          >
            {{ session.loading ? t("signIn.signingIn") : t("common.signIn") }}
          </button>
          <div v-if="error" role="alert" class="flex items-start gap-2 rounded-2xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
            <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm text-red-300">{{ error }}</p>
          </div>
        </form>

        <div class="ui-section-band space-y-3 text-xs text-slate-300">
          <p class="font-medium text-slate-100">{{ t("signIn.firstTime") }}</p>
          <p>
            {{ t("signIn.firstTime") }}
            <RouterLink :to="activateLink" class="text-[var(--color-secondary)] underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:rounded-sm focus-visible:underline">{{ t("signIn.activationLink") }}</RouterLink>
          </p>
          <p>
            {{ t("signIn.forgotPassword") }}
            <RouterLink :to="forgotPasswordLink" class="text-[var(--color-secondary)] underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:rounded-sm focus-visible:underline">{{ t("signIn.resetHere") }}</RouterLink>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { currentHostname, isPlatformPublicHost } from "../lib/runtimeHost";
import { useSessionStore } from "../stores/session";

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
    const user = await session.signIn(identifier.value, password.value);
    if (session.canEditTenantMenu && redirectOwnerToTenantHost(user)) {
      return;
    }
    const next = typeof route.query.next === "string" ? route.query.next : "";
    if (next) {
      router.push(next);
    } else {
      router.push(fallbackRoute());
    }
  } catch {
    error.value = session.error || t("signIn.failed");
  }
};
</script>
