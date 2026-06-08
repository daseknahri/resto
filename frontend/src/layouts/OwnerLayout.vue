<template>
  <div class="ui-shell">
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[9999] focus:rounded-lg focus:bg-slate-900 focus:px-4 focus:py-2 focus:text-sm focus:text-white focus:outline-none focus:ring-2 focus:ring-brand-secondary">{{ t('common.skipToMain') }}</a>
    <header class="ui-header relative z-[2000] overflow-visible md:top-0 md:z-[2000]">
      <div class="mx-auto w-full max-w-7xl px-3 py-1.5 sm:px-4 md:py-3 ui-fade-up">
        <div class="ui-workspace-stage overflow-visible p-2.5 md:p-4 owner-workspace-stage">
          <div class="relative flex items-start justify-between gap-2 md:grid md:grid-cols-[minmax(0,1fr)_minmax(420px,2fr)_auto] md:items-center md:gap-4">
            <div class="flex min-w-0 items-center gap-2.5 md:gap-3">
              <img
                v-if="tenantLogo"
                :src="tenantLogo"
                :alt="`${tenantName} logo`"
                class="h-8 w-8 shrink-0 rounded-xl border border-slate-700/70 object-cover md:h-9 md:w-9"
                loading="eager"
                decoding="async"
                @error="$event.target.style.display='none'"
              />
              <div class="min-w-0">
                <h1 class="ui-display truncate text-base font-semibold text-white sm:text-lg md:text-2xl">{{ tenantName }}</h1>
                <div class="mt-1 flex flex-wrap items-center gap-2">
                  <span class="ui-data-strip hidden sm:inline-flex">{{ tenant.meta?.slug || "tenant" }}</span>
                  <span class="ui-data-strip inline-flex sm:hidden">{{ activeWorkspaceLabel }}</span>
                </div>
              </div>
            </div>

            <nav
              class="owner-main-nav hidden md:grid"
              :style="`--nav-cols: ${3 + (showTables ? 1 : 0) + (showReservations ? 1 : 0) + 1}`"
              :aria-label="t('ownerLayout.navDesktop')"
            >
              <RouterLink to="/owner" class="owner-main-nav-item" :data-active="$route.path === '/owner'" :aria-current="$route.path === '/owner' ? 'page' : undefined" active-class="" exact-active-class="">
                <AppIcon name="home" class="owner-nav-icon" />
                <span>{{ t("ownerLayout.dashboard") }}</span>
              </RouterLink>
              <!-- Orders — second position, always visible, live badge -->
              <RouterLink
                to="/owner/orders"
                class="owner-main-nav-item"
                :data-active="$route.path.startsWith('/owner/orders')"
                :data-urgent="pendingOrdersCount > 0"
                :aria-current="$route.path.startsWith('/owner/orders') ? 'page' : undefined"
                active-class=""
                exact-active-class=""
              >
                <span class="relative inline-flex items-center gap-1">
                  <AppIcon name="menu" class="owner-nav-icon" />
                  <span
                    v-if="pendingOrdersCount > 0"
                    class="owner-orders-badge"
                    aria-hidden="true"
                  >{{ pendingOrdersCount }}</span>
                </span>
                <span>{{ t("ownerLayout.orders") }}</span>
              </RouterLink>
              <RouterLink
                :to="{ name: 'owner-menu-builder' }"
                class="owner-main-nav-item"
                :data-active="$route.path.startsWith('/owner/menu-builder')"
                :aria-current="$route.path.startsWith('/owner/menu-builder') ? 'page' : undefined"
                active-class=""
                exact-active-class=""
              >
                <AppIcon name="menu" class="owner-nav-icon" />
                <span>{{ menuBuilderLabel }}</span>
              </RouterLink>
              <RouterLink
                v-if="showTables"
                to="/owner/tables"
                class="owner-main-nav-item"
                :data-active="$route.path.startsWith('/owner/tables')"
                :aria-current="$route.path.startsWith('/owner/tables') ? 'page' : undefined"
                active-class=""
                exact-active-class=""
              >
                <AppIcon name="table" class="owner-nav-icon" />
                <span>{{ t("ownerLayout.tablesQr") }}</span>
              </RouterLink>
              <RouterLink
                v-if="showReservations"
                to="/owner/reservations"
                class="owner-main-nav-item"
                :data-active="$route.path.startsWith('/owner/reservations')"
                :aria-current="$route.path.startsWith('/owner/reservations') ? 'page' : undefined"
                active-class=""
                exact-active-class=""
              >
                <AppIcon name="calendar" class="owner-nav-icon" />
                <span>{{ t("ownerLayout.reservations") }}</span>
              </RouterLink>
              <!-- Reports/Analytics — a daily tool, promoted out of the settings menu -->
              <RouterLink
                :to="{ name: 'owner-analytics' }"
                class="owner-main-nav-item"
                :data-active="$route.path.startsWith('/owner/analytics')"
                :aria-current="$route.path.startsWith('/owner/analytics') ? 'page' : undefined"
                active-class=""
                exact-active-class=""
              >
                <AppIcon name="chart" class="owner-nav-icon" />
                <span>{{ t("ownerAnalytics.title") }}</span>
              </RouterLink>
            </nav>

            <div class="flex shrink-0 items-center gap-1.5 sm:gap-2">
              <!-- Waiter view shortcut (desktop) -->
              <RouterLink
                v-if="showWaiter"
                to="/waiter"
                class="ui-chip hidden md:inline-flex focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
              >
                <AppIcon name="user" class="h-3.5 w-3.5" />
                {{ t("ownerLayout.waiterView") }}
              </RouterLink>
              <LanguageSwitcher compact dropdown />
              <!-- Dark / light mode toggle -->
              <button
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-slate-700/50 bg-slate-800/50 text-slate-400 transition-colors hover:border-amber-500/40 hover:text-amber-300 ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                type="button"
                :aria-label="ownerTheme === 'dark' ? t('ownerLayout.themeLight') : t('ownerLayout.themeDark')"
                :title="ownerTheme === 'dark' ? t('ownerLayout.themeLight') : t('ownerLayout.themeDark')"
                @click="toggleTheme"
              >
                <svg v-if="ownerTheme === 'dark'" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-3.5 w-3.5">
                  <path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clip-rule="evenodd"/>
                </svg>
                <svg v-else aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-3.5 w-3.5">
                  <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"/>
                </svg>
              </button>
              <!-- PWA install button -->
              <button
                v-if="canInstall"
                class="hidden sm:flex items-center gap-1.5 rounded-xl border border-slate-700/50 bg-slate-800/50 px-3 py-1.5 text-xs font-medium text-slate-400 hover:border-teal-500/40 hover:text-teal-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                type="button"
                :aria-label="t('ownerLayout.installApp')"
                :title="t('ownerLayout.installApp')"
                @click="pwaInstall"
              >
                <span aria-hidden="true">⬇</span> {{ t('ownerLayout.installApp') }}
              </button>
              <!-- Web Push bell (only when VAPID is configured) -->
              <button
                v-if="pushSupported && pushEnabled"
                class="relative flex h-8 w-8 items-center justify-center rounded-xl border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 ui-touch-target"
                :class="pushSubscribed
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                  : 'border-slate-700/50 bg-slate-800/50 text-slate-400 hover:border-slate-600'"
                :aria-label="pushSubscribed ? t('ownerLayout.pushDisable') : t('ownerLayout.pushEnable')"
                :disabled="pushLoading"
                type="button"
                @click="pushSubscribed ? pushUnsubscribe() : pushSubscribe()"
              >
                <span class="text-sm leading-none" :class="pushLoading ? 'animate-pulse' : ''" aria-hidden="true">
                  {{ pushSubscribed ? '🔔' : '🔕' }}
                </span>
              </button>
              <div ref="settingsMenuRef" class="relative" @keydown.escape.stop="closeSettingsMenuByKey" @keydown="navigateSettingsMenu">
                <button
                  ref="settingsTriggerRef"
                  class="owner-settings-trigger ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                  type="button"
                  :aria-expanded="settingsOpen ? 'true' : 'false'"
                  :aria-label="t('common.profile')"
                  aria-haspopup="menu"
                  @click="toggleSettingsMenu"
                >
                  <AppIcon name="settings" class="owner-settings-icon" />
                </button>
                <transition name="ui-fade">
                  <div v-if="settingsOpen" class="owner-settings-menu" role="menu" :aria-label="t('common.profile')">
                    <!-- Reports: in the top nav on desktop; shown here on mobile only -->
                    <div role="group" :aria-label="t('ownerLayout.groupReports')" class="md:hidden">
                      <p class="owner-settings-section" aria-hidden="true">{{ t("ownerLayout.groupReports") }}</p>
                      <RouterLink class="owner-settings-item" role="menuitem" :to="{ name: 'owner-analytics' }" @click="closeSettingsMenu">
                        <AppIcon name="chart" class="owner-settings-item-icon" />
                        <span>{{ t("ownerAnalytics.title") }}</span>
                      </RouterLink>
                    </div>

                    <div role="group" :aria-label="t('ownerLayout.groupMarketing')">
                      <p class="owner-settings-section" aria-hidden="true">{{ t("ownerLayout.groupMarketing") }}</p>
                      <RouterLink class="owner-settings-item" role="menuitem" :to="{ name: 'owner-promotions' }" @click="closeSettingsMenu">
                        <AppIcon name="tag" class="owner-settings-item-icon" />
                        <span>{{ t("ownerLayout.promotions") }}</span>
                      </RouterLink>
                      <RouterLink class="owner-settings-item" role="menuitem" :to="{ name: 'owner-loyalty' }" @click="closeSettingsMenu">
                        <AppIcon name="star" class="owner-settings-item-icon" />
                        <span>{{ t("ownerLayout.loyalty") }}</span>
                      </RouterLink>
                      <RouterLink class="owner-settings-item" role="menuitem" :to="{ name: 'owner-ratings' }" @click="closeSettingsMenu">
                        <AppIcon name="star" class="owner-settings-item-icon" />
                        <span>{{ t("ownerLayout.ratings") }}</span>
                      </RouterLink>
                    </div>

                    <div role="group" :aria-label="t('ownerLayout.groupOperations')">
                      <p class="owner-settings-section" aria-hidden="true">{{ t("ownerLayout.groupOperations") }}</p>
                      <RouterLink v-if="showKitchen" class="owner-settings-item" role="menuitem" :to="{ name: 'owner-kitchen' }" @click="closeSettingsMenu">
                        <AppIcon name="menu" class="owner-settings-item-icon" />
                        <span>{{ t("ownerLayout.kitchen") }}</span>
                      </RouterLink>
                      <RouterLink class="owner-settings-item" role="menuitem" :to="{ name: 'owner-wallet' }" @click="closeSettingsMenu">
                        <AppIcon name="wallet" class="owner-settings-item-icon" />
                        <span>{{ t("ownerLayout.wallet") }}</span>
                      </RouterLink>
                      <RouterLink class="owner-settings-item" role="menuitem" :to="{ name: 'owner-notifications' }" @click="closeSettingsMenu">
                        <AppIcon name="info" class="owner-settings-item-icon" />
                        <span>{{ t("ownerLayout.notifications") }}</span>
                      </RouterLink>
                    </div>

                    <div role="group" :aria-label="t('ownerLayout.groupAccount')">
                      <p class="owner-settings-section" aria-hidden="true">{{ t("ownerLayout.groupAccount") }}</p>
                      <RouterLink class="owner-settings-item" role="menuitem" :to="{ name: 'owner-staff' }" @click="closeSettingsMenu">
                        <AppIcon name="user" class="owner-settings-item-icon" />
                        <span>{{ t("ownerLayout.staff") }}</span>
                      </RouterLink>
                      <RouterLink class="owner-settings-item" role="menuitem" :to="{ name: 'owner-profile' }" @click="closeSettingsMenu">
                        <AppIcon name="settings" class="owner-settings-item-icon" />
                        <span>{{ t("common.profile") }}</span>
                      </RouterLink>
                      <RouterLink class="owner-settings-item" role="menuitem" :to="{ name: 'owner-profile', query: { tab: 'billing' } }" @click="closeSettingsMenu">
                        <AppIcon name="card" class="owner-settings-item-icon" />
                        <span>{{ t("ownerBilling.tabLabel") }}</span>
                      </RouterLink>
                      <button class="owner-settings-item owner-settings-item-danger" role="menuitem" type="button" @click="handleSignOut">
                        <AppIcon name="logout" class="owner-settings-item-icon" />
                        <span>{{ t("common.signOut") }}</span>
                      </button>
                    </div>
                  </div>
                </transition>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- Grace period / payment overdue banner -->
    <Transition name="ui-fade">
      <div
        v-if="tenant.isInGracePeriod || tenant.graceExpired"
        role="alert"
        class="sticky top-0 z-[1900] w-full border-b px-4 py-2.5 text-center text-xs font-semibold"
        :class="tenant.graceExpired
          ? 'border-red-500/40 bg-red-500/15 text-red-200'
          : tenant.graceDaysRemaining <= 1
            ? 'border-orange-500/40 bg-orange-500/15 text-orange-200'
            : 'border-amber-500/40 bg-amber-500/12 text-amber-200'"
      >
        <span v-if="tenant.graceExpired">{{ t('ownerLayout.graceExpiredWarning') }}</span>
        <span v-else-if="tenant.graceDaysRemaining <= 1">{{ t('ownerLayout.gracePeriodCritical') }}</span>
        <span v-else>{{ t('ownerLayout.gracePeriodWarning', { days: tenant.graceDaysRemaining }) }}</span>
        <RouterLink
          :to="{ name: 'owner-profile', query: { tab: 'billing' } }"
          class="ms-2 underline opacity-80 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current focus-visible:ring-offset-1 focus-visible:ring-offset-transparent rounded"
        >{{ t('ownerLayout.gracePeriodCta') }}</RouterLink>
      </div>
    </Transition>

    <!-- Waiter-call alerts — live via WebSocket, persistent until acknowledged -->
    <div v-if="waiterCallsPending.length" class="mx-auto w-full max-w-7xl px-3 pt-2 sm:px-4">
      <div role="alert" class="ui-panel border border-amber-500/40 bg-amber-500/10 p-3 space-y-2">
        <div class="flex items-center gap-2 text-sm font-semibold text-amber-300">
          <span class="relative flex h-2.5 w-2.5">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
            <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-400" />
          </span>
          {{ t("ownerLayout.waiterCallBannerTitle", { count: waiterCallsPending.length }) }}
        </div>
        <ul class="space-y-1.5">
          <li
            v-for="call in waiterCallsPending"
            :key="call.id"
            class="flex items-center justify-between gap-3 rounded-lg border border-amber-500/20 bg-slate-900/40 px-3 py-2"
          >
            <div class="min-w-0 text-sm">
              <span class="font-semibold text-white">{{ call.table_label || t("ownerLayout.waiterCallTableUnknown") }}</span>
              <span v-if="call.note" class="text-slate-300"> — {{ call.note }}</span>
            </div>
            <button
              type="button"
              class="shrink-0 rounded-lg border border-amber-500/40 px-3 py-1 text-xs font-semibold text-amber-200 transition hover:bg-amber-500/15 ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
              @click="acknowledgeWaiterCall(call.id)"
            >
              {{ t("ownerLayout.waiterCallAcknowledge") }}
            </button>
          </li>
        </ul>
      </div>
    </div>

    <!-- Visually-hidden live region: announces pending-order count changes to screen readers -->
    <span class="sr-only" aria-live="polite" aria-atomic="true">{{ pendingOrdersCount > 0 ? t('ownerLayout.ordersBadgeLabel', { count: pendingOrdersCount }) : '' }}</span>

    <main id="main-content" class="mx-auto w-full max-w-7xl px-3 py-3 pb-24 sm:px-4 md:py-5 md:pb-10">
      <RouterView v-slot="{ Component }">
        <Transition name="ui-route" mode="out-in">
          <KeepAlive :max="8" :exclude="KEEPALIVE_EXCLUDE">
            <component :is="Component" />
          </KeepAlive>
        </Transition>
      </RouterView>
    </main>

    <nav class="ui-bottom-dock owner-bottom-dock md:hidden" :aria-label="t('ownerLayout.navMobile')">
      <div class="ui-bottom-dock-grid" :class="`grid-cols-${3 + (showWaiter ? 1 : 0) + (showTables ? 1 : 0) + (showReservations ? 1 : 0)}`">
        <RouterLink
          to="/owner"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[10px] leading-tight"
          :data-active="$route.path === '/owner'"
          :aria-current="$route.path === '/owner' ? 'page' : undefined"
          active-class=""
          exact-active-class=""
        >
          <AppIcon name="home" class="owner-dock-icon" />
          <span>{{ t("ownerLayout.dashboard") }}</span>
        </RouterLink>
        <!-- Orders — second position with live badge -->
        <RouterLink
          to="/owner/orders"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[10px] leading-tight"
          :data-active="$route.path.startsWith('/owner/orders')"
          :data-urgent="pendingOrdersCount > 0"
          :aria-current="$route.path.startsWith('/owner/orders') ? 'page' : undefined"
          active-class=""
          exact-active-class=""
        >
          <span class="relative inline-flex">
            <AppIcon name="menu" class="owner-dock-icon" />
            <span v-if="pendingOrdersCount > 0" class="owner-orders-badge-dock" aria-hidden="true">{{ pendingOrdersCount }}</span>
          </span>
          <span>{{ t("ownerLayout.orders") }}</span>
        </RouterLink>
        <RouterLink
          v-if="showWaiter"
          to="/waiter"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[10px] leading-tight"
          :data-active="$route.path.startsWith('/waiter')"
          :aria-current="$route.path.startsWith('/waiter') ? 'page' : undefined"
          active-class=""
          exact-active-class=""
        >
          <AppIcon name="user" class="owner-dock-icon" />
          <span>{{ t("ownerLayout.waiterView") }}</span>
        </RouterLink>
        <RouterLink
          :to="{ name: 'owner-menu-builder' }"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[10px] leading-tight"
          :data-active="$route.path.startsWith('/owner/menu-builder')"
          :aria-current="$route.path.startsWith('/owner/menu-builder') ? 'page' : undefined"
          active-class=""
          exact-active-class=""
        >
          <AppIcon name="menu" class="owner-dock-icon" />
          <span>{{ menuBuilderLabel }}</span>
        </RouterLink>
        <RouterLink
          v-if="showTables"
          to="/owner/tables"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[10px] leading-tight"
          :data-active="$route.path.startsWith('/owner/tables')"
          :aria-current="$route.path.startsWith('/owner/tables') ? 'page' : undefined"
          active-class=""
          exact-active-class=""
        >
          <AppIcon name="table" class="owner-dock-icon" />
          <span>{{ t("ownerLayout.tablesQr") }}</span>
        </RouterLink>
        <RouterLink
          v-if="showReservations"
          to="/owner/reservations"
          class="ui-pill-nav owner-dock-link justify-center px-2 py-1 text-center text-[10px] leading-tight"
          :data-active="$route.path.startsWith('/owner/reservations')"
          :aria-current="$route.path.startsWith('/owner/reservations') ? 'page' : undefined"
          active-class=""
          exact-active-class=""
        >
          <AppIcon name="calendar" class="owner-dock-icon" />
          <span>{{ t("ownerLayout.reservations") }}</span>
        </RouterLink>
      </div>
    </nav>

    <!-- Internal staff chat (floating, real-time) -->
    <OwnerStaffChat />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import LanguageSwitcher from "../components/LanguageSwitcher.vue";
import OwnerStaffChat from "../components/OwnerStaffChat.vue";
import { useI18n } from "../composables/useI18n";
import { useVocabulary } from "../composables/useVocabulary";
import { useOwnerTheme } from "../composables/useOwnerTheme";
import { useOwnerRealtime } from "../composables/useOwnerRealtime";
import { useWaiterCalls } from "../composables/useWaiterCalls";
import { useStaffChat } from "../composables/useStaffChat";
import { useInstallPrompt } from "../composables/useInstallPrompt";
import { usePushNotifications } from "../composables/usePushNotifications";
import { useOrderStore } from "../stores/order";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";

const session = useSessionStore();
const tenant = useTenantStore();
const order = useOrderStore();
const router = useRouter();
const { t } = useI18n();
const { isShop: vocabIsShop, catalog: vocabCatalog } = useVocabulary();
// Shops see "Catalog" in place of "Menu Builder" in the nav.
const menuBuilderLabel = computed(() => (vocabIsShop.value ? vocabCatalog.value : t("ownerLayout.menuBuilder")));

// ── Owner color scheme (dark / light) ─────────────────────────────────────────
const { theme: ownerTheme, toggleTheme, activate: activateTheme, deactivate: deactivateTheme } = useOwnerTheme();

// ── PWA install prompt ────────────────────────────────────────────────────────
const { canInstall, install: pwaInstall } = useInstallPrompt();

// ── Web Push notifications ────────────────────────────────────────────────────
const {
  supported: pushSupported,
  enabled: pushEnabled,
  subscribed: pushSubscribed,
  loading: pushLoading,
  subscribe: pushSubscribe,
  unsubscribe: pushUnsubscribe,
  autoRestore: pushAutoRestore,
  checkEnabled: pushCheckEnabled,
} = usePushNotifications();

const tenantName = computed(() => tenant.meta?.name || t("ownerLayout.fallbackTenantName"));
const tenantLogo = computed(() => String(tenant.meta?.profile?.logo_url || "").trim());
// Always show all features until tier gating is configured
// Restaurant-only features are gated by the tenant's business_type capabilities
// (served in the profile meta). Non-restaurant verticals (retail, grocery) hide
// table/dine-in service navigation. Restaurants keep everything (defaults all true).
const showTables = computed(() => tenant.capabilities.tables !== false);
const showReservations = computed(() => tenant.capabilities.reservations !== false);
const showWaiter = computed(() => tenant.capabilities.waiter !== false);
const showKitchen = computed(() => tenant.capabilities.kitchen !== false);
const pendingOrdersCount = computed(() => order.orders.filter((o) => o.status === "pending").length);
const activeWorkspaceLabel = computed(() => {
  const path = router.currentRoute.value.path || "";
  if (path.startsWith("/owner/menu-builder")) return t("ownerLayout.menuBuilder");
  if (path.startsWith("/owner/profile")) return t("common.profile");
  if (path.startsWith("/owner/tables")) return t("ownerLayout.tablesQr");
  if (path.startsWith("/owner/reservations")) return t("ownerLayout.reservations");
  if (path.startsWith("/owner/orders")) return t("ownerLayout.orders");
  if (path.startsWith("/owner/staff")) return t("ownerLayout.staff");
  if (path.startsWith("/owner/ratings")) return t("ownerLayout.ratings");
  if (path.startsWith("/owner/kitchen")) return t("ownerLayout.kitchen");
  if (path.startsWith("/owner/loyalty")) return t("ownerLayout.loyalty");
  if (path.startsWith("/owner/wallet")) return t("ownerLayout.wallet");
  if (path.startsWith("/owner/promotions")) return t("ownerLayout.promotions");
  return t("ownerLayout.dashboard");
});
const settingsOpen = ref(false);
const settingsMenuRef = ref(null);
const settingsTriggerRef = ref(null);

const signOut = async () => {
  await session.signOut();
  router.push({ name: "home" });
};

const closeSettingsMenu = () => {
  settingsOpen.value = false;
};

// Called via Escape key — close and return focus to trigger button
const closeSettingsMenuByKey = () => {
  settingsOpen.value = false;
  settingsTriggerRef.value?.focus();
};

const toggleSettingsMenu = () => {
  settingsOpen.value = !settingsOpen.value;
  if (settingsOpen.value) {
    // Move focus to the first visible menuitem when the menu opens (ARIA menu pattern).
    nextTick(() => {
      const items = Array.from(
        settingsMenuRef.value?.querySelectorAll('[role="menuitem"]:not([disabled])') || []
      );
      items[0]?.focus();
    });
  }
};

// Arrow-key navigation for the settings dropdown (ARIA 1.1 Menu pattern).
const navigateSettingsMenu = (e) => {
  if (!settingsOpen.value || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) return;
  e.preventDefault();
  const items = Array.from(
    settingsMenuRef.value?.querySelectorAll('[role="menuitem"]:not([disabled])') || []
  );
  if (!items.length) return;
  const idx = items.indexOf(document.activeElement);
  if (e.key === 'ArrowDown') items[(idx + 1) % items.length]?.focus();
  else if (e.key === 'ArrowUp') items[(idx - 1 + items.length) % items.length]?.focus();
  else if (e.key === 'Home') items[0]?.focus();
  else if (e.key === 'End') items[items.length - 1]?.focus();
};

const handleSignOut = async () => {
  closeSettingsMenu();
  await signOut();
};

const onDocumentPointerDown = (event) => {
  if (!settingsOpen.value) return;
  const root = settingsMenuRef.value;
  if (root && !root.contains(event.target)) {
    closeSettingsMenu();
  }
};

// ── Layout-level new-order alerts ─────────────────────────────────────────────
// Keeps the nav badge live on every page. Also fires audio + browser notif when
// a new pending order arrives and the owner is NOT already on the Orders page
// (OwnerOrders handles its own sound there to avoid double-chime).
const layoutKnownIds = new Set();

// Read the same sound-preference key that OwnerOrders writes.
const LAYOUT_SOUND_KEY = typeof window === "undefined"
  ? "orders:sound"
  : `orders:sound:${window.location.hostname}`;
const layoutSoundEnabled = () => {
  try { return localStorage.getItem(LAYOUT_SOUND_KEY) !== "off"; } catch { return true; }
};

const layoutPlayAlertSound = () => {
  if (!layoutSoundEnabled()) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.18].forEach((delay, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = "sine";
      osc.frequency.setValueAtTime(i === 0 ? 780 : 980, ctx.currentTime + delay);
      gain.gain.setValueAtTime(0.35, ctx.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.25);
      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + 0.25);
    });
  } catch {
    // AudioContext not available or blocked
  }
};

const layoutCheckNewOrders = (orders) => {
  if (!Array.isArray(orders)) return;
  if (!layoutKnownIds.size) {
    // First load — seed without alerting
    orders.forEach((o) => layoutKnownIds.add(o.id));
    return;
  }
  const newPending = orders.filter((o) => o.status === "pending" && !layoutKnownIds.has(o.id));
  orders.forEach((o) => layoutKnownIds.add(o.id));
  if (!newPending.length) return;
  // Play sound only when not on the Orders page (it handles its own sound there)
  const onOrdersPage = router.currentRoute.value.path.startsWith("/owner/orders");
  if (!onOrdersPage) layoutPlayAlertSound();
  // Browser notification
  if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
    new Notification(
      t(newPending.length === 1 ? "ownerOrders.newOrderNotifTitle_one" : "ownerOrders.newOrderNotifTitle_other", { count: newPending.length }),
      { body: t("ownerOrders.newOrderNotifBody"), icon: "/favicon.ico", tag: "new-order", renotify: true }
    );
  }
};

const layoutRequestNotifPermission = () => {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission === "default") Notification.requestPermission().catch(() => {});
};

let orderPollTimer = null;

const layoutDoSilentPoll = async () => {
  const fresh = await order.fetchOrders("", { silent: true });
  layoutCheckNewOrders(Array.isArray(fresh) ? fresh : order.orders);
};

// Real-time: when a socket "order.new" ping arrives, refresh immediately (same
// path as the poll, incl. the new-order alert). Polling stays as the fallback, so
// this is purely a latency win when the WS infra is connected.
const {
  pending: waiterCallsPending,
  load: loadWaiterCalls,
  acknowledge: acknowledgeWaiterCall,
  handleRealtime: handleWaiterRealtime,
} = useWaiterCalls();

const layoutNotifyWaiterCall = (payload) => {
  layoutPlayAlertSound();
  if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
    const label = payload && payload.table_label ? payload.table_label : "";
    new Notification(t("ownerLayout.waiterCallNotifTitle"), {
      body: label
        ? t("ownerLayout.waiterCallNotifBody", { table: label })
        : t("ownerLayout.waiterCallNotifTitle"),
      icon: "/favicon.ico",
      tag: "waiter-call",
      renotify: true,
    });
  }
};

const { handleRealtime: handleChatRealtime } = useStaffChat();

const ownerRealtime = useOwnerRealtime((event, payload) => {
  if (typeof event !== "string") return;
  if (event.startsWith("order.")) {
    layoutDoSilentPoll();
  } else if (event.startsWith("waiter.")) {
    // Async: the handler resyncs through the section-filtered list, so the alert
    // only fires for a call this user is actually responsible for.
    handleWaiterRealtime(event, payload).then((isNew) => {
      if (isNew) layoutNotifyWaiterCall(payload);
    });
  } else if (event === "chat.message") {
    handleChatRealtime(event, payload);
  }
});

const onLayoutPageVisible = () => {
  if (typeof document !== "undefined" && document.visibilityState === "visible") {
    layoutDoSilentPoll();
  }
};

// Owner pages kept alive across navigation render instantly on revisit (state +
// scroll preserved, no refetch). These are excluded because they poll live data,
// have lifecycle cleanup that must run on unmount, or are editing surfaces that
// must stay fresh — they keep their normal mount/unmount behaviour. Names come
// from each page's defineOptions({ name }).
const KEEPALIVE_EXCLUDE = [
  "OwnerHome",
  "OwnerOrders",
  "OwnerKitchen",
  "OwnerMenuBuilder",
  "OwnerPromotions",
  "OwnerTables",
];

// Warm the chunks for the most-visited owner pages once the browser is idle, so
// the first navigation to them doesn't pay a JS download. Same dynamic imports the
// router uses, so this just fills the module cache — no duplicate chunk.
const prefetchOwnerChunks = () => {
  if (typeof window === "undefined") return;
  const run = () => {
    import("../pages/OwnerOrders.vue");
    import("../pages/OwnerMenuBuilder.vue");
  };
  if (typeof window.requestIdleCallback === "function") {
    window.requestIdleCallback(run, { timeout: 3000 });
  } else {
    setTimeout(run, 1500);
  }
};

onMounted(async () => {
  activateTheme(); // paint the saved dark/light choice onto <html>
  prefetchOwnerChunks();
  ownerRealtime.connect(); // instant order updates when WS is available (else polling)
  loadWaiterCalls(); // seed any pending waiter calls (real-time keeps it live)
  if (!tenant.meta && !tenant.loading) {
    await tenant.fetchMeta();
  }
  if (typeof document !== "undefined") {
    document.addEventListener("pointerdown", onDocumentPointerDown);
    document.addEventListener("visibilitychange", onLayoutPageVisible);
  }
  layoutRequestNotifPermission();
  // Web Push: check if VAPID is configured, then auto-restore existing subscription.
  pushCheckEnabled().then(() => {
    if (pushEnabled.value) pushAutoRestore();
  });
  // Background order poll — keeps the nav badge live on every page.
  // Always silent so we never trigger the loading spinner shown in OwnerOrders.
  const initial = await order.fetchOrders("", { silent: true });
  layoutCheckNewOrders(Array.isArray(initial) ? initial : order.orders);
  orderPollTimer = setInterval(() => {
    // Skip when tab is hidden — the visibilitychange handler fires on resume instead
    if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
    layoutDoSilentPoll();
  }, 30000);
});

onBeforeUnmount(() => {
  if (typeof document !== "undefined") {
    document.removeEventListener("pointerdown", onDocumentPointerDown);
    document.removeEventListener("visibilitychange", onLayoutPageVisible);
  }
  clearInterval(orderPollTimer);
  ownerRealtime.disconnect();
  deactivateTheme(); // strip data-owner-theme so customer/admin pages stay un-themed
});

watch(
  () => router.currentRoute.value.fullPath,
  () => {
    closeSettingsMenu();
  }
);
</script>

<style scoped>
.owner-bottom-dock {
  padding-top: 0.35rem;
  padding-bottom: calc(var(--safe-bottom) + 0.35rem);
}

.owner-dock-link {
  min-height: 2.3rem;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.14rem;
}

.owner-dock-icon {
  width: 0.82rem;
  height: 0.82rem;
}

.owner-settings-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.1rem;
  min-width: 2.1rem;
  border-radius: 9999px;
  border: 1px solid rgba(51, 65, 85, 0.85);
  background: rgba(15, 23, 42, 0.6);
  color: rgb(226, 232, 240);
  padding: 0.35rem;
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

.owner-settings-icon {
  width: 0.85rem;
  height: 0.85rem;
}

.owner-settings-trigger:hover {
  border-color: var(--color-secondary);
  color: var(--color-secondary);
}

.owner-settings-menu {
  position: absolute;
  inset-inline-end: 0;
  top: calc(100% + 0.5rem);
  z-index: 2200;
  min-width: 11rem;
  border-radius: 1rem;
  border: 1px solid rgba(51, 65, 85, 0.85);
  background: linear-gradient(180deg, rgba(2, 6, 23, 0.98), rgba(15, 23, 42, 0.96));
  padding: 0.45rem;
  box-shadow: 0 20px 45px rgba(2, 6, 23, 0.42);
  backdrop-filter: blur(18px);
}

.owner-settings-item {
  width: 100%;
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  border-radius: 0.8rem;
  padding: 0.7rem 0.8rem;
  color: rgb(226, 232, 240);
  font-size: 0.84rem;
  font-weight: 600;
  transition: background 0.2s ease, color 0.2s ease;
}

.owner-settings-section {
  padding: 0.6rem 0.8rem 0.2rem;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: rgb(100, 116, 139);
}
.owner-settings-section:first-child {
  padding-top: 0.2rem;
}

.owner-settings-item:hover {
  background: rgba(30, 41, 59, 0.92);
  color: var(--color-secondary);
}

.owner-settings-item:focus-visible {
  outline: 2px solid transparent;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.55);
}

.owner-settings-item-danger:hover {
  color: rgb(252, 165, 165);
}

.owner-settings-item-icon {
  width: 0.85rem;
  height: 0.85rem;
  flex-shrink: 0;
}

.owner-workspace-stage {
  z-index: 50;
}

.owner-main-nav {
  grid-template-columns: repeat(var(--nav-cols, 4), minmax(0, 1fr));
  gap: 0.5rem;
  border: 1px solid rgba(51, 65, 85, 0.7);
  border-radius: 1rem;
  background: linear-gradient(135deg, rgba(2, 6, 23, 0.86), rgba(3, 15, 35, 0.78));
  padding: 0.4rem;
  box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.15);
}

.owner-main-nav-item {
  min-height: 2.6rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(51, 65, 85, 0.35);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: rgb(203, 213, 225);
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.owner-main-nav-item:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.6);
}

.owner-nav-icon {
  width: 0.88rem;
  height: 0.88rem;
}

.owner-main-nav-item:hover {
  border-color: rgba(245, 158, 11, 0.55);
  background: rgba(15, 23, 42, 0.72);
  color: rgb(245, 158, 11);
}

.owner-main-nav-item[data-active="true"] {
  border-color: rgba(245, 158, 11, 0.85);
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(245, 158, 11, 0.08));
  color: rgb(245, 158, 11);
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.12) inset;
}

.owner-main-nav-item[data-urgent="true"] {
  border-color: rgba(245, 158, 11, 0.55);
  color: rgb(245, 158, 11);
}

.owner-orders-badge {
  position: absolute;
  top: -0.45rem;
  inset-inline-end: -0.55rem;
  min-width: 1.1rem;
  height: 1.1rem;
  border-radius: 9999px;
  background: rgb(245, 158, 11);
  color: rgb(0, 0, 0);
  font-size: 0.6rem;
  font-weight: 800;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.18rem;
  animation: owner-badge-pulse 2s ease-in-out infinite;
}

.owner-orders-badge-dock {
  position: absolute;
  top: -0.3rem;
  inset-inline-end: -0.35rem;
  min-width: 0.95rem;
  height: 0.95rem;
  border-radius: 9999px;
  background: rgb(245, 158, 11);
  color: rgb(0, 0, 0);
  font-size: 0.52rem;
  font-weight: 800;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.15rem;
  animation: owner-badge-pulse 2s ease-in-out infinite;
}

@keyframes owner-badge-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.7); }
  50% { box-shadow: 0 0 0 4px rgba(245, 158, 11, 0); }
}

@media (max-width: 640px) {
  .owner-workspace-stage {
    padding: 0.7rem;
  }

  .owner-bottom-dock {
    padding-top: 0.25rem;
    padding-bottom: calc(var(--safe-bottom) + 0.3rem);
  }

  .owner-dock-link {
    min-height: 2.12rem;
    padding-inline: 0.45rem;
    gap: 0.12rem;
    font-size: 0.62rem;
  }

  .owner-dock-icon {
    width: 0.78rem;
    height: 0.78rem;
  }

  .owner-settings-trigger {
    min-height: 1.95rem;
    min-width: 1.95rem;
    padding: 0.28rem;
  }

  .owner-settings-menu {
    min-width: 9.5rem;
    padding: 0.35rem;
    border-radius: 0.9rem;
  }

  .owner-settings-item {
    padding: 0.65rem 0.72rem;
    font-size: 0.8rem;
  }
}

/* Light-mode overrides for these scoped classes live in styles/tailwind.css —
   Vue's scoped compiler mishandles `:global(ancestor) .scoped-child`, so the
   owner light theme is centralised there as plain global rules. */
</style>
