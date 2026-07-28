<template>
  <li
    class="flex items-start gap-2.5 py-0.5 text-sm"
    :class="(item.is_voided || item.is_comped) ? 'text-slate-500' : (held ? 'opacity-60 text-amber-300/70' : 'text-slate-300')"
  >
    <span
class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-700/80 bg-slate-800/70 text-[10px] font-bold tabular-nums"
      :class="(item.is_voided || item.is_comped) ? 'text-slate-500' : 'text-slate-100'">
      {{ item.qty }}
    </span>
    <span
class="min-w-0 flex-1 leading-snug"
      :class="[(item.is_voided || item.is_comped) ? 'line-through text-slate-500' : (item.is_ready ? 'line-through text-slate-500' : '')]">
      {{ item.dish_name }}
    </span>
    <span v-if="item.note" class="shrink-0 text-[10px] italic text-slate-500 leading-snug">({{ item.note }})</span>
    <!-- Course chip -->
    <span
      v-if="(item.course ?? 0) > 0 && !item.is_voided && !item.is_comped"
      class="shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold leading-none"
      :class="held
        ? 'border-amber-500/40 bg-amber-500/10 text-amber-400'
        : 'border-slate-600/50 bg-slate-700/30 text-slate-400'"
    >{{ held ? t('waiterPage.heldChip') : t('waiterPage.courseChip', { n: item.course }) }}</span>
    <span
      v-if="item.is_voided"
      class="shrink-0 rounded-full border border-red-500/30 bg-red-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-red-400 leading-none"
    >{{ t('waiterPage.voidedBadge') }}</span>
    <span
      v-else-if="item.is_comped"
      class="shrink-0 rounded-full border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-amber-400 leading-none"
    >{{ t('waiterPage.compedBadge') }}</span>
    <!-- Tap-to-ready: tappable when order is in a kitchen-active status -->
    <button
      v-else-if="canManage && !item.is_voided && readyToggleable"
      class="ui-press ui-touch-target shrink-0 flex items-center justify-center rounded-full w-6 h-6 border transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500/60"
      :class="item.is_ready
        ? 'border-emerald-500/60 bg-emerald-500/15 text-emerald-400'
        : 'border-slate-600/60 bg-slate-800/50 text-slate-600 hover:border-emerald-500/40 hover:text-emerald-500/60'"
      :aria-label="item.is_ready ? t('waiterPage.markItemNotReady') : t('waiterPage.markItemReady')"
      :aria-pressed="item.is_ready"
      @click.stop="emit('toggleReady')"
    >
      <span class="text-[10px] font-bold leading-none" aria-hidden="true">✓</span>
    </button>
    <span v-else-if="item.is_ready" class="shrink-0 text-[10px] font-semibold text-emerald-500/80 leading-snug">✓</span>
    <button
      v-if="canManage && !item.is_voided && !item.is_comped && notTerminal && canComp"
      class="ui-press shrink-0 rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-amber-500/10 hover:text-amber-400 active:text-amber-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber-500/60"
      :aria-label="t('waiterPage.compItem')"
      :disabled="comping"
      @click.stop="emit('comp')"
    >
      <svg viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4" aria-hidden="true"><path d="M9.586 2a2 2 0 0 1 1.414.586l2.414 2.414a2 2 0 0 1 .586 1.414V7H2V4a2 2 0 0 1 2-2h5.586ZM2 8v4a2 2 0 0 0 2 2h1V8H2Zm5 0v6h5a2 2 0 0 0 2-2V8H7ZM5.5 3a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Z"/></svg>
    </button>
    <button
      v-if="canManage && !item.is_voided && !item.is_comped && notTerminal && canVoid"
      class="ui-press shrink-0 rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-red-500/10 hover:text-red-400 active:text-red-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500/60"
      :aria-label="t('waiterPage.voidItem')"
      :disabled="voiding"
      @click.stop="emit('void')"
    >
      <svg viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4" aria-hidden="true"><path d="M3.75 7.25a.75.75 0 0 0 0 1.5h8.5a.75.75 0 0 0 0-1.5h-8.5Z"/></svg>
    </button>
  </li>
</template>

<script setup>
// A single order-item row of WaiterPage.vue's order cards, extracted as a
// standalone child (RISK FE-2). The item <li> markup was byte-identical (bar
// comments) across three of the four order-card loops (table-grouped, non-table,
// flat-list), so this one component DRYs all three. Display + three affordances:
// tap-to-ready / comp / void, forwarded to the parent as `toggleReady` / `comp` /
// `void` emits (the parent supplies (order, item) from its v-for scope). All the
// order-derived flags (held / canManage / canComp / canVoid / readyToggleable /
// notTerminal / comping / voiding) are computed in the parent and passed as props,
// so the item stays context-free. Combo sub-lines remain the parent's sibling
// <template> (they read `item` from the same v-for), so their scoping is unchanged.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The order item to render. */
  item: { type: Object, required: true },
  /** Whether this item is course-held (isItemHeld). */
  held: { type: Boolean, default: false },
  /** Whether the waiter can manage orders (drives all affordances). */
  canManage: { type: Boolean, default: false },
  /** Whether comping is allowed for the parent order (canCompPaidOrder). */
  canComp: { type: Boolean, default: false },
  /** Whether voiding is allowed for the parent order (canVoidPaidOrder). */
  canVoid: { type: Boolean, default: false },
  /** Whether the order is in a kitchen-active status (ITEM_READY_STATUSES). */
  readyToggleable: { type: Boolean, default: false },
  /** Whether the order is NOT in a terminal status. */
  notTerminal: { type: Boolean, default: false },
  /** True while THIS item's comp request is in flight. */
  comping: { type: Boolean, default: false },
  /** True while THIS item's void request is in flight. */
  voiding: { type: Boolean, default: false },
});

const emit = defineEmits(['toggleReady', 'comp', 'void']);
</script>
