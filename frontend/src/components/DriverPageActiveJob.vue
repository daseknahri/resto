<template>
  <div class="sticky top-0 z-30 ui-panel p-0 overflow-hidden ui-reveal border-emerald-600/40">
    <!-- Hero header: status pill + payout always visible at a glance -->
    <div class="flex items-center justify-between gap-2 border-b border-slate-700/40 bg-slate-950/90 px-4 py-3 backdrop-blur-sm">
      <div class="flex items-center gap-2 min-w-0">
        <span class="ui-status-pill shrink-0">
          {{ statusLabel(job.status, job.business_type) }}
        </span>
        <p v-if="job.restaurant_name" class="truncate text-sm font-semibold text-slate-100">{{ job.restaurant_name }}</p>
        <p v-else class="text-xs text-slate-500">{{ t('driver.order') }} #{{ job.order_number }}</p>
      </div>
      <span class="shrink-0 text-base font-bold tabular-nums text-emerald-300">{{ fmtMoney(job.driver_payout) }}</span>
    </div>

    <div class="p-4 space-y-3 bg-slate-950/60">
      <!-- Order meta: distance + items count -->
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
        <p class="text-[11px] text-slate-500 shrink-0">{{ t('driver.order') }} #{{ job.order_number }}</p>
        <span v-if="job.distance_km != null" class="inline-flex items-center gap-1">
          <AppIcon name="location" class="h-3 w-3" aria-hidden="true" />{{ t('driver.distanceKm', { km: job.distance_km }) }}
        </span>
        <span v-if="job.items_count">{{ t('driver.itemsCount', { n: job.items_count }) }}</span>
      </div>

      <!-- Active address: one always-visible truncated line for the relevant destination.
           Before pickup → pickup address (amber); after pickup → dropoff address (emerald). -->
      <p
        v-if="job.status === 'picked_up' ? (job.delivery_address || job.delivery_lat) : (job.pickup_address || job.pickup_lat)"
        class="flex items-center gap-1.5 truncate text-sm"
        :title="job.status === 'picked_up' ? job.delivery_address : job.pickup_address"
      >
        <span
          class="flex h-5 w-5 shrink-0 items-center justify-center rounded-md"
          :class="job.status === 'picked_up' ? 'bg-emerald-500/15' : 'bg-amber-500/15'"
          aria-hidden="true"
        >
          <AppIcon name="location" class="h-3 w-3" :class="job.status === 'picked_up' ? 'text-emerald-300' : 'text-amber-300'" aria-hidden="true" />
        </span>
        <span class="truncate" :class="job.status === 'picked_up' ? 'text-emerald-200' : 'text-amber-200'">
          {{ job.status === 'picked_up' ? (job.delivery_address || t('driver.dropoff')) : (job.pickup_address || t('driver.pickup')) }}
        </span>
      </p>

      <!-- Food-ready ETA (owner's prep estimate) — when to be at the restaurant -->
      <div
        v-if="readyEta"
        class="inline-flex items-center gap-1.5 rounded-lg border border-emerald-600/30 bg-emerald-900/15 px-2.5 py-1 text-xs font-semibold text-emerald-300"
      >
        <span aria-hidden="true">⏱</span>
        <span>{{ t('driver.foodReady', { time: readyEta.clock }) }}</span>
        <span v-if="readyEta.mins > 0" class="font-normal text-emerald-400/70">· {{ t('driver.foodReadyIn', { minutes: readyEta.mins }) }}</span>
      </div>

      <!-- Cash to collect (COD) vs already paid — the driver must know -->
      <div
        v-if="job.collect_cash"
        class="flex items-center justify-between rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2.5"
      >
        <span class="text-xs font-semibold text-amber-200">{{ t('driver.collectCash') }}</span>
        <span class="text-lg font-bold tabular-nums text-amber-200">{{ fmtMoney(job.order_total) }}</span>
      </div>
      <div
        v-else-if="job.order_total"
        class="flex items-center gap-1.5 rounded-xl border border-emerald-600/30 bg-emerald-900/15 px-3 py-2.5 text-xs font-semibold text-emerald-300"
      >
        <AppIcon name="check" class="h-3.5 w-3.5" aria-hidden="true" />{{ t('driver.prepaid', { amount: fmtMoney(job.order_total) }) }}
      </div>

      <!-- ── PRIMARY HERO ACTIONS ── -->
      <!-- Reminder: confirm delivery with the customer's code -->
      <div
        v-if="nextAction && nextAction.to === 'delivered'"
        class="flex items-start gap-1.5 rounded-xl border border-sky-700/30 bg-sky-900/15 px-3 py-2.5 text-xs text-sky-300"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <AppIcon name="info" class="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span>{{ t('driver.codeReminder') }}</span>
      </div>

      <!-- BIG advance button — the ONE next action, 56px min for propped phone -->
      <button
        v-if="nextAction"
        class="ui-btn-primary ui-touch-target inline-flex w-full items-center justify-center gap-2 text-base font-bold"
        style="min-height: 56px"
        :disabled="busy"
        :aria-busy="busy"
        @click="emit('advance', nextAction.to)"
      >
        <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
        {{ busy ? t('common.loading') : nextAction.label }}
      </button>

      <!-- Correct-leg Navigate link — pinned below the advance button.
           Before pickup → link to pickup; after pickup → link to dropoff. -->
      <a
        v-if="navigateHref"
        :href="navigateHref"
        target="_blank" rel="noopener"
        class="ui-touch-target flex w-full items-center justify-center gap-2 rounded-xl border border-slate-600/60 bg-slate-900/50 px-4 py-3 text-sm font-semibold text-slate-200 transition-colors hover:border-slate-500/80 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
        style="min-height: 48px"
        :aria-label="t('driver.navigateTo')"
      >
        <AppIcon name="location" class="h-4 w-4 shrink-0 text-sky-300" aria-hidden="true" />
        {{ t('driver.navigateTo') }}
      </a>

      <!-- Fail / can't complete -->
      <button
        v-if="!failingOpen"
        class="ui-touch-target w-full rounded-xl border border-red-500/40 px-4 py-2 text-xs text-red-300 hover:border-red-400/70 hover:text-red-200 transition-colors disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-400"
        :disabled="busy"
        @click="openFail"
      >
        {{ t('driver.actionFailed') }}
      </button>
      <!-- Failure-reason picker -->
      <div v-else class="space-y-2 rounded-xl border border-red-500/40 bg-red-900/10 p-3">
        <p class="text-xs font-semibold text-red-200">{{ t('driver.failReasonTitle') }}</p>
        <button
          v-for="r in FAIL_REASONS"
          :key="r"
          class="ui-touch-target w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-start text-sm text-slate-200 hover:border-slate-500 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
          :disabled="busy"
          @click="submitFail(r)"
        >
          {{ t(`driver.failReason_${r}`) }}
        </button>
        <input
          v-model="failNote"
          maxlength="500"
          :placeholder="t('driver.failNotePlaceholder')"
          :aria-label="t('driver.failNotePlaceholder')"
          class="ui-input"
        />
        <button
          class="ui-touch-target w-full py-1 text-xs text-slate-400 hover:text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
          :disabled="busy"
          @click="failingOpen = false"
        >
          {{ t('driver.failCancel') }}
        </button>
      </div>
    </div>

    <!-- Supporting detail (expandable) — below the fold under the hero -->
    <div class="border-t border-slate-700/30">
      <button
        class="flex w-full items-center justify-between gap-2 px-4 py-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
        :aria-expanded="detailOpen"
        aria-controls="active-job-detail-panel"
        @click="emit('toggleDetail')"
      >
        <p class="text-xs font-medium text-slate-400">{{ t('driver.activeTitle') }}</p>
        <AppIcon :name="detailOpen ? 'chevronUp' : 'chevronDown'" class="h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
      </button>
      <div id="active-job-detail-panel">
        <template v-if="detailOpen">
          <div class="px-4 pb-4 space-y-3">
            <!-- Pickup / dropoff address links -->
            <div class="space-y-2">
              <a
                v-if="job.pickup_address || job.pickup_lat"
                :href="mapsLink(job.pickup_lat, job.pickup_lng, job.pickup_address)"
                target="_blank" rel="noopener"
                class="flex items-center gap-3 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-3 transition-colors hover:border-slate-600/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
                :aria-label="t('driver.pickup')"
              >
                <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/15">
                  <AppIcon name="location" class="h-4 w-4 text-amber-300" aria-hidden="true" />
                </span>
                <div class="min-w-0 flex-1">
                  <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.pickup') }}</p>
                  <p class="truncate text-sm text-slate-200" :title="job.pickup_address || undefined">{{ job.pickup_address || t('driver.openMaps') }}</p>
                </div>
                <AppIcon name="chevronRight" class="h-4 w-4 shrink-0 text-slate-600 rtl:scale-x-[-1]" aria-hidden="true" />
              </a>
              <a
                v-if="job.delivery_address || job.delivery_lat"
                :href="mapsLink(job.delivery_lat, job.delivery_lng, job.delivery_address)"
                target="_blank" rel="noopener"
                class="flex items-center gap-3 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-3 transition-colors hover:border-slate-600/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
                :aria-label="t('driver.dropoff')"
              >
                <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-500/15">
                  <AppIcon name="location" class="h-4 w-4 text-emerald-300" aria-hidden="true" />
                </span>
                <div class="min-w-0 flex-1">
                  <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.dropoff') }}</p>
                  <p class="truncate text-sm text-slate-200" :title="job.delivery_address || undefined">{{ job.delivery_address || t('driver.openMaps') }}</p>
                </div>
                <AppIcon name="chevronRight" class="h-4 w-4 shrink-0 text-slate-600 rtl:scale-x-[-1]" aria-hidden="true" />
              </a>

              <!-- Call the customer (only the assigned driver sees the phone) -->
              <a
                v-if="job.customer_phone"
                :href="`tel:${job.customer_phone}`"
                class="flex items-center gap-3 rounded-xl border border-sky-700/50 bg-sky-900/20 px-3 py-3 transition-colors hover:border-sky-600/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400"
                :aria-label="`${t('driver.callCustomer')}: ${job.customer_name || job.customer_phone}`"
              >
                <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sky-500/15">
                  <AppIcon name="phone" class="h-4 w-4 text-sky-300" aria-hidden="true" />
                </span>
                <div class="min-w-0 flex-1">
                  <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.callCustomer') }}</p>
                  <p class="truncate text-sm text-slate-200" :title="job.customer_name || job.customer_phone || undefined">{{ job.customer_name || job.customer_phone }}</p>
                </div>
                <span class="shrink-0 text-xs font-semibold text-sky-300">{{ t('driver.call') }}</span>
              </a>
              <!-- Call the restaurant / merchant — lets the driver check if food is ready -->
              <a
                v-if="job.restaurant_phone"
                :href="`tel:${job.restaurant_phone}`"
                class="flex items-center gap-3 rounded-xl border border-amber-700/50 bg-amber-900/15 px-3 py-3 transition-colors hover:border-amber-600/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400"
                :aria-label="`${t('driver.callRestaurant')}: ${job.restaurant_name || job.restaurant_phone}`"
              >
                <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/15">
                  <AppIcon name="phone" class="h-4 w-4 text-amber-300" aria-hidden="true" />
                </span>
                <div class="min-w-0 flex-1">
                  <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.callRestaurant') }}</p>
                  <p class="truncate text-sm text-slate-200" :title="job.restaurant_name || job.restaurant_phone || undefined">{{ job.restaurant_name || job.restaurant_phone }}</p>
                </div>
                <span class="shrink-0 text-xs font-semibold text-amber-300">{{ t('driver.call') }}</span>
              </a>
            </div>

            <!-- What's in the order -->
            <div v-if="job.items && job.items.length" class="rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-3">
              <p class="mb-2 text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.itemsTitle') }}</p>
              <ul class="space-y-1">
                <li v-for="(it, idx) in job.items" :key="idx" class="flex justify-between gap-2 text-sm text-slate-300">
                  <span class="truncate" :title="it.name">{{ it.name }}</span>
                  <span class="shrink-0 tabular-nums text-slate-400">×{{ it.qty }}</span>
                </li>
              </ul>
            </div>

            <!-- Payout row -->
            <div class="flex items-center justify-between rounded-xl border border-emerald-700/30 bg-emerald-900/10 px-3 py-2.5">
              <span class="text-xs font-medium text-slate-400">{{ t('driver.payout') }}</span>
              <span class="text-base font-bold tabular-nums text-emerald-300">{{ fmtMoney(job.driver_payout) }}</span>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
// Active-job hero of DriverPage.vue, extracted as a standalone child (RISK FE-2,
// the hardest tier — a core-state-coupled block). It renders the sticky hero for
// the driver's current job: status/payout header, active address, food-ready ETA,
// cash-to-collect, the ONE big advance button, the correct-leg navigate link, the
// fail / failure-reason picker, and the expandable detail panel (maps/phone links,
// items, payout).
//
// The coupling stays in the parent: `activeJob`, the `advance` action (which drives
// the code modal / status PATCH / earnings / rating flows), `busy`, the computeds
// (`nextAction`/`activeReadyEta`/`activeJobNavigateHref`) and `showActiveJobDetail`
// (whose parent watcher auto-expands on a new job and collapses when it clears) all
// remain in DriverPage.vue. This component receives them as props and forwards
// intent via emits:
//   • `advance(to)`      — the big next-action button (parent runs `advance`)
//   • `fail({reason, note})` — the failure-reason picker (parent runs advance('failed', …))
//   • `toggleDetail`     — the detail-panel disclosure (parent flips showActiveJobDetail)
// Only the fail-picker's own UI state (failingOpen / failNote / FAIL_REASONS) is
// local here. `statusLabel` / `fmtMoney` / `mapsLink` are passed as function props
// so they stay single-sourced in the parent.
import { ref } from 'vue';
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The driver's current active job (non-null; parent gates on activeJob). */
  job: { type: Object, required: true },
  /** The single next-action descriptor ({ to, label }) or null. */
  nextAction: { type: Object, default: null },
  /** Food-ready ETA ({ clock, mins }) or null. */
  readyEta: { type: Object, default: null },
  /** Maps deep-link for the current leg (pickup before pickup, dropoff after), or ''. */
  navigateHref: { type: String, default: '' },
  /** True while a status advance / fail request is in flight (parent-owned). */
  busy: { type: Boolean, default: false },
  /** Whether the supporting-detail panel is expanded (parent-owned + watcher-driven). */
  detailOpen: { type: Boolean, default: false },
  /** Status → label formatter (status, business_type) => string. */
  statusLabel: { type: Function, required: true },
  /** Money formatter (value) => string. */
  fmtMoney: { type: Function, required: true },
  /** Maps-link builder (lat, lng, address) => href. */
  mapsLink: { type: Function, required: true },
});

const emit = defineEmits(['advance', 'fail', 'toggleDetail']);

// Fail-picker UI state (local — the parent only learns the chosen reason + note).
const FAIL_REASONS = ['customer_no_show', 'bad_address', 'driver_unable', 'other'];
const failingOpen = ref(false);
const failNote = ref('');

const openFail = () => {
  failNote.value = '';
  failingOpen.value = true;
};

const submitFail = (reason) => {
  failingOpen.value = false;
  emit('fail', { reason, note: failNote.value });
};
</script>
