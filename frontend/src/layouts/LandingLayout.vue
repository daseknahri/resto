<template>
  <div class="ui-shell">
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:start-2 focus:top-2 focus:z-[9999] focus:rounded-lg focus:bg-slate-900 focus:px-4 focus:py-2 focus:text-sm focus:text-white focus:outline-none focus:ring-2 focus:ring-[var(--color-secondary)]">{{ t('common.skipToMain') }}</a>
    <div class="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden="true">
      <div class="absolute ltr:-left-32 rtl:-right-32 -top-20 h-72 w-72 rounded-full bg-amber-400/10 blur-3xl"></div>
      <div class="absolute ltr:-right-20 rtl:-left-20 top-10 h-72 w-72 rounded-full bg-teal-400/10 blur-3xl"></div>
    </div>

    <header class="ui-header ui-fade-up relative z-[2000] overflow-visible">
      <div class="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <RouterLink to="/" class="flex min-w-0 items-center gap-3" :aria-label="t('landingLayout.title')">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-sm font-bold text-slate-950 shadow-lg shadow-black/30" :style="logoStyle" aria-hidden="true">
            RM
          </div>
          <div class="min-w-0" aria-hidden="true">
            <p class="truncate text-xs uppercase tracking-[0.24em] text-slate-400">{{ t("landingLayout.kicker") }}</p>
            <p class="ui-display truncate text-base font-semibold text-slate-100">{{ t("landingLayout.title") }}</p>
          </div>
        </RouterLink>

        <nav class="hidden items-center gap-2 rounded-full border border-slate-800/80 bg-slate-950/65 px-2 py-1.5 shadow-lg shadow-black/20 lg:flex" :aria-label="t('landingLayout.navDesktop')">
          <RouterLink class="ui-pill-nav whitespace-nowrap" to="/" :data-active="$route.path === '/'" :aria-current="$route.path === '/' ? 'page' : undefined" active-class="" exact-active-class="">{{ t("common.landing") }}</RouterLink>
          <RouterLink class="ui-pill-nav whitespace-nowrap" to="/demo" :data-active="$route.path === '/demo'" :aria-current="$route.path === '/demo' ? 'page' : undefined" active-class="" exact-active-class="">{{ t("common.liveDemo") }}</RouterLink>
          <RouterLink class="ui-pill-nav whitespace-nowrap" to="/get-started" :data-active="$route.path === '/get-started'" :aria-current="$route.path === '/get-started' ? 'page' : undefined" active-class="" exact-active-class="">{{ t("common.getStarted") }}</RouterLink>
          <RouterLink class="ui-pill-nav whitespace-nowrap" to="/contact" :data-active="$route.path === '/contact'" :aria-current="$route.path === '/contact' ? 'page' : undefined" active-class="" exact-active-class="">{{ t("common.contact") }}</RouterLink>
        </nav>

        <div class="flex items-center gap-1.5 sm:gap-2 min-w-0">
          <div class="hidden items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-[11px] font-medium text-emerald-100 xl:inline-flex">
            <span class="ui-live-dot bg-emerald-400" aria-hidden="true"></span>
            {{ t("home.heroLive") }}
          </div>
          <LanguageSwitcher dropdown />
          <RouterLink v-if="session.isPlatformAdmin" to="/admin-console" class="ui-btn-outline ui-touch-target hidden text-sm lg:inline-flex">{{ t("common.admin") }}</RouterLink>
          <RouterLink
            v-if="session.canEditTenantMenu"
            to="/owner"
            class="ui-btn-outline ui-touch-target inline-flex px-3 py-2 text-[11px] sm:px-4 sm:text-sm"
          >
            <AppIcon name="settings" class="me-1.5 h-3.5 w-3.5" aria-hidden="true" />
            {{ t("common.workspace") }}
          </RouterLink>
          <RouterLink
            v-if="customerStore.isAuthenticated"
            :to="{ name: 'customer-account' }"
            class="ui-btn-outline ui-touch-target inline-flex px-3 py-2 text-[11px] sm:px-4 sm:text-sm"
          >
            <AppIcon name="user" class="me-1.5 h-3.5 w-3.5" aria-hidden="true" />
            {{ t("common.myAccount") }}
          </RouterLink>
          <RouterLink v-if="!session.isAuthenticated" to="/signin" class="ui-btn-primary ui-touch-target inline-flex px-3 py-2 text-[11px] sm:px-5 sm:text-sm">{{ t("common.signIn") }}</RouterLink>
          <button v-else class="ui-btn-outline ui-touch-target inline-flex px-3 py-2 text-[11px] sm:px-5 sm:text-sm" @click="signOut">
            {{ t("common.signOut") }}
          </button>
        </div>
      </div>
      <div class="ui-divider"></div>
    </header>

    <nav class="ui-bottom-dock lg:hidden" :aria-label="t('landingLayout.navMobile')">
      <div class="ui-bottom-dock-grid grid-cols-4">
        <RouterLink class="ui-pill-nav flex flex-col items-center justify-center gap-0.5 px-2 py-1 text-center text-[10px] leading-tight" to="/" :data-active="$route.path === '/'" :aria-current="$route.path === '/' ? 'page' : undefined" active-class="" exact-active-class="">
          <AppIcon name="home" class="h-4 w-4" aria-hidden="true" />
          <span>{{ t("common.landing") }}</span>
        </RouterLink>
        <RouterLink class="ui-pill-nav flex flex-col items-center justify-center gap-0.5 px-2 py-1 text-center text-[10px] leading-tight" to="/demo" :data-active="$route.path === '/demo'" :aria-current="$route.path === '/demo' ? 'page' : undefined" active-class="" exact-active-class="">
          <AppIcon name="menu" class="h-4 w-4" aria-hidden="true" />
          <span>{{ t("common.demo") }}</span>
        </RouterLink>
        <RouterLink class="ui-pill-nav flex flex-col items-center justify-center gap-0.5 px-2 py-1 text-center text-[10px] leading-tight" to="/get-started" :data-active="$route.path === '/get-started'" :aria-current="$route.path === '/get-started' ? 'page' : undefined" active-class="" exact-active-class="">
          <AppIcon name="plus" class="h-4 w-4" aria-hidden="true" />
          <span>{{ t("common.getStarted") }}</span>
        </RouterLink>
        <RouterLink class="ui-pill-nav flex flex-col items-center justify-center gap-0.5 px-2 py-1 text-center text-[10px] leading-tight" to="/contact" :data-active="$route.path === '/contact'" :aria-current="$route.path === '/contact' ? 'page' : undefined" active-class="" exact-active-class="">
          <AppIcon name="chat" class="h-4 w-4" aria-hidden="true" />
          <span>{{ t("common.contact") }}</span>
        </RouterLink>
      </div>
    </nav>

    <main id="main-content" tabindex="-1" class="mx-auto w-full max-w-6xl px-4 ui-fade-up pb-[calc(var(--safe-bottom)+4rem)] lg:pb-0">
      <RouterView v-slot="{ Component, route: viewRoute }">
        <Transition name="ui-route" mode="out-in">
          <div :key="viewRoute.fullPath">
            <component :is="Component" />
          </div>
        </Transition>
      </RouterView>
    </main>

    <footer class="ui-footer pb-[calc(var(--safe-bottom)+4.5rem)] lg:pb-8">
      <div class="ui-reveal ui-panel-soft mx-auto grid w-full max-w-6xl gap-4 p-4 md:grid-cols-[minmax(0,1.15fr),minmax(0,0.45fr),minmax(0,0.45fr)] md:items-start">
        <div class="space-y-2">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-sm font-bold text-slate-950 shadow-lg shadow-black/30" :style="logoStyle" aria-hidden="true">
              RM
            </div>
            <div>
              <p class="ui-kicker">{{ t("landingLayout.kicker") }}</p>
              <p class="ui-display text-lg font-semibold text-white">{{ t("landingLayout.footerTitle") }}</p>
            </div>
          </div>
          <p class="max-w-xl text-sm text-slate-400">
            {{ t("home.heroSubtitle") }}
          </p>
          <div class="flex flex-wrap gap-2">
            <span class="ui-chip">{{ t("home.stats.launchTimeValue") }}</span>
            <span class="ui-chip">{{ t("home.stats.interfacesValue") }}</span>
            <span class="ui-chip">{{ supportEmail }}</span>
          </div>
        </div>

        <div class="space-y-3">
          <p id="footer-nav-getstarted" class="ui-kicker">{{ t("common.getStarted") }}</p>
          <nav aria-labelledby="footer-nav-getstarted">
            <ul class="flex flex-col gap-2 text-sm">
              <li>
                <RouterLink class="ui-top-link inline-flex items-center gap-2" to="/get-started">
                  <AppIcon name="plus" class="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{{ t("common.getStarted") }}</span>
                </RouterLink>
              </li>
              <li>
                <RouterLink class="ui-top-link inline-flex items-center gap-2" to="/demo">
                  <AppIcon name="eye" class="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{{ t("common.liveDemo") }}</span>
                </RouterLink>
              </li>
              <li>
                <RouterLink class="ui-top-link inline-flex items-center gap-2" to="/contact">
                  <AppIcon name="chat" class="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{{ t("common.contact") }}</span>
                </RouterLink>
              </li>
            </ul>
          </nav>
        </div>

        <div class="space-y-3">
          <p id="footer-nav-legal" class="ui-kicker">{{ t("common.legal") }}</p>
          <nav aria-labelledby="footer-nav-legal">
            <ul class="flex flex-col gap-2 text-sm">
              <li>
                <RouterLink class="ui-top-link inline-flex items-center gap-2" to="/privacy">
                  <AppIcon name="info" class="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{{ t("common.privacy") }}</span>
                </RouterLink>
              </li>
              <li>
                <RouterLink class="ui-top-link inline-flex items-center gap-2" to="/terms">
                  <AppIcon name="check" class="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{{ t("common.terms") }}</span>
                </RouterLink>
              </li>
            </ul>
          </nav>
          <p class="text-slate-500 text-sm mt-1">&copy; {{ year }}</p>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import LanguageSwitcher from "../components/LanguageSwitcher.vue";
import { useI18n } from "../composables/useI18n";
import { useSessionStore } from "../stores/session";
import { useCustomerStore } from "../stores/customer";

const router = useRouter();
const session = useSessionStore();
const customerStore = useCustomerStore();
const { t } = useI18n();
const year = new Date().getFullYear();
const supportEmail = import.meta.env.VITE_CONTACT_EMAIL || "contact@ibnbatoutaweb.com";

const logoStyle = computed(() => ({
  background: "linear-gradient(135deg, var(--color-primary), var(--color-secondary))",
}));

const signOut = async () => {
  await session.signOut();
  router.push({ name: "home" });
};

// Resolve the customer session so the header can show "My account" on the marketplace.
onMounted(() => { customerStore.fetchCustomer(); });
</script>
