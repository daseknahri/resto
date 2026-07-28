<template>
  <!-- Cashier-mode big-total modal — tap settle button to open -->
  <Teleport to="body">
    <Transition name="ui-fade">
      <div
        v-if="order"
        class="fixed inset-0 z-[3500] flex items-end justify-center sm:items-center"
        role="dialog"
        :aria-label="t('ownerOrders.cashierModalTitle')"
        @click.self="emit('close')"
      >
        <div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" aria-hidden="true" @click="emit('close')" />
        <div class="relative z-10 w-full max-w-sm rounded-t-3xl border border-slate-700/60 bg-slate-900 px-6 pb-8 pt-6 text-center shadow-2xl sm:rounded-2xl">
          <p class="text-sm font-medium uppercase tracking-widest text-slate-400">{{ t('ownerOrders.cashierModalTitle') }}</p>
          <p class="mt-2 font-mono text-6xl font-extrabold tabular-nums text-emerald-300 sm:text-7xl">
            {{ formatCurrency(order.total, order.currency) }}
          </p>
          <p v-if="order.table_label" class="mt-2 text-sm text-slate-400">
            {{ t('ownerOrders.fulfillmentTable', { table: order.table_label }) }}
          </p>
          <p class="mt-1 text-sm text-slate-500">#{{ order.order_number }}</p>
          <div class="mt-6 flex gap-3">
            <button
              type="button"
              class="ui-btn-outline ui-press flex-1 py-3 text-sm"
              @click="emit('close')"
            >{{ t('common.cancel') }}</button>
            <button
              type="button"
              class="ui-press flex-[2] rounded-xl bg-emerald-600 py-3 text-sm font-semibold text-white shadow-md hover:bg-emerald-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
              :disabled="settling"
              @click="emit('settle', order)"
            >
              <span v-if="settling" class="inline-block animate-spin h-4 w-4 border-2 border-white/60 border-t-white rounded-full mr-2 align-middle" aria-hidden="true" />
              {{ order.status === 'ready' ? t('ownerOrders.settleAndClose') : t('ownerOrders.markPaid') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
// Cashier-mode big-total modal of OwnerOrders.vue, extracted as a standalone
// presentational child (RISK FE-2). The `cashierOrder` state, the settle API
// call (`settleOrder`) and the `settlingOrderId` guard all stay owned by the
// parent (OwnerOrders.vue) — this component only renders the big-total screen
// for whatever order the parent passes in, and asks the parent to close it or
// settle it via emits. `formatCurrency` is passed down as a function (same
// convention as DriverPageDeliveryHistory's `fmtMoney`) so currency formatting
// stays single-sourced in the parent.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The order driving the modal ({ total, currency, table_label, order_number, status, id }); null = closed. */
  order: { type: Object, default: null },
  /** True while this order's settle request is in flight (drives the spinner + disabled state). */
  settling: { type: Boolean, default: false },
  /** Currency formatter (amount, currency) => string, owned by the parent. */
  formatCurrency: { type: Function, required: true },
});

const emit = defineEmits(['close', 'settle']);
</script>
