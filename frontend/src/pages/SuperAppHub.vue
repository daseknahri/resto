<template>
  <div class="space-y-10 px-4 py-10 md:space-y-14 md:py-14">

    <!-- ── IDENTITY HERO ─────────────────────────────────────────────────── -->
    <div class="ui-hero-stage ui-reveal">
      <div class="pointer-events-none absolute -right-16 -top-16 h-72 w-72 rounded-full bg-amber-400/12 blur-3xl" aria-hidden="true"></div>
      <div class="pointer-events-none absolute -left-16 bottom-0 h-72 w-72 rounded-full bg-teal-400/14 blur-3xl" aria-hidden="true"></div>
      <div class="relative p-6 sm:p-8 md:p-12">
        <div class="max-w-2xl space-y-5">
          <div class="ui-chip-strong w-fit">
            <span class="h-1.5 w-1.5 rounded-full bg-emerald-400" aria-hidden="true"></span>
            {{ t('superAppHub.heroKicker') }}
          </div>
          <h1 class="ui-display text-4xl font-bold leading-[1.1] tracking-tight text-white md:text-5xl lg:text-6xl">
            {{ t('superAppHub.heroTitle', { platform: platformName }) }}
          </h1>
          <p class="text-base leading-relaxed text-slate-300 md:text-lg">
            {{ t('superAppHub.heroSubtitle') }}
          </p>

          <!-- AUTH state -->
          <div class="flex flex-wrap items-center gap-3 pt-1">
            <template v-if="customerStore.isAuthenticated">
              <RouterLink
                :to="{ name: 'customer-account' }"
                class="ui-btn-primary ui-touch-target inline-flex items-center gap-2"
              >
                <span aria-hidden="true">👤</span>
                {{ t('superAppHub.signInGreeting', { name: customerStore.displayName }) }}
              </RouterLink>
              <RouterLink
                :to="{ name: 'customer-account' }"
                class="ui-btn-outline ui-touch-target text-sm"
              >
                {{ t('superAppHub.myAccount') }}
              </RouterLink>
            </template>
            <template v-else>
              <button
                type="button"
                class="ui-btn-primary ui-touch-target inline-flex items-center gap-2"
                @click="showAuthModal = true"
              >
                <span aria-hidden="true">🔑</span>
                {{ t('superAppHub.signInCta') }}
              </button>
            </template>
          </div>

          <!-- Low-key partner link -->
          <p class="text-sm text-slate-500">
            <RouterLink
              :to="{ name: 'business' }"
              class="ui-top-link inline-flex items-center gap-1.5"
            >
              <AppIcon name="settings" class="h-3.5 w-3.5" aria-hidden="true" />
              {{ t('superAppHub.partnerLink') }}
            </RouterLink>
          </p>
        </div>
      </div>
    </div>

    <!-- ── SERVICE LAUNCHER GRID ─────────────────────────────────────────── -->
    <section aria-labelledby="services-heading">
      <h2 id="services-heading" class="sr-only">{{ t('home.verticalsTitle') }}</h2>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <template v-for="(svc, idx) in services" :key="svc.id">
          <component
            :is="svc.status === 'live' ? 'RouterLink' : 'div'"
            v-bind="svc.status === 'live' ? { to: serviceRoute(svc) } : {}"
            class="ui-glass ui-reveal flex flex-col gap-4 p-5 md:p-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
            :class="svc.status === 'coming_soon' ? 'cursor-default opacity-60' : 'ui-press cursor-pointer'"
            :style="{ '--ui-delay': (idx * 56) + 'ms' }"
            :aria-disabled="svc.status === 'coming_soon' ? 'true' : undefined"
          >
            <!-- Icon tile -->
            <div
              class="flex h-12 w-12 items-center justify-center rounded-2xl text-2xl"
              :class="ACCENT_CLASSES[svc.accent]?.tile ?? 'border border-slate-600/40 bg-slate-700/20'"
              aria-hidden="true"
            >{{ svc.icon }}</div>

            <!-- Text -->
            <div class="flex-1 space-y-1.5">
              <div class="flex items-center gap-2">
                <p class="text-sm font-semibold text-white">{{ t('services.' + svc.id + 'Title') }}</p>
                <span
                  v-if="svc.status === 'coming_soon'"
                  class="rounded-full border border-slate-600/60 bg-slate-800/60 px-2 py-0.5 text-[10px] font-medium text-slate-400"
                >{{ t('services.comingSoon') }}</span>
              </div>
              <p class="text-sm leading-relaxed text-slate-400">{{ t('services.' + svc.id + 'Desc') }}</p>
            </div>

            <!-- CTA pill — live only -->
            <span
              v-if="svc.status === 'live'"
              class="inline-flex w-fit items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors"
              :class="ACCENT_CLASSES[svc.accent]?.pill ?? 'border-slate-500/40 bg-slate-500/8 text-slate-300'"
              aria-hidden="true"
            >
              {{ t('home.verticalCta') }}
              <AppIcon name="arrowRight" class="h-3 w-3 rtl:scale-x-[-1]" aria-hidden="true" />
            </span>
          </component>
        </template>
      </div>
    </section>

    <!-- ── PARTNER / OPEN YOUR BUSINESS CTA ────────────────────────────── -->
    <!-- Distinct B2B invite — not a service tile, styled as an editorial strip
         so it reads separately from the consumer grid above. -->
    <section aria-labelledby="partner-strip-heading" class="ui-reveal">
      <div class="ui-glass relative overflow-hidden rounded-3xl p-6 sm:p-8">
        <!-- Subtle background accent -->
        <div class="pointer-events-none absolute -right-12 -top-12 h-48 w-48 rounded-full bg-violet-400/10 blur-3xl" aria-hidden="true"></div>
        <div class="pointer-events-none absolute -bottom-8 -left-8 h-36 w-36 rounded-full bg-sky-400/8 blur-2xl" aria-hidden="true"></div>

        <div class="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
          <!-- Icon -->
          <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-violet-500/30 bg-violet-500/10 text-2xl" aria-hidden="true">
            🏪
          </div>

          <!-- Text -->
          <div class="min-w-0 flex-1 space-y-1">
            <p id="partner-strip-heading" class="ui-kicker text-violet-400">{{ t('superAppHub.partnerKicker') }}</p>
            <h2 class="text-base font-semibold text-white sm:text-lg">{{ t('superAppHub.partnerTitle') }}</h2>
            <p class="text-sm leading-relaxed text-slate-400">{{ t('superAppHub.partnerBody') }}</p>
          </div>

          <!-- CTA -->
          <RouterLink
            :to="{ name: 'lead' }"
            class="inline-flex shrink-0 items-center gap-2 rounded-full border border-violet-500/40 bg-violet-500/10 px-5 py-2.5 text-sm font-semibold text-violet-200 transition-colors hover:border-violet-400/70 hover:bg-violet-500/18 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/60 focus-visible:ring-offset-1 focus-visible:ring-offset-slate-950 ui-press"
          >
            {{ t('superAppHub.partnerCta') }}
            <AppIcon name="arrowRight" class="h-3.5 w-3.5 rtl:scale-x-[-1]" aria-hidden="true" />
          </RouterLink>
        </div>
      </div>
    </section>

    <!-- ── AUTH MODAL ────────────────────────────────────────────────────── -->
    <CustomerAuthModal
      v-if="showAuthModal"
      @close="showAuthModal = false"
      @authenticated="showAuthModal = false"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import CustomerAuthModal from '../components/CustomerAuthModal.vue';
import { useI18n } from '../composables/useI18n';
import { useCustomerStore } from '../stores/customer';
import { getServices } from '../lib/services';
import { PLATFORM_NAME } from '../lib/brand';

const { t } = useI18n();
const customerStore = useCustomerStore();
const showAuthModal = ref(false);
const platformName = PLATFORM_NAME;

// Status-adjust the service grid by the platform's enabled_verticals (P0).
// Until the session loads, platform is null → getServices returns all as-is.
const services = computed(() => getServices(customerStore.platform?.enabled_verticals));

onMounted(() => {
  customerStore.fetchCustomer();
});

// Full literal Tailwind class strings per accent — never computed by string concat
// so that the Tailwind scanner can reliably detect all classes.
const ACCENT_CLASSES = {
  amber:   { tile: 'border border-amber-500/30 bg-amber-500/10',     pill: 'border-amber-500/40 bg-amber-500/8 text-amber-300 hover:border-amber-500/70 hover:bg-amber-500/15'   },
  indigo:  { tile: 'border border-indigo-500/30 bg-indigo-500/10',   pill: 'border-indigo-500/40 bg-indigo-500/8 text-indigo-300 hover:border-indigo-500/70 hover:bg-indigo-500/15' },
  emerald: { tile: 'border border-emerald-500/30 bg-emerald-500/10', pill: 'border-emerald-500/40 bg-emerald-500/8 text-emerald-300 hover:border-emerald-500/70 hover:bg-emerald-500/15' },
  rose:    { tile: 'border border-rose-500/30 bg-rose-500/10',       pill: 'border-rose-500/40 bg-rose-500/8 text-rose-300 hover:border-rose-500/70 hover:bg-rose-500/15'     },
  sky:     { tile: 'border border-sky-500/30 bg-sky-500/10',         pill: 'border-sky-500/40 bg-sky-500/8 text-sky-300 hover:border-sky-500/70 hover:bg-sky-500/15'       },
  violet:  { tile: 'border border-violet-500/30 bg-violet-500/10',   pill: 'border-violet-500/40 bg-violet-500/8 text-violet-300 hover:border-violet-500/70 hover:bg-violet-500/15' },
};

/**
 * Resolve the router target for a service tile.
 * lens  → marketplace route with ?type= (and ?sub= for pharmacy)
 * route → named route directly
 */
function serviceRoute(svc) {
  if (svc.kind === 'lens') {
    const query = svc.subtype
      ? { type: svc.lens, sub: svc.subtype }
      : { type: svc.lens };
    return { name: 'marketplace', query };
  }
  return { name: svc.routeName };
}
</script>
