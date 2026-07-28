<template>
  <div>
    <p class="ui-kicker">{{ t('waiterPage.settleTitle') }}</p>
    <p class="mt-0.5 tabular-nums text-xs text-slate-400">
      {{ order.table_label || ('#' + order.order_number) }} ·
      {{ fmtOrderPrice(settleOutstanding(order), order.currency) }}
    </p>
  </div>
  <!-- Item breakdown -->
  <ul v-if="order.items?.length" class="max-h-28 overflow-y-auto divide-y divide-slate-700/40 rounded-lg border border-slate-700/50 bg-slate-800/50" aria-label="Order items">
    <li
      v-for="item in order.items"
      :key="item.id"
      class="flex items-center justify-between gap-2 px-2.5 py-1.5 text-xs"
    >
      <span class="min-w-0 truncate text-slate-300"><span class="text-slate-500">{{ item.qty }}×</span> {{ item.dish_name }}</span>
      <span class="shrink-0 tabular-nums text-slate-400">{{ fmtOrderPrice((item.subtotal ?? item.unit_price * item.qty), order.currency) }}</span>
    </li>
  </ul>
  <!-- Split-by-seat toggle (only for dine-in/table orders with seat data) -->
  <div
    v-if="order.fulfillment_type === 'table'"
    class="flex items-center gap-1.5"
  >
    <button
      type="button"
      class="ui-press ui-touch-target flex-1 rounded-lg border py-1.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500/60"
      :class="splitBySeatMode
        ? 'border-violet-500/60 bg-violet-500/15 text-violet-300'
        : 'border-slate-600/70 bg-slate-800/60 text-slate-300 hover:border-slate-500 hover:text-slate-100'"
      @click="toggleSeatSplit"
    >{{ t('waiterPage.splitBySeat') }}</button>
  </div>

  <!-- Seat-split view -->
  <template v-if="splitBySeatMode">
    <div v-if="seatGroupsLoading" class="space-y-1.5">
      <div v-for="i in 2" :key="i" class="ui-skeleton h-10 rounded-lg" />
    </div>
    <div v-else-if="seatGroupsError" class="text-xs text-red-400">{{ seatGroupsError }}</div>
    <div v-else-if="seatGroups.length" class="space-y-1.5">
      <div
        v-for="seat in seatGroups"
        :key="seat.seat"
        class="flex items-center justify-between gap-2 rounded-lg border border-slate-700/60 bg-slate-800/50 px-3 py-2"
      >
        <div class="min-w-0 flex-1">
          <p class="text-xs font-semibold text-slate-200">{{ seatGroupLabel(seat) }}</p>
          <p class="text-[10px] text-slate-500">{{ seat.items.length }} {{ seat.items.length === 1 ? 'item' : 'items' }}</p>
        </div>
        <div class="flex shrink-0 items-center gap-1.5">
          <button
            class="ui-press ui-touch-target shrink-0 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1.5 text-xs font-semibold text-emerald-300 transition-colors hover:border-emerald-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500/60"
            @click="emit('payCashForSeat', seat)"
          >{{ t('waiterPage.payCash') }}</button>
          <button
            class="ui-press ui-touch-target shrink-0 rounded-lg border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/10 px-2.5 py-1.5 text-xs font-semibold text-[var(--color-secondary)] transition-colors hover:border-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
            @click="emit('payWalletForSeat', seat)"
          >{{ t('waiterPage.payWalletForSeat') }}</button>
        </div>
      </div>
    </div>
  </template>

  <!-- Standard settle controls (hidden when seat-split mode is on) -->
  <template v-else>
    <!-- Cash received input + change calculator -->
    <div class="rounded-lg border border-slate-700/50 bg-slate-800/40 p-3 space-y-2">
      <label class="block text-[11px] font-medium text-slate-400" for="waiter-cash-received">{{ t('waiterPage.cashReceived') }}</label>
      <input
        id="waiter-cash-received"
        v-model="cashReceived"
        type="number"
        inputmode="decimal"
        step="0.01"
        min="0"
        class="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm tabular-nums text-slate-100 focus:border-[var(--color-secondary)] focus:outline-none"
        :placeholder="fmtOrderPrice(settleOutstanding(order), order.currency)"
      />
      <div v-if="cashChange !== null" class="flex items-center justify-between text-sm tabular-nums">
        <span class="text-slate-400">{{ t('waiterPage.cashChange') }}</span>
        <span :class="Number(cashChange) >= 0 ? 'font-bold text-emerald-300' : 'font-bold text-red-400'">
          {{ Number(cashChange) >= 0 ? '+' : '' }}{{ fmtOrderPrice(Number(cashChange), order.currency) }}
        </span>
      </div>
    </div>
    <!-- Primary CTA: Cash full amount — one tap -->
    <button
      class="ui-press ui-touch-target w-full flex items-center justify-center gap-2 rounded-xl border border-emerald-500/50 bg-emerald-500/15 px-4 py-4 text-emerald-300 transition-colors hover:border-emerald-400 hover:bg-emerald-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
      @click="emit('payCash')"
    >
      <span class="text-xl" aria-hidden="true">💵</span>
      <span class="text-base font-bold">{{ t('waiterPage.cashFull', { amount: fmtOrderPrice(settleOutstanding(order), order.currency) }) }}</span>
    </button>
    <!-- Secondary CTA: Wallet — equally prominent -->
    <button
      class="ui-press ui-touch-target w-full flex items-center justify-center gap-2 rounded-xl border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/10 px-4 py-4 text-[var(--color-secondary)] transition-colors hover:border-[var(--color-secondary)] hover:bg-[var(--color-secondary)]/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
      @click="emit('payWallet')"
    >
      <span class="text-xl" aria-hidden="true">💳</span>
      <span class="text-base font-bold">{{ t('waiterPage.payWalletMethod') }}</span>
    </button>
    <!-- Collapsible split section -->
    <div class="rounded-lg border border-slate-700/60 bg-slate-800/40">
      <button
        type="button"
        class="ui-press ui-touch-target flex w-full items-center justify-between px-3 py-2.5 text-xs font-semibold text-slate-400 hover:text-slate-200 focus-visible:outline-none"
        :aria-expanded="splitSectionOpen"
        @click="splitSectionOpen = !splitSectionOpen"
      >
        <span>{{ t('waiterPage.splitSection') }}</span>
        <span class="text-slate-500 transition-transform" :class="splitSectionOpen ? 'rotate-180' : ''">▾</span>
      </button>
      <div v-if="splitSectionOpen" class="space-y-2 px-3 pb-3">
        <label class="block text-xs font-medium text-slate-300" :for="'settle-amount-' + order.id">
          {{ t('waiterPage.splitAmount') }}
        </label>
        <!-- Quick-split buttons: ÷2 ÷3 ÷4 ÷5 -->
        <div class="flex gap-1.5">
          <button
            v-for="n in [2, 3, 4, 5]"
            :key="n"
            type="button"
            class="ui-press ui-touch-target flex-1 rounded-lg border border-slate-600/70 bg-slate-800/60 py-1.5 text-xs font-semibold text-slate-300 transition-colors hover:border-slate-500 hover:text-slate-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
            @click="splitAmount = (settleOutstanding(order) / n).toFixed(2)"
          >÷{{ n }}</button>
        </div>
        <input
          :id="'settle-amount-' + order.id"
          v-model="splitAmount"
          type="number"
          inputmode="decimal"
          step="0.01"
          min="0.01"
          :max="settleOutstanding(order)"
          class="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm tabular-nums text-slate-100 focus:border-[var(--color-secondary)] focus:outline-none"
        />
        <p class="text-[11px] text-slate-500">{{ t('waiterPage.splitHint') }}</p>
        <div class="grid grid-cols-2 gap-2 pt-1">
          <button
            class="ui-press ui-touch-target flex flex-col items-center gap-1 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-3 text-emerald-300 transition-colors hover:border-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
            @click="emit('payCash')"
          >
            <span class="text-xl" aria-hidden="true">💵</span>
            <span class="text-sm font-semibold">{{ t('waiterPage.payCash') }}</span>
          </button>
          <button
            class="ui-press ui-touch-target flex flex-col items-center gap-1 rounded-xl border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/10 px-3 py-3 text-[var(--color-secondary)] transition-colors hover:border-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
            @click="emit('payWallet')"
          >
            <span class="text-xl" aria-hidden="true">💳</span>
            <span class="text-sm font-semibold">{{ t('waiterPage.payWalletMethod') }}</span>
          </button>
        </div>
      </div>
    </div>
  </template>

  <button
    class="ui-press ui-touch-target w-full px-3 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 focus-visible:outline-none"
    @click="emit('close')"
  >
    {{ t('common.cancel') }}
  </button>
</template>

<script setup>
// The inner body of WaiterPage.vue's settle sheet (cash / wallet / split-by-seat),
// extracted as a FRAGMENT child (RISK FE-2). Like the customer-rating form, it has
// no wrapper root, so its blocks stay direct children of the parent's role="dialog"
// panel — the panel's `space-y-3` rhythm and the parent-owned focus trap (querying
// that dialog via `settleDialogRef` + the shared FOCUSABLE_BILL selector) are both
// untouched. This is money-path UI, so it owns ZERO payment logic: every settle
// action stays in the parent and is invoked via an emit; the parent keeps the modal
// shell (Teleport / Transition / backdrop), the idempotency-key minting, the seat-
// split fetch, the cashReceived-clear watch, and the settleChooser state.
//
// Two-way form state (cashReceived / splitAmount / splitBySeatMode / splitSectionOpen)
// stays owned by the parent's refs via defineModel, so the parent's handlers read the
// exact same values. `cashChange` (a parent computed) and `settleOutstanding` /
// `fmtOrderPrice` / `seatGroupLabel` (parent helpers) come in as props. Actions are
// emits: close / loadSeatGroups / payCash / payWallet / payCashForSeat / payWalletForSeat.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The order being settled (settleChooser). */
  order: { type: Object, required: true },
  /** Per-seat groupings from the seat-split fetch (seatGroups). */
  seatGroups: { type: Array, default: () => [] },
  /** Whether the seat-split fetch is in flight (seatGroupsLoading). */
  seatGroupsLoading: { type: Boolean, default: false },
  /** Error text for the seat-split fetch, or '' (seatGroupsError). */
  seatGroupsError: { type: String, default: '' },
  /** Change due for the typed cash amount, or null (parent computed cashChange). */
  cashChange: { type: [String, Number], default: null },
  /** Helper: outstanding amount for an order (settleOutstanding). */
  settleOutstanding: { type: Function, required: true },
  /** Helper: format a price in the order's currency (fmtOrderPrice). */
  fmtOrderPrice: { type: Function, required: true },
  /** Helper: human-readable label for a seat group (seatGroupLabel). */
  seatGroupLabel: { type: Function, required: true },
});

/** Seat-split mode toggle (splitBySeatMode), two-way. */
const splitBySeatMode = defineModel('splitBySeatMode', { type: Boolean, default: false });
/** Cash-received input (cashReceived), two-way. */
const cashReceived = defineModel('cashReceived', { type: [String, Number], default: '' });
/** "Split amount" accordion open state (splitSectionOpen), two-way. */
const splitSectionOpen = defineModel('splitSectionOpen', { type: Boolean, default: false });
/** Split-amount input (splitAmount), two-way. */
const splitAmount = defineModel('splitAmount', { type: [String, Number], default: '' });

const emit = defineEmits([
  'close', 'loadSeatGroups', 'payCash', 'payWallet', 'payCashForSeat', 'payWalletForSeat',
]);

// Preserve the parent's inline toggle handler verbatim: flip the mode, and when
// turning it ON, ask the parent to (re)load the seat groups.
const toggleSeatSplit = () => {
  splitBySeatMode.value = !splitBySeatMode.value;
  if (splitBySeatMode.value) emit('loadSeatGroups');
};
</script>
