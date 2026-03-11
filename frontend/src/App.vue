<template>
  <RouterView />
  <ToastHost />
</template>

<script setup>
import { onMounted, watch } from "vue";
import { useTenantStore } from "./stores/tenant";
import { useLocaleStore } from "./stores/locale";
import { useThemeStore } from "./stores/theme";
import { useSessionStore } from "./stores/session";
import ToastHost from "./components/ToastHost.vue";

const tenant = useTenantStore();
const locale = useLocaleStore();
const theme = useThemeStore();
const session = useSessionStore();

watch(
  () => tenant.resolvedMeta?.profile?.language,
  (language) => {
    if (language) locale.setTenantDefault(language);
  }
);

onMounted(async () => {
  await tenant.fetchMeta();
  locale.setTenantDefault(tenant.resolvedMeta?.profile?.language);
  if (tenant.resolvedMeta?.profile) theme.apply(tenant.resolvedMeta.profile);
  try {
    await session.fetchSession();
  } catch (err) {
    // Anonymous session is expected for public visitors.
  }
});
</script>
