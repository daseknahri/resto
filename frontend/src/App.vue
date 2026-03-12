<template>
  <RouterView />
  <ToastHost />
</template>

<script setup>
import { onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import { useTenantStore } from "./stores/tenant";
import { useLocaleStore } from "./stores/locale";
import { useThemeStore } from "./stores/theme";
import { useSessionStore } from "./stores/session";
import {
  hasPublicDemoTenant,
  isPlatformAdminHost,
  isPublicDemoHost,
} from "./lib/runtimeHost";
import ToastHost from "./components/ToastHost.vue";

const tenant = useTenantStore();
const locale = useLocaleStore();
const theme = useThemeStore();
const session = useSessionStore();
const route = useRoute();

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
