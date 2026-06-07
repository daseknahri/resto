<template>
  <main
    class="flex min-h-dvh items-center justify-center px-4 py-12"
    aria-labelledby="not-found-heading"
  >
    <div class="flex w-full max-w-sm flex-col items-center gap-8 text-center">

      <!-- Big 404 graphic -->
      <div
        class="ui-reveal flex select-none items-center gap-3"
        aria-hidden="true"
        style="--ui-delay: 0ms"
      >
        <span class="not-found-number">4</span>

        <div class="not-found-plate">
          <svg
            aria-hidden="true"
            focusable="false"
            viewBox="0 0 80 80"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            class="not-found-icon"
          >
            <circle cx="40" cy="40" r="34" stroke="currentColor" stroke-width="3" opacity="0.15"/>
            <circle cx="40" cy="40" r="24" stroke="currentColor" stroke-width="2" opacity="0.25"/>
            <path d="M28 40c0-6.627 5.373-12 12-12s12 5.373 12 12" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
            <path d="M33 43c0 3.866 3.134 7 7 7s7-3.134 7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
            <path d="M40 28v-6M40 58v-6M52 40h6M28 40h-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.3"/>
          </svg>
        </div>

        <span class="not-found-number">4</span>
      </div>

      <!-- Message -->
      <div
        class="ui-reveal space-y-2"
        style="--ui-delay: 60ms"
      >
        <p class="ui-kicker">{{ t('notFound.kicker') }}</p>
        <h1
          id="not-found-heading"
          class="ui-page-title"
        >
          {{ t('notFound.title') }}
        </h1>
        <p class="ui-subtle mx-auto max-w-xs leading-relaxed">
          {{ t('notFound.message') }}
        </p>
      </div>

      <!-- CTAs -->
      <nav
        class="ui-reveal flex flex-wrap justify-center gap-3"
        style="--ui-delay: 120ms"
        :aria-label="t('notFound.recovery')"
      >
        <RouterLink
          v-if="isOwnerHost"
          to="/owner"
          class="ui-btn-primary ui-press min-w-[10rem] justify-center"
        >
          {{ t('notFound.goDashboard') }}
        </RouterLink>
        <RouterLink
          v-else-if="isCustomerHost"
          to="/browse"
          class="ui-btn-primary ui-press min-w-[10rem] justify-center"
        >
          {{ t('notFound.goMenu') }}
        </RouterLink>
        <RouterLink
          v-else
          to="/"
          class="ui-btn-primary ui-press min-w-[10rem] justify-center"
        >
          {{ t('notFound.goHome') }}
        </RouterLink>

        <button
          class="ui-btn-outline ui-press min-w-[8rem] justify-center"
          @click="goBack"
        >
          {{ t('notFound.goBack') }}
        </button>
      </nav>

      <!-- Subtle path indicator -->
      <p
        class="ui-reveal max-w-full truncate font-mono text-[11px] tracking-wide text-slate-600"
        style="--ui-delay: 180ms"
        aria-hidden="true"
      >
        {{ currentPath }}
      </p>

    </div>
  </main>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink, useRouter, useRoute } from 'vue-router'
import { useI18n } from '../composables/useI18n'
import { useSessionStore } from '../stores/session'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const session = useSessionStore()

const isOwnerHost = computed(() => session.canEditTenantMenu || session.isAuthenticated)
const isCustomerHost = computed(() => !isOwnerHost.value)
const currentPath = computed(() => route.fullPath)

const goBack = () => {
  if (window.history.length > 2) {
    router.back()
  } else {
    router.push(isOwnerHost.value ? '/owner' : '/')
  }
}
</script>

<style scoped>
/* ── Hero numbers ───────────────────────────────────────── */
.not-found-number {
  font-size: clamp(5rem, 18vw, 9rem);
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
  background: linear-gradient(135deg, #334155 0%, #1e293b 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* ── Plate circle ───────────────────────────────────────── */
.not-found-plate {
  width: clamp(4.5rem, 16vw, 8rem);
  height: clamp(4.5rem, 16vw, 8rem);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(245, 158, 11, 0.04));
  border: 1.5px solid rgba(245, 158, 11, 0.18);
  flex-shrink: 0;
}

/* ── Dish icon — respects reduced-motion ────────────────── */
.not-found-icon {
  width: 65%;
  height: 65%;
  color: var(--color-secondary, #f59e0b);
  opacity: 0.7;
  animation: not-found-spin 14s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .not-found-icon {
    animation: none;
  }
}

@keyframes not-found-spin {
  to { transform: rotate(360deg); }
}
</style>
