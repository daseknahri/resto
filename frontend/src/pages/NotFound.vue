<template>
  <div class="not-found-root">
    <div class="not-found-inner">

      <!-- Big 404 graphic -->
      <div class="not-found-hero" aria-hidden="true">
        <span class="not-found-number">4</span>
        <div class="not-found-plate">
          <!-- Animated plate / dish icon -->
          <svg aria-hidden="true" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" class="not-found-icon">
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
      <div class="not-found-body">
        <h1 class="not-found-title">{{ t('notFound.title') }}</h1>
        <p class="not-found-message">{{ t('notFound.message') }}</p>
      </div>

      <!-- CTAs -->
      <div class="not-found-actions">
        <RouterLink
          v-if="isOwnerHost"
          to="/owner"
          class="ui-btn-primary not-found-cta-primary"
        >
          {{ t('notFound.goDashboard') }}
        </RouterLink>
        <RouterLink
          v-else-if="isCustomerHost"
          to="/browse"
          class="ui-btn-primary not-found-cta-primary"
        >
          {{ t('notFound.goMenu') }}
        </RouterLink>
        <RouterLink
          v-else
          to="/"
          class="ui-btn-primary not-found-cta-primary"
        >
          {{ t('notFound.goHome') }}
        </RouterLink>

        <button
          class="ui-btn-outline not-found-cta-secondary"
          @click="goBack"
        >
          {{ t('notFound.goBack') }}
        </button>
      </div>

      <!-- Subtle path indicator -->
      <p class="not-found-path">{{ currentPath }}</p>

    </div>
  </div>
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
.not-found-root {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(160deg, #020b18 0%, #060f1e 55%, #030b16 100%);
  padding: 2rem 1rem;
}

.not-found-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2rem;
  max-width: 480px;
  width: 100%;
  text-align: center;
}

/* ── Hero: "4 🍽 4" ─────────────────────────────────────── */
.not-found-hero {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  user-select: none;
}

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

.not-found-plate {
  width: clamp(4.5rem, 16vw, 8rem);
  height: clamp(4.5rem, 16vw, 8rem);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(var(--color-secondary-rgb, 245,158,11), 0.12), rgba(var(--color-secondary-rgb, 245,158,11), 0.04));
  border: 1.5px solid rgba(var(--color-secondary-rgb, 245,158,11), 0.18);
}

.not-found-icon {
  width: 65%;
  height: 65%;
  color: var(--color-secondary, #f59e0b);
  opacity: 0.7;
  animation: not-found-spin 14s linear infinite;
}

@keyframes not-found-spin {
  0%   { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* ── Text ──────────────────────────────────────────────── */
.not-found-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #f1f5f9;
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.not-found-message {
  margin-top: 0.5rem;
  font-size: 0.9rem;
  color: #64748b;
  line-height: 1.6;
}

/* ── Buttons ───────────────────────────────────────────── */
.not-found-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.75rem;
}

.not-found-cta-primary {
  min-width: 10rem;
  justify-content: center;
}

.not-found-cta-secondary {
  min-width: 8rem;
  justify-content: center;
}

/* ── Path ──────────────────────────────────────────────── */
.not-found-path {
  font-size: 0.7rem;
  color: #1e293b;
  font-family: ui-monospace, monospace;
  letter-spacing: 0.04em;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
