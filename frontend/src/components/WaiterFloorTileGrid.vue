<template>
  <div
    class="grid gap-3"
    style="grid-template-columns: repeat(auto-fill, minmax(140px, 1fr))"
  >
    <button
      v-for="tile in tiles"
      :key="tile.tableKey"
      class="ui-press ui-touch-target relative flex min-h-[120px] flex-col items-start gap-1 overflow-hidden rounded-2xl border p-3 text-start transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
      :class="floorTileClass(tile.tableStatus)"
      :aria-label="t('waiterPage.floorTileAriaLabel', { label: tile.tableLabel, status: t(`waiterPage.tableStatus_${tile.tableStatus}`) })"
      :aria-pressed="expandedKey === tile.tableKey"
      @click="emit('toggle', tile)"
    >
      <!-- "Ready to serve" pulse ring — overlays the status dot when food is ready -->
      <span
        v-if="tile.orders.some(o => o.status === 'ready')"
        class="absolute end-2 top-2 flex h-4 w-4 items-center justify-center"
        :title="t('waiterPage.floorReadyToServe')"
        aria-hidden="true"
      >
        <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
        <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
      </span>
      <!-- Status dot (hidden when ready pulse is shown) -->
      <span
        class="absolute end-2.5 top-2.5 h-2.5 w-2.5 rounded-full"
        :class="floorDotClass(tile.tableStatus)"
        aria-hidden="true"
      />

      <!-- Table label + active order count -->
      <span class="pe-4 text-base font-bold leading-tight text-white">{{ tile.tableLabel }}</span>
      <span
        v-if="tile.orders.length > 0"
        class="ms-auto me-6 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-amber-500/20 px-1 text-[9px] font-bold tabular-nums text-amber-300"
        :title="t('waiterPage.floorOrderCount', { n: tile.orders.length })"
      >{{ tile.orders.length }}</span>

      <!-- Capacity badge -->
      <span v-if="tile.tableCapacity" class="text-[10px] text-slate-400 tabular-nums">{{ t('waiterPage.floorCapacity', { n: tile.tableCapacity }) }}</span>

      <!-- Status label -->
      <span
        class="mt-auto rounded-full border px-2 py-0.5 text-[10px] font-semibold"
        :class="tableStatusBadgeClass(tile.tableStatus)"
      >{{ t(`waiterPage.tableStatus_${tile.tableStatus}`) }}</span>

      <!-- Outstanding + elapsed (when occupied) -->
      <template v-if="tile.orders.length > 0">
        <span class="tabular-nums text-xs font-bold text-white">
          {{ fmtOrderPrice(tile.totalOutstanding, tile.orders[0]?.currency) }}
        </span>
        <span
          v-if="tile.longestElapsedLabel"
          class="rounded-full border px-1.5 py-0.5 text-[9px] font-semibold tabular-nums"
          :class="tile.longestElapsedClass"
        >{{ tile.longestElapsedLabel }}</span>
      </template>
      <span v-else class="text-[10px] text-slate-500">{{ t('waiterPage.floorNoOrders') }}</span>

      <!-- Expand indicator -->
      <span
        v-if="tile.orders.length > 0"
        class="absolute bottom-2 end-2 text-[10px] text-slate-400 transition-transform"
        :class="expandedKey === tile.tableKey ? 'rotate-180' : ''"
        aria-hidden="true"
      >▾</span>
    </button>
  </div>
</template>

<script setup>
// Floor table-tile grid of WaiterPage.vue's floor view, extracted as a standalone
// child (RISK FE-2). It renders the tappable table tiles (status dot / ready pulse,
// table label + active-order count, capacity, status label, outstanding + longest-
// elapsed badge, expand indicator) and asks the parent to expand/collapse a tile via
// the `toggle` emit. The floor data (filteredFloorTiles), the expanded-tile state
// (expandedFloorTable) and the toggle/mark actions stay in the parent; the tile list,
// the expanded key, and the display helpers (floorTileClass / floorDotClass /
// tableStatusBadgeClass / fmtOrderPrice) are passed in as props.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The floor tiles to render (parent's filteredFloorTiles). */
  tiles: { type: Array, default: () => [] },
  /** The tableKey of the currently expanded tile, or '' / null. */
  expandedKey: { type: [String, Number], default: null },
  /** tableStatus => tile background class. */
  floorTileClass: { type: Function, required: true },
  /** tableStatus => status-dot class. */
  floorDotClass: { type: Function, required: true },
  /** tableStatus => status-badge class. */
  tableStatusBadgeClass: { type: Function, required: true },
  /** (amount, currency) => formatted price string. */
  fmtOrderPrice: { type: Function, required: true },
});

const emit = defineEmits(['toggle']);
</script>
