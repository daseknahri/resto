<template>
  <!--
    Minimal chrome-less layout for standalone routes (sign-in, password reset,
    activation, unauthorized, admin pages, 404). These pages render no header /
    nav, but a11y still requires (a) a single focusable <main id="main-content">
    landmark so the SPA route-change focus guard (router/focusGuard.js, WCAG
    2.4.3) has somewhere to land, and (b) a skip-link so keyboard users can jump
    straight to content. We reuse the exact skip-link markup + #main-content
    pattern from the full layouts (LandingLayout.vue) — only the page chrome is
    omitted.
  -->
  <div class="ui-shell">
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:start-2 focus:top-2 focus:z-[9999] focus:rounded-lg focus:bg-slate-900 focus:px-4 focus:py-2 focus:text-sm focus:text-white focus:outline-none focus:ring-2 focus:ring-[var(--color-secondary)]">{{ t('common.skipToMain') }}</a>
    <main id="main-content" tabindex="-1" class="min-h-screen w-full">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
</script>
