<template>
  <!-- Global offline banner — role="alert" is always in the DOM so assistive
       technologies register it as a live region before any content is injected.
       The inner content is conditionally rendered via v-if so the mutation fires
       the announcement correctly in JAWS + Chrome / NVDA + Firefox. -->
  <div role="alert" aria-live="assertive" aria-atomic="true" class="fixed inset-x-0 top-0 z-[9999]">
    <Transition name="ui-fade">
      <div
        v-if="isOffline"
        class="flex items-center justify-center gap-2 bg-[var(--color-surface)] px-4 py-2 text-xs font-medium text-[var(--color-secondary)] shadow-lg"
      >
        <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" class="h-3.5 w-3.5 shrink-0">
          <path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/>
        </svg>
        {{ t('common.offlineBanner') }}
      </div>
    </Transition>
  </div>
  <ErrorBoundary>
    <RouterView />
  </ErrorBoundary>
  <ToastHost />
  <ConfirmModal />
  <PromptModal />
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useTenantStore } from "./stores/tenant";
import { useLocaleStore } from "./stores/locale";
import { useThemeStore } from "./stores/theme";
import { useSessionStore } from "./stores/session";
import { useSeoMeta } from "./composables/useSeoMeta";
import { useI18n } from "./composables/useI18n";
import {
  hasPublicDemoTenant,
  isPlatformAdminHost,
  isPublicDemoHost,
} from "./lib/runtimeHost";
import ToastHost from "./components/ToastHost.vue";
import ConfirmModal from "./components/ConfirmModal.vue";
import PromptModal from "./components/PromptModal.vue";
import ErrorBoundary from "./components/ErrorBoundary.vue";

const { t } = useI18n();

// ── Offline detection ────────────────────────────────────────────────────────
const isOffline = ref(typeof navigator !== "undefined" ? !navigator.onLine : false);
const handleOnline = () => { isOffline.value = false; };
const handleOffline = () => { isOffline.value = true; };
onMounted(() => {
  window.addEventListener("online", handleOnline);
  window.addEventListener("offline", handleOffline);
});
onUnmounted(() => {
  window.removeEventListener("online", handleOnline);
  window.removeEventListener("offline", handleOffline);
});

const tenant = useTenantStore();
const locale = useLocaleStore();
const theme = useThemeStore();
const session = useSessionStore();
const route = useRoute();
useSeoMeta();

watch(
  () => tenant.resolvedMeta?.profile?.language,
  (language) => {
    if (language) locale.setTenantDefault(language);
  }
);

onMounted(async () => {
  const isCustomerInterfaceRoute = route.matched.some(
    (record) => record.meta?.interface === "customer"
  );
  const shouldBootstrapTenant =
    !isPlatformAdminHost() &&
    (!isPublicDemoHost() ||
      (hasPublicDemoTenant() && isCustomerInterfaceRoute));

  if (shouldBootstrapTenant) {
    await tenant.fetchMeta();
    locale.setTenantDefault(tenant.resolvedMeta?.profile?.language);
    if (tenant.resolvedMeta?.profile) theme.apply(tenant.resolvedMeta.profile);
  }
  const shouldFetchSession = !isPublicDemoHost();
  if (shouldFetchSession) {
    try {
      await session.fetchSession();
    } catch {
      // Anonymous session is expected for public visitors.
    }
  }
});
</script>
