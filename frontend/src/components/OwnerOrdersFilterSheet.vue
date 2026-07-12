<template>
  <!-- ── FILTER SHEET — bottom drawer for fulfillment / payment / date filters ── -->
  <Teleport to="body">
    <Transition name="ui-fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[2200] flex items-end justify-center"
        role="dialog"
        aria-modal="true"
        :aria-label="t('ownerOrders.filterSheetTitle')"
        @keydown.esc="emit('close')"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" @click="emit('close')" />
        <!-- Panel -->
        <div class="relative z-10 w-full max-w-lg rounded-t-2xl bg-slate-900 border border-slate-700/60 shadow-2xl flex flex-col max-h-[80dvh]">
          <!-- Handle + header -->
          <div class="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 shrink-0">
            <h2 class="text-base font-bold text-white">{{ t('ownerOrders.filterSheetTitle') }}</h2>
            <div class="flex items-center gap-2">
              <button
                v-if="activeFilterCount > 0"
                class="ui-press rounded-full border border-slate-700 px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200"
                @click="emit('clear')"
              >{{ t('ownerOrders.clearFilters') }}</button>
              <button
                class="ui-press flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-200"
                :aria-label="t('common.close')"
                @click="emit('close')"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5" aria-hidden="true">
                  <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z"/>
                </svg>
              </button>
            </div>
          </div>
          <!-- Filter content -->
          <div class="overflow-y-auto flex-1 px-4 py-4 space-y-5">
            <!-- Date filter -->
            <div class="space-y-2">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('ownerOrders.dateAll') }}</p>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="d in dateTabs"
                  :key="d.value"
                  type="button"
                  :aria-pressed="activeDateFilter === d.value"
                  class="ui-state-chip ui-press"
                  :data-active="activeDateFilter === d.value || undefined"
                  @click="emit('set-date-filter', d.value)"
                >{{ d.label }}</button>
              </div>
              <!-- Custom date-range inputs -->
              <div v-if="activeDateFilter === 'custom'" class="flex flex-wrap items-center gap-1.5 pt-1">
                <label class="text-xs text-slate-400" for="fs-date-from">{{ t('ownerOrders.dateFrom') }}</label>
                <input
                  id="fs-date-from"
                  type="date"
                  class="ui-input py-1 text-xs"
                  :value="customDateFrom"
                  :max="customDateTo || undefined"
                  @input="emit('set-custom-date-from', $event.target.value)"
                />
                <label class="text-xs text-slate-400" for="fs-date-to">{{ t('ownerOrders.dateTo') }}</label>
                <input
                  id="fs-date-to"
                  type="date"
                  class="ui-input py-1 text-xs"
                  :value="customDateTo"
                  :min="customDateFrom || undefined"
                  @input="emit('set-custom-date-to', $event.target.value)"
                />
              </div>
            </div>

            <!-- Fulfillment-type filter (only when 2+ types in the order list) -->
            <div v-if="fulfillmentTabs.length" class="space-y-2">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('ownerOrders.fulfillmentFilter') }}</p>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="tab in fulfillmentTabs"
                  :key="tab.value"
                  type="button"
                  :aria-pressed="activeFulfillmentType === tab.value"
                  class="ui-state-chip ui-press"
                  :data-active="activeFulfillmentType === tab.value || undefined"
                  @click="emit('set-fulfillment-type', tab.value)"
                >{{ tab.label }}</button>
              </div>
            </div>

            <!-- Payment status filter -->
            <div class="space-y-2">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('ownerOrders.paymentFilter') }}</p>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="p in paymentStatusTabs"
                  :key="p.value"
                  type="button"
                  :aria-pressed="activePaymentStatus === p.value"
                  class="ui-state-chip ui-press"
                  :data-active="activePaymentStatus === p.value || undefined"
                  @click="emit('set-payment-status', p.value)"
                >
                  {{ p.label }}
                  <span
                    v-if="p.count > 0"
                    class="ms-1 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-slate-700/80 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums leading-none"
                  >{{ p.count }}</span>
                </button>
              </div>
            </div>
          </div>
          <!-- Apply / close -->
          <div class="border-t border-slate-800 px-4 py-3 shrink-0">
            <button
              class="ui-btn-primary w-full py-2.5 text-sm font-semibold"
              @click="emit('close')"
            >{{ t('common.close') }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
// Filter bottom-sheet of OwnerOrders.vue, extracted as a standalone
// presentational child (RISK FE-2). All filter state (activeDateFilter,
// customDateFrom/To, activeFulfillmentType, activePaymentStatus) and the
// derived tab lists (dateTabs, fulfillmentTabs, paymentStatusTabs) stay
// owned by the parent — they're also read outside this sheet (header filter
// chip strip, the filteredOrders computed, history export params). This
// component only renders the drawer body and asks the parent to apply
// mutations via emits; it never touches order fetch/poll/status-mutation
// logic.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Whether the sheet is open. */
  open: { type: Boolean, default: false },
  /** Currently selected date-filter value ('all' | 'today' | 'yesterday' | 'week' | 'custom'). */
  activeDateFilter: { type: String, default: 'all' },
  /** Custom range "from" date (yyyy-mm-dd), only relevant when activeDateFilter === 'custom'. */
  customDateFrom: { type: String, default: '' },
  /** Custom range "to" date (yyyy-mm-dd), only relevant when activeDateFilter === 'custom'. */
  customDateTo: { type: String, default: '' },
  /** Currently selected fulfillment-type filter ('' | 'pickup' | 'delivery' | 'table'). */
  activeFulfillmentType: { type: String, default: '' },
  /** Currently selected payment-status filter ('' | 'unpaid' | 'paid'). */
  activePaymentStatus: { type: String, default: '' },
  /** Count of non-default filter values, drives the "clear" button visibility. */
  activeFilterCount: { type: Number, default: 0 },
  /** { value, label } tabs for the date filter. */
  dateTabs: { type: Array, default: () => [] },
  /** { value, label } tabs for the fulfillment-type filter (empty when <2 types present). */
  fulfillmentTabs: { type: Array, default: () => [] },
  /** { value, label, count } tabs for the payment-status filter. */
  paymentStatusTabs: { type: Array, default: () => [] },
});

const emit = defineEmits([
  'close',
  'clear',
  'set-date-filter',
  'set-custom-date-from',
  'set-custom-date-to',
  'set-fulfillment-type',
  'set-payment-status',
]);
</script>
