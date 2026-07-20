<template>
  <article
    class="ui-surface-lift ui-reveal overflow-hidden rounded-2xl border transition-colors"
    :class="statusCardClass(order.status)"
    :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
  >
    <!-- Card header -->
    <div class="flex items-start justify-between gap-3 px-4 pt-4 pb-3">
      <div class="min-w-0">
        <p class="truncate text-xl font-bold leading-tight text-white" :title="orderHeadline(order)">
          {{ orderHeadline(order) }}
        </p>
        <p class="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs">
          <span class="tabular-nums font-medium text-slate-300">#{{ order.order_number }}</span>
          <span aria-hidden="true" class="text-slate-600">·</span>
          <span :class="timeUrgencyClass(order.created_at, order.status)">{{ timeAgo(order.created_at) }}</span>
          <template v-if="order.customer_name">
            <span aria-hidden="true" class="text-slate-600">·</span>
            <span>{{ order.customer_name }}</span>
          </template>
          <template v-if="order.section_name">
            <span aria-hidden="true" class="text-slate-600">·</span>
            <span class="text-slate-500">{{ order.section_name }}</span>
          </template>
        </p>
        <span
          v-if="order.scheduled_for"
          class="mt-1 inline-flex items-center gap-1 rounded-full border border-violet-500/30 bg-violet-500/15 px-2 py-0.5 text-[10px] font-semibold text-violet-300"
        >
          <span aria-hidden="true">🗓️</span> {{ formatScheduledFor(order.scheduled_for) }}
        </span>
        <span
          v-if="order.fulfillment_type === 'delivery' && order.delivery_job"
          class="mt-1 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold"
          :class="waiterDjChipClass(order.delivery_job.status)"
        >
          <span
            v-if="order.delivery_job.status === 'searching'"
            class="block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400 motion-safe:animate-pulse"
            aria-hidden="true"
          />
          <span v-else aria-hidden="true">🛵</span>
          {{ waiterDjChipLabel(order.delivery_job) }}
        </span>
      </div>
      <div v-if="showElapsed" class="mt-0.5 flex shrink-0 flex-col items-end gap-1">
        <span
          class="rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
          :class="statusChipClass(order.status)"
        >{{ t(`waiterPage.status_${order.status}`) }}</span>
        <span
          v-if="orderElapsedLabel(order)"
          class="rounded-full border px-2 py-0.5 text-[9px] font-semibold tabular-nums"
          :class="orderElapsedClass(order)"
        >{{ orderElapsedLabel(order) }}</span>
      </div>
      <span
        v-else
        class="mt-0.5 shrink-0 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
        :class="statusChipClass(order.status)"
      >{{ t(`waiterPage.status_${order.status}`) }}</span>
    </div>
    <!-- Items -->
    <ul class="space-y-0.5 border-t px-4 py-2.5" :class="statusBorderClass(order.status)">
      <template v-for="(item, idx) in order.items" :key="idx">
        <WaiterOrderItem
          :item="item"
          :held="isItemHeld(item, order)"
          :can-manage="canManage"
          :can-comp="canCompPaidOrder(order)"
          :can-void="canVoidPaidOrder(order)"
          :ready-toggleable="itemReadyStatuses.has(order.status)"
          :not-terminal="!terminalStatuses.has(order.status)"
          :comping="compingItemId === item.id"
          :voiding="voidingItemId === item.id"
          @toggle-ready="emit('toggleItemReady', item)"
          @comp="emit('compItem', item)"
          @void="emit('voidItem', item)"
        />
        <!-- Combo sub-lines -->
        <template v-if="showCombos && item.combo_components?.length">
          <li
            v-for="comp in item.combo_components"
            :key="comp.dish_id"
            class="flex items-center gap-2 ps-6 py-0.5 text-[11px] text-slate-500"
          >
            <span aria-hidden="true">↳</span>
            <span>{{ comp.name }} ×{{ comp.qty * item.qty }}</span>
          </li>
        </template>
      </template>
    </ul>
    <!-- Notes row -->
    <div v-if="order.customer_note || order.owner_note" class="space-y-1 border-t px-4 py-2.5" :class="statusBorderClass(order.status)">
      <p v-if="order.customer_note" class="flex gap-2 text-xs text-slate-400">
        <span class="shrink-0 font-semibold text-slate-300">{{ t('waiterPage.customerNote') }}:</span>
        <span>{{ order.customer_note }}</span>
      </p>
      <p v-if="order.owner_note" class="flex gap-2 text-xs text-amber-300/90">
        <span class="shrink-0 font-semibold">{{ t('waiterPage.staffNote') }}:</span>
        <span>{{ order.owner_note }}</span>
      </p>
    </div>
    <!-- ETA + total + payment status -->
    <div class="border-t px-4 py-2" :class="statusBorderClass(order.status)">
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span v-if="order.estimated_ready_minutes" class="tabular-nums text-xs text-slate-500">
          {{ t('waiterPage.eta', { minutes: order.estimated_ready_minutes }) }}
        </span>
        <span class="tabular-nums text-sm font-bold text-white">{{ fmtOrderPrice(order.total, order.currency) }}</span>
        <span
          class="rounded-full border px-2 py-0.5 text-[10px] font-semibold"
          :class="order.payment_status === 'paid'
            ? 'border-emerald-500/30 bg-emerald-500/12 text-emerald-300'
            : 'border-amber-500/30 bg-amber-500/12 text-amber-300'"
        >{{ order.payment_status === 'paid' ? t('ownerOrders.paid') : t('ownerOrders.unpaid') }}</span>
      </div>
      <p v-if="Number(order.amount_paid) > 0 && order.payment_status !== 'paid'" class="mt-0.5 text-[11px] tabular-nums text-amber-400">
        {{ t('waiterPage.paidSoFar', { paid: fmtOrderPrice(order.amount_paid, order.currency), left: fmtOrderPrice(order.outstanding, order.currency) }) }}
      </p>
    </div>
    <!-- Action footer — primary CTA + compact secondaries + overflow -->
    <div class="space-y-2 border-t px-4 py-3" :class="statusBorderClass(order.status)">
      <button
        v-if="canManage && waiter.nextStatus(order)"
        class="ui-press ui-touch-target w-full rounded-xl py-3 text-sm font-bold tracking-wide shadow-sm transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
        :class="[actionBtnClass(order.status), waiter.updatingOrderIds.has(order.id) ? 'opacity-50 pointer-events-none' : '']"
        :disabled="waiter.updatingOrderIds.has(order.id)"
        :aria-busy="waiter.updatingOrderIds.has(order.id)"
        @click="emit('advance')"
      >
        <span v-if="waiter.updatingOrderIds.has(order.id)" class="inline-flex items-center justify-center gap-1.5" aria-hidden="true">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
        </span>
        <span v-else>{{ actionLabel(order) }}</span>
      </button>
      <button
        v-else-if="canManage && order.payment_status !== 'paid'"
        class="ui-press ui-touch-target w-full rounded-xl border border-emerald-500/50 bg-emerald-500/15 py-3 text-sm font-bold text-emerald-300 transition-colors hover:border-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
        :disabled="waiter.updatingOrderIds.has(order.id)"
        @click="emit('settle')"
      ><span aria-hidden="true">💵</span> {{ order.status === 'ready' ? t('ownerOrders.settleAndClose') : t('ownerOrders.markPaid') }}</button>
      <span v-else-if="canManage" class="block text-center text-xs italic text-slate-500">{{ t('waiterPage.handedOff') }}</span>
      <div class="flex items-center gap-1.5">
        <button
          v-if="canManage && waiter.nextStatus(order) && order.payment_status !== 'paid'"
          class="ui-press ui-touch-target shrink-0 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-300 transition-colors hover:border-emerald-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500/40"
          :disabled="waiter.updatingOrderIds.has(order.id)"
          @click="emit('settle')"
        ><span aria-hidden="true">💵</span></button>
        <button
          v-if="canManage && order.fulfillment_type === 'table' && appendableTableStatuses.has(order.status) && order.payment_status !== 'paid'"
          class="ui-press ui-touch-target shrink-0 rounded-xl border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-300 transition-colors hover:border-sky-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-500/40"
          @click="emit('append')"
        ><span aria-hidden="true">+</span> {{ t('waiterPage.addItems') }}</button>
        <button
          v-if="canManage && lowestHeldCourse(order) !== null && !terminalStatuses.has(order.status)"
          class="ui-press ui-touch-target shrink-0 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-300 transition-colors hover:border-amber-400 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber-500/40"
          :disabled="firingCourseOrderId === order.id"
          @click="emit('fireCourse')"
        >{{ firingCourseOrderId === order.id ? t('waiterPage.firingCourse') : t('waiterPage.fireCourse', { n: lowestHeldCourse(order) }) }}</button>
        <button
          v-else-if="canManage && itemReadyStatuses.has(order.status) && order.items?.some(it => !it.is_voided && !it.is_ready)"
          class="ui-press ui-touch-target shrink-0 rounded-xl border border-emerald-600/50 bg-emerald-600/10 px-3 py-2 text-xs font-semibold text-emerald-300 transition-colors hover:border-emerald-500 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500/40"
          :disabled="allReadyBusyIds.has(order.id)"
          @click="emit('allReady')"
        >✓ {{ t('waiterPage.allReadyBtn') }}</button>
        <button
          class="ui-press ui-touch-target ms-auto shrink-0 rounded-xl border border-slate-600/70 bg-slate-800/50 px-3 py-2 text-xs font-semibold text-slate-400 transition-colors hover:border-slate-500 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-500/40"
          :aria-label="t('common.more')"
          @click="emit('overflow')"
        >…</button>
      </div>
    </div>
  </article>
</template>

<script setup>
// Unified waiter order card of WaiterPage.vue (RISK FE-2). The waiter "order
// card" existed as three near-identical copies (table-grouped / non-table / flat
// list) that differed by exactly two features: the non-table variant shows an
// elapsed-time badge next to the status chip (showElapsed), and the grouped/non-
// table variants render combo sub-lines while the flat list does not (showCombos).
// Both are gated so each variant's DOM is byte-preserved. This one component now
// backs all three loops, DRYing ~450 lines.
//
// The card owns only presentation: it embeds WaiterOrderItem for the item list and
// re-emits its events; the parent keeps the order data, the waiter store, every
// action, and all display helpers (passed as function props). Actions are emits:
// advance / settle / append / fireCourse / allReady / overflow (order-scoped, the
// parent supplies `order` from its v-for), and toggleItemReady / compItem /
// voidItem (payload: the item).
import WaiterOrderItem from './WaiterOrderItem.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The order to render. */
  order: { type: Object, required: true },
  /** Row index within the loop (staggered --ui-delay reveal). */
  index: { type: Number, default: 0 },
  /** Whether the waiter can manage orders. */
  canManage: { type: Boolean, default: false },
  /** The waiter store (nextStatus / updatingOrderIds). */
  waiter: { type: Object, required: true },
  /** Id of the order whose fire-course request is in flight, or null. */
  firingCourseOrderId: { type: [Number, String], default: null },
  /** Set of order ids whose mark-all-ready is in flight. */
  allReadyBusyIds: { type: Object, default: () => new Set() },
  /** Id of the item whose comp request is in flight, or null. */
  compingItemId: { type: [Number, String], default: null },
  /** Id of the item whose void request is in flight, or null. */
  voidingItemId: { type: [Number, String], default: null },
  /** Kitchen-active order statuses (Set). */
  itemReadyStatuses: { type: Object, required: true },
  /** Terminal order statuses (Set). */
  terminalStatuses: { type: Object, required: true },
  /** Table statuses that allow appending items (Set). */
  appendableTableStatuses: { type: Object, required: true },
  /** Variant flag: show the elapsed-time badge (non-table list). */
  showElapsed: { type: Boolean, default: false },
  /** Variant flag: render combo sub-lines (grouped / non-table lists). */
  showCombos: { type: Boolean, default: false },
  // ── display helpers (parent-owned, passed as function props) ──
  statusCardClass: { type: Function, required: true },
  orderHeadline: { type: Function, required: true },
  timeUrgencyClass: { type: Function, required: true },
  timeAgo: { type: Function, required: true },
  formatScheduledFor: { type: Function, required: true },
  waiterDjChipClass: { type: Function, required: true },
  waiterDjChipLabel: { type: Function, required: true },
  statusChipClass: { type: Function, required: true },
  statusBorderClass: { type: Function, required: true },
  isItemHeld: { type: Function, required: true },
  canCompPaidOrder: { type: Function, required: true },
  canVoidPaidOrder: { type: Function, required: true },
  fmtOrderPrice: { type: Function, required: true },
  actionBtnClass: { type: Function, required: true },
  actionLabel: { type: Function, required: true },
  lowestHeldCourse: { type: Function, required: true },
  orderElapsedLabel: { type: Function, required: true },
  orderElapsedClass: { type: Function, required: true },
});

const emit = defineEmits([
  'advance', 'settle', 'append', 'fireCourse', 'allReady', 'overflow',
  'toggleItemReady', 'compItem', 'voidItem',
]);
</script>
