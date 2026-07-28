<template>
  <!-- Restaurant header -->
  <div class="pt-4 pb-2">
    <header class="ui-hero-ribbon ui-reveal px-4 py-4">
      <div class="flex items-start gap-4">
        <!-- Logo -->
        <div class="h-16 w-16 shrink-0 rounded-xl overflow-hidden bg-slate-800 flex items-center justify-center">
          <img v-if="restaurant.logo_url" :src="restaurant.logo_url" :alt="restaurant.name" loading="eager" decoding="async" class="h-full w-full object-cover" @error="$event.target.style.display='none'" />
          <span v-else aria-hidden="true" class="text-2xl">{{ businessIcon(restaurant) }}</span>
        </div>
        <!-- Info -->
        <div class="flex-1 min-w-0">
          <p class="ui-kicker">{{ t('mktMenu.restaurantKicker') }}</p>
          <h1 class="ui-display text-xl font-semibold tracking-tight text-white leading-tight">{{ restaurant.name }}</h1>
          <p v-if="restaurant.tagline" class="mt-0.5 text-xs text-slate-400 line-clamp-1" :title="restaurant.tagline">{{ restaurant.tagline }}</p>
          <!-- Chips row -->
          <div class="mt-2 flex flex-wrap gap-1.5">
            <span
              class="ui-status-pill"
              :class="restaurant.is_open
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                : 'border-slate-700/60 bg-slate-800/50 text-slate-400'"
            >
              <span
                class="ui-live-dot"
                :class="restaurant.is_open ? 'bg-emerald-400' : 'bg-slate-500'"
                aria-hidden="true"
              />
              {{ restaurant.is_open ? t('mktMenu.open') : t('mktMenu.closed') }}
            </span>
            <!-- Rating chip -->
            <span v-if="restaurant.rating_average" class="ui-chip flex items-center gap-0.5 text-amber-400">
              <svg viewBox="0 0 12 12" class="h-2.5 w-2.5 fill-current shrink-0" aria-hidden="true"><path d="M6 1l1.39 2.82 3.11.45-2.25 2.19.53 3.09L6 8.12 3.22 9.55l.53-3.09L1.5 4.27l3.11-.45z"/></svg>
              <span class="tabular-nums">{{ restaurant.rating_average }}</span>
              <span class="text-slate-500 tabular-nums">({{ restaurant.rating_count }})</span>
            </span>
            <!-- Pre-order prep ETA chip ('Ready in ~X–Y min') -->
            <span v-if="prepEta" class="ui-chip flex items-center gap-1 text-sky-300" :title="t('common.estimate')">
              <AppIcon name="clock" class="h-3 w-3 shrink-0" aria-hidden="true" />
              {{ t('menu.etaReadyIn', { min: prepEta.min, max: prepEta.max }) }}
            </span>
            <span v-if="restaurant.cuisine_type" class="ui-chip">{{ restaurant.cuisine_type }}</span>
            <span v-if="restaurant.city" class="ui-chip">{{ restaurant.city }}</span>
            <span v-if="restaurant.delivery_enabled" class="ui-chip text-sky-300">
              {{ t('mktMenu.deliveryFee') }}: {{ Number(restaurant.delivery_fee) > 0 ? fmtPrice(restaurant.delivery_fee) : t('mktMenu.freeDelivery') }}
            </span>
            <span
              v-if="restaurant.delivery_enabled && Number(restaurant.delivery_minimum_order) > 0"
              class="ui-chip"
            >
              {{ t('mktMenu.minOrder', { amount: fmtPrice(restaurant.delivery_minimum_order) }) }}
            </span>
          </div>
        </div>
      </div>
      <!-- Opening hours (today + expandable week) -->
      <div v-if="todayHours" class="mt-2 pl-px">
        <button
          type="button"
          class="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 focus-visible:outline-none transition-colors"
          :aria-expanded="hoursExpanded"
          @click="hoursExpanded = !hoursExpanded"
        >
          <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3 shrink-0" aria-hidden="true"><circle cx="6" cy="6" r="4.5"/><path d="M6 3.5V6l1.5 1.5"/></svg>
          <span v-if="todayHours.closed" class="text-rose-400/80">{{ t('mktMenu.hoursClosedToday') }}</span>
          <span v-else>{{ t('mktMenu.hoursToday', { open: todayHours.open, close: todayHours.close }) }}</span>
          <span class="transition-transform" :class="hoursExpanded ? 'rotate-180' : ''" aria-hidden="true">▾</span>
        </button>
        <div v-if="hoursExpanded && weeklyHours" class="mt-1.5 overflow-hidden rounded-lg border border-slate-700/50 bg-slate-800/40 divide-y divide-slate-700/30">
          <div
            v-for="day in weeklyHours"
            :key="day.key"
            class="flex justify-between items-center px-2.5 py-1.5 text-[11px]"
            :class="day.isToday ? 'bg-slate-700/40 font-semibold text-slate-200' : 'text-slate-400'"
          >
            <span>{{ day.label }}</span>
            <span v-if="day.open" class="tabular-nums">{{ day.open }} – {{ day.close }}</span>
            <span v-else class="text-slate-500">–</span>
          </div>
        </div>
      </div>
      <!-- Share restaurant link -->
      <div class="mt-3 flex justify-end">
        <button
          class="ui-press inline-flex items-center gap-1.5 rounded-full border border-slate-700/60 bg-slate-900/50 px-3 py-1 text-xs font-medium text-slate-400 transition-colors hover:border-slate-500 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500/50"
          :aria-label="t('mktMenu.shareRestaurant')"
          @click="emit('share')"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><circle cx="12" cy="3" r="1.5"/><circle cx="4" cy="8" r="1.5"/><circle cx="12" cy="13" r="1.5"/><path d="M5.5 8.9l5 2.7M10.5 4.1l-5 2.7"/></svg>
          {{ menuLinkCopied ? t('mktMenu.linkCopied') : t('mktMenu.share') }}
        </button>
      </div>
    </header>
  </div>
</template>

<script setup>
// Restaurant header / "about" section of MarketplaceMenuPage.vue (customer
// menu-browsing page), extracted as a standalone presentational component
// (RISK FE-2). This is DISPLAY ONLY — logo, name, tagline, status/rating/ETA/
// delivery chips, the today+weekly opening-hours disclosure, and the share
// button. NO cart, add-to-cart, option-selection, checkout, or money logic
// lives here or is shared with it. All data (the restaurant object plus the
// parent-derived prepEta / todayHours / weeklyHours) is passed down as props;
// the share button forwards intent via the `share` emit so the parent keeps
// owning the navigator.share/clipboard logic and the `menuLinkCopied` flag
// (passed back in as a prop for the button label). The hours-expanded toggle
// is pure local UI state with no bearing outside this block, so it lives here.
// `fmtPrice` and `businessIcon` are passed down as function props (same
// convention as OwnerOrdersCashierModal's formatCurrency) so currency
// formatting and the business-type icon stay single-sourced in the parent.
import AppIcon from './AppIcon.vue';
import { ref } from 'vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The loaded restaurant/menu payload (display fields only). */
  restaurant: { type: Object, required: true },
  /** Pre-order prep estimate { min, max } for the ETA chip, or null. */
  prepEta: { type: Object, default: null },
  /** Today's opening hours { closed, open?, close? }, or null when no schedule. */
  todayHours: { type: Object, default: null },
  /** Full-week opening hours rows for the disclosure, or null. */
  weeklyHours: { type: Array, default: null },
  /** Whether the "share" fell back to clipboard-copy (drives the button label). */
  menuLinkCopied: { type: Boolean, default: false },
  /** Locale-aware currency formatter, owned by the parent. */
  fmtPrice: { type: Function, required: true },
  /** Business-type → emoji placeholder icon helper, owned by the parent. */
  businessIcon: { type: Function, required: true },
});

const emit = defineEmits(['share']);

// Pure local UI state: whether the weekly-hours disclosure is expanded.
const hoursExpanded = ref(false);
</script>
