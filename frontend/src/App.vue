<template>
  <RouterView />
  <ToastHost />
</template>

<script setup>
import { onMounted } from "vue";
import { useTenantStore } from "./stores/tenant";
import { useThemeStore } from "./stores/theme";
import { useSessionStore } from "./stores/session";
import ToastHost from "./components/ToastHost.vue";

const tenant = useTenantStore();
const theme = useThemeStore();
const session = useSessionStore();

onMounted(async () => {
  await tenant.fetchMeta();
  if (tenant.meta?.profile) theme.apply(tenant.meta.profile);
  try {
    await session.fetchSession();
  } catch (err) {
    // Anonymous session is expected for public visitors.
  }
});
</script>
