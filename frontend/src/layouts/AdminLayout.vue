<template>
  <!--
    Admin chrome layout — wraps the 9 platform-admin routes with a persistent
    top nav bar. Follows the same skip-link + <main id="main-content" tabindex="-1">
    a11y pattern as PlainLayout and the other full layouts (WCAG 2.4.3).
  -->
  <div class="ui-shell">
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:start-2 focus:top-2 focus:z-[9999] focus:rounded-lg focus:bg-slate-900 focus:px-4 focus:py-2 focus:text-sm focus:text-white focus:outline-none focus:ring-2 focus:ring-[var(--color-secondary)]">{{ t('common.skipToMain') }}</a>

    <header class="admin-header">
      <div class="admin-header-inner">
        <!-- Brand / title -->
        <div class="admin-brand">
          <span class="admin-brand-title">{{ t('adminLayout.title', { platform: platformName }) }}</span>
        </div>

        <!-- Primary nav links (scroll horizontally on narrow screens) -->
        <nav class="admin-nav" :aria-label="t('adminLayout.title', { platform: platformName })">
          <RouterLink
            v-for="link in navLinks"
            :key="link.name"
            :to="{ name: link.name }"
            class="admin-nav-link"
            :data-active="$route.name === link.name ? 'true' : undefined"
            :aria-current="$route.name === link.name ? 'page' : undefined"
            active-class=""
            exact-active-class=""
          >
            {{ t(link.labelKey) }}
          </RouterLink>
        </nav>

        <!-- Sign out -->
        <button
          type="button"
          class="admin-signout-btn"
          @click="handleSignOut"
        >
          {{ t('common.signOut') }}
        </button>
      </div>
    </header>

    <main id="main-content" tabindex="-1" class="min-h-screen w-full">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { useRouter } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { useSessionStore } from "../stores/session";
import { PLATFORM_NAME } from "../lib/brand";

const { t } = useI18n();
const router = useRouter();
const session = useSessionStore();

const platformName = PLATFORM_NAME;

const navLinks = [
  { name: "admin-console",       labelKey: "adminLayout.console" },
  { name: "admin-drivers",       labelKey: "adminLayout.drivers" },
  { name: "admin-customers",     labelKey: "adminLayout.customers" },
  { name: "admin-wallets",       labelKey: "adminLayout.wallets" },
  { name: "admin-delivery-jobs", labelKey: "adminLayout.deliveryJobs" },
  { name: "admin-delivery-zones",labelKey: "adminLayout.deliveryZones" },
  { name: "admin-rides",         labelKey: "adminLayout.rides" },
  { name: "admin-flash-sales",   labelKey: "adminLayout.flashSales" },
  { name: "admin-analytics",     labelKey: "adminLayout.analytics" },
];

const handleSignOut = async () => {
  await session.signOut();
  router.push({ name: "signin" });
};
</script>

<style scoped>
.admin-header {
  position: sticky;
  top: 0;
  z-index: 2000;
  border-bottom: 1px solid rgba(51, 65, 85, 0.7);
  background: linear-gradient(180deg, rgba(2, 6, 23, 0.97), rgba(3, 15, 35, 0.95));
  backdrop-filter: blur(16px);
}

.admin-header-inner {
  display: flex;
  align-items: center;
  gap: 1rem;
  max-width: 100%;
  padding: 0 1rem;
  height: 3.25rem;
  overflow: hidden;
}

.admin-brand {
  flex-shrink: 0;
}

.admin-brand-title {
  font-size: 0.875rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: rgb(226, 232, 240);
  white-space: nowrap;
}

.admin-nav {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  overflow-x: auto;
  flex: 1 1 0%;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.admin-nav::-webkit-scrollbar {
  display: none;
}

.admin-nav-link {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  padding: 0.375rem 0.75rem;
  border-radius: 0.625rem;
  border: 1px solid transparent;
  font-size: 0.8rem;
  font-weight: 600;
  color: rgb(148, 163, 184);
  white-space: nowrap;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
  text-decoration: none;
}

.admin-nav-link:hover {
  border-color: rgba(245, 158, 11, 0.45);
  background: rgba(15, 23, 42, 0.7);
  color: rgb(245, 158, 11);
}

.admin-nav-link:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.6);
}

.admin-nav-link[data-active="true"] {
  border-color: rgba(245, 158, 11, 0.8);
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.18), rgba(245, 158, 11, 0.07));
  color: rgb(245, 158, 11);
}

.admin-signout-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.7rem;
  border-radius: 0.625rem;
  border: 1px solid rgba(51, 65, 85, 0.7);
  background: transparent;
  font-size: 0.78rem;
  font-weight: 600;
  color: rgb(148, 163, 184);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
  white-space: nowrap;
}

.admin-signout-btn:hover {
  border-color: rgba(252, 165, 165, 0.6);
  background: rgba(239, 68, 68, 0.08);
  color: rgb(252, 165, 165);
}

.admin-signout-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgba(252, 165, 165, 0.5);
}
</style>
