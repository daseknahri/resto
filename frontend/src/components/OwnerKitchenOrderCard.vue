<template>
  <article
    class="kitchen-card ui-reveal"
    :class="cardClass(order.status)"
    :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
    role="listitem"
  >
    <!-- Status strip at top -->
    <div class="kitchen-strip" :class="stripClass(order.status)" />

    <!-- Order headline -->
    <div class="flex items-start justify-between gap-3 px-4 pt-4">
      <div class="min-w-0 flex-1">
        <p class="kitchen-headline truncate" :class="headlineColorClass(order.status)" :title="orderHeadline(order)">
          {{ orderHeadline(order) }}
        </p>
        <p class="mt-1 text-xs font-medium text-slate-500 tabular-nums">
          #{{ order.order_number }} · {{ timeAgo(order.created_at) }}<span v-if="order.customer_name"> · {{ order.customer_name }}</span>
        </p>
        <!-- Advance-order scheduled badge -->
        <span
          v-if="order.scheduled_for"
          class="mt-1 inline-flex items-center gap-1 rounded-full border border-violet-500/30 bg-violet-500/15 px-2 py-0.5 text-[10px] font-semibold text-violet-300"
        >
          <span aria-hidden="true">🗓️</span> {{ formatScheduledFor(order.scheduled_for) }}
        </span>
        <!-- Due-soon badge — a scheduled order now inside its prep window -->
        <span
          v-if="kitchenDueSoon(order)"
          class="mt-1 ms-1 inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-300 motion-safe:animate-pulse"
        >
          <span aria-hidden="true">⏱</span> {{ t('kitchen.dueSoon') }}
        </span>
        <!-- Delivery job status chip — kitchen staff visibility -->
        <span
          v-if="order.fulfillment_type === 'delivery' && order.delivery_job"
          class="mt-1 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold"
          :class="djChipClass(order.delivery_job.status)"
        >
          <span
            v-if="order.delivery_job.status === 'searching'"
            class="block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400 motion-safe:animate-pulse"
            aria-hidden="true"
          />
          <span v-else aria-hidden="true">🛵</span>
          {{ djChipLabel(order.delivery_job) }}
        </span>
      </div>
      <div class="flex shrink-0 flex-col items-end gap-2">
        <!-- Elapsed timer badge (amber ≥10m, red ≥20m from created_at) -->
        <span
          class="rounded-full border px-2.5 py-0.5 text-xs font-bold tabular-nums"
          :class="elapsedBadgeClass(elapsedMinutes(order))"
          :aria-label="elapsedLabel(order)"
        >{{ elapsedLabel(order) }}</span>
        <!-- Status chip -->
        <span
          class="rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-widest"
          :class="chipClass(order.status)"
        >{{ t(`kitchen.status_${order.status}`) }}</span>
      </div>
    </div>

    <!-- Items header: ready progress pill -->
    <p class="sr-only">{{ t('kitchen.tapItemReady') }}</p>
    <div v-if="orderReadyCount(order).total > 0" class="mt-4 flex items-center justify-between px-4 mb-1">
      <span class="text-[11px] font-medium text-slate-500">{{ t('kitchen.tapItemReady') }}</span>
      <span
        class="rounded-full border px-2 py-0.5 text-[11px] tabular-nums font-semibold transition-colors"
        :class="orderReadyCount(order).done === orderReadyCount(order).total
          ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/25'
          : 'text-slate-400 bg-slate-800/60 border-slate-700/40'"
      >{{ orderReadyCount(order).done }}/{{ orderReadyCount(order).total }}</span>
    </div>
    <ul class="mt-2 flex-1 divide-y divide-slate-700/30 overflow-y-auto px-4" :aria-label="t('kitchen.orderItems')">
      <li
        v-for="(item, idx) in order.items"
        :key="item.id ?? idx"
        class="kitchen-item select-none"
      >
        <!-- Voided items: show struck-out label only, no toggle interaction -->
        <div
          v-if="item.is_voided"
          class="flex items-baseline gap-2.5 px-2 py-2 opacity-30 line-through"
          :aria-label="t('kitchen.itemVoided', { name: item.dish_name })"
        >
          <span class="kitchen-qty" :class="headlineColorClass(order.status)" aria-hidden="true">{{ item.qty }}×</span>
          <span class="kitchen-name font-medium">{{ item.dish_name }}</span>
        </div>
        <button
          v-else-if="item.id != null"
          type="button"
          class="flex w-full items-baseline gap-2.5 cursor-pointer ui-press text-start rounded-lg px-2 py-2 -mx-2 transition-colors hover:bg-slate-700/30"
          :class="[item.is_ready ? 'opacity-40 line-through' : '', isItemHeld(item, order) ? 'opacity-50' : '', item.station && prepStation && item.station !== prepStation ? 'opacity-30' : '']"
          :title="t('kitchen.tapItemReady')"
          :aria-pressed="item.is_ready"
          @click="emit('toggleItem', order, item)"
        >
          <span class="kitchen-qty" :class="headlineColorClass(order.status)" aria-hidden="true">{{ item.qty }}×</span>
          <span class="kitchen-name font-medium">{{ item.dish_name }}</span>
          <span v-if="item.note" class="ms-1 shrink-0 text-[11px] italic text-slate-500">({{ item.note }})</span>
          <!-- Right-side chips: station + course + checkmark -->
          <span class="ms-auto shrink-0 flex items-center gap-1">
            <!-- Station chip -->
            <span
              v-if="item.station && !item.is_ready"
              class="rounded-full border px-1.5 py-0.5 text-[9px] font-bold leading-none"
              :class="prepStation && item.station !== prepStation
                ? 'border-slate-700/30 bg-transparent text-slate-600'
                : 'border-sky-500/40 bg-sky-500/10 text-sky-400'"
            >{{ item.station }}</span>
            <!-- Course chip -->
            <span
              v-if="(item.course ?? 0) > 0 && !item.is_ready"
              class="rounded-full border px-1.5 py-0.5 text-[9px] font-bold leading-none"
              :class="isItemHeld(item, order)
                ? 'border-amber-500/50 bg-amber-500/10 text-amber-400'
                : 'border-slate-600/50 bg-slate-700/30 text-slate-400'"
            >{{ isItemHeld(item, order) ? `${t('waiterPage.heldChip')} · ${t('waiterPage.courseChip', { n: item.course })}` : t('waiterPage.courseChip', { n: item.course }) }}</span>
            <!-- Checkmark when item ready -->
            <span v-if="item.is_ready" class="text-emerald-400" aria-hidden="true">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4" aria-hidden="true">
                <path fill-rule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clip-rule="evenodd"/>
              </svg>
            </span>
          </span>
        </button>
        <template v-else>
          <span class="kitchen-qty px-2 py-2" :class="headlineColorClass(order.status)" aria-hidden="true">{{ item.qty }}×</span>
          <span class="kitchen-name font-medium py-2">{{ item.dish_name }}</span>
          <span v-if="item.note" class="ms-1 shrink-0 text-[11px] italic text-slate-500">({{ item.note }})</span>
        </template>
        <!-- Combo sub-lines -->
        <template v-if="item.combo_components?.length">
          <div
            v-for="comp in item.combo_components"
            :key="comp.dish_id"
            class="flex items-baseline gap-1.5 ps-6 py-0.5 text-[11px] text-slate-500"
          >
            <span aria-hidden="true">↳</span>
            <span>{{ comp.name }} ×{{ comp.qty * item.qty }}</span>
          </div>
        </template>
      </li>
    </ul>

    <!-- Notes -->
    <div v-if="order.customer_note || order.owner_note" class="mt-3 space-y-1.5 border-t border-slate-700/40 px-4 pt-3 text-xs">
      <p v-if="order.customer_note" class="flex items-start gap-1.5 rounded-lg border border-amber-500/25 bg-amber-500/8 px-2.5 py-1.5 text-amber-200">
        <span class="mt-px shrink-0 font-semibold">{{ t("kitchen.noteCustomer") }}:</span>
        <span>{{ order.customer_note }}</span>
      </p>
      <p v-if="order.owner_note" class="flex items-start gap-1.5 text-amber-300/80">
        <span class="mt-px shrink-0 font-semibold">{{ t("kitchen.noteStaff") }}:</span>
        <span>{{ order.owner_note }}</span>
      </p>
    </div>

    <!-- Action button -->
    <div class="mt-auto space-y-2 px-4 pb-4 pt-4">
      <!-- Fire course button (owner/expediter) -->
      <button
        v-if="lowestHeldCourse(order) !== null"
        type="button"
        class="ui-btn-outline ui-press w-full gap-1.5 border-amber-500/30 text-amber-300/90 hover:border-amber-400/50 hover:text-amber-200 text-xs"
        :disabled="firingCourseOrderId === order.id"
        @click="emit('fireCourse', order)"
      >{{ firingCourseOrderId === order.id ? t('waiterPage.firingCourse') : t('waiterPage.fireCourse', { n: lowestHeldCourse(order) }) }}</button>
      <!-- Mark all items ready at once -->
      <button
        v-if="hasUnreadyItems(order)"
        type="button"
        class="ui-btn-outline ui-press w-full gap-1.5 border-emerald-500/30 text-emerald-300/90 hover:border-emerald-400/50 hover:text-emerald-200 text-xs"
        :aria-label="`${t('kitchen.markAllReady')} — #${order.order_number}`"
        @click="emit('markAllReady', order)"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0" aria-hidden="true">
          <path fill-rule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clip-rule="evenodd"/>
        </svg>
        {{ t('kitchen.markAllReady') }}
      </button>
      <button
        v-if="waiter.nextStatus(order)"
        class="ui-btn-primary ui-touch-target w-full rounded-xl py-3 text-sm font-bold tracking-wide focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
        :class="[actionBtnClass(order.status), waiter.updatingOrderIds.has(order.id) ? 'opacity-50 pointer-events-none' : '', allItemsReady(order) && !waiter.updatingOrderIds.has(order.id) ? 'ring-2 ring-emerald-300/40 shadow-md shadow-emerald-500/20' : '']"
        :disabled="waiter.updatingOrderIds.has(order.id)"
        :aria-busy="waiter.updatingOrderIds.has(order.id)"
        :aria-label="`${actionLabel(order)} — #${order.order_number}`"
        @click="emit('advance', order.id)"
      >
        <span v-if="waiter.updatingOrderIds.has(order.id)" class="animate-pulse" aria-hidden="true">…</span>
        <span v-else>{{ actionLabel(order) }}</span>
      </button>
      <p v-else class="text-center text-xs italic text-slate-500">{{ t("kitchen.handedOff") }}</p>
      <button
        class="ui-btn-outline ui-press w-full gap-1.5"
        :aria-label="`${t('ownerOrders.printTicket')} — #${order.order_number}`"
        @click="emit('printTicket', order)"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0" aria-hidden="true">
          <path fill-rule="evenodd" d="M4 2a1.5 1.5 0 0 0-1.5 1.5v2.879a2.25 2.25 0 0 0-.659 1.591v3.158A2.25 2.25 0 0 0 4.09 13.5H4.5v.5A1.5 1.5 0 0 0 6 15.5h4a1.5 1.5 0 0 0 1.5-1.5v-.5h.41a2.25 2.25 0 0 0 2.249-2.372l-.21-3.158A2.25 2.25 0 0 0 13.5 6.379V3.5A1.5 1.5 0 0 0 12 2H4Zm8.5 4.379-.097-.172A.75.75 0 0 0 11.75 6h-7.5a.75.75 0 0 0-.653.207L3.5 6.379V3.5a.5.5 0 0 1 .5-.5h8a.5.5 0 0 1 .5.5v2.879ZM10 8.5a.5.5 0 0 1 .5.5v4.5a.5.5 0 0 1-.5.5H6a.5.5 0 0 1-.5-.5V9a.5.5 0 0 1 .5-.5h4Z" clip-rule="evenodd"/>
        </svg>
        {{ t("ownerOrders.printTicket") }}
      </button>
    </div>
  </article>
</template>

<script setup>
// Kitchen order card of OwnerKitchen.vue, extracted as a standalone child (RISK
// FE-2, the most coupled block in the app). It renders one order tile: headline +
// badges, the tap-to-ready item list (with held/station/course chips + combo
// sub-lines), notes, and the action bar (fire-course / mark-all-ready / advance /
// print).
//
// The coupling stays in the parent (OwnerKitchen.vue): the whole `activeOrders`
// grid + `prepStation`, the `waiter` store (nextStatus / updatingOrderIds), the
// `firingCourseOrderId` guard, and every action (toggleItem / fireCourse /
// markAllReady / advance / printTicket) — the card forwards those as emits. All
// the DISPLAY helpers (class/label/count/held/course computeds) are passed down as
// function props so they stay single-sourced in the parent AND keep the parent's
// reactive deps (e.g. the elapsed-time now-ticker read inside elapsedLabel is
// tracked by THIS card's render, so the timer badge still ticks live). `index`
// drives the same staggered reveal the inline v-for used.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The order to render. */
  order: { type: Object, required: true },
  /** Row index within the grid — drives the staggered --ui-delay reveal. */
  index: { type: Number, default: 0 },
  /** Active prep-station filter ('' = all) — dims non-matching items. */
  prepStation: { type: String, default: '' },
  /** Id of the order whose fire-course request is in flight, or null. */
  firingCourseOrderId: { type: [Number, String], default: null },
  /** The waiter store (nextStatus / updatingOrderIds) — owned by the parent. */
  waiter: { type: Object, required: true },
  // ── display helpers (parent-owned, passed as function props) ──
  cardClass: { type: Function, required: true },
  stripClass: { type: Function, required: true },
  headlineColorClass: { type: Function, required: true },
  orderHeadline: { type: Function, required: true },
  chipClass: { type: Function, required: true },
  elapsedBadgeClass: { type: Function, required: true },
  elapsedMinutes: { type: Function, required: true },
  elapsedLabel: { type: Function, required: true },
  timeAgo: { type: Function, required: true },
  formatScheduledFor: { type: Function, required: true },
  kitchenDueSoon: { type: Function, required: true },
  djChipClass: { type: Function, required: true },
  djChipLabel: { type: Function, required: true },
  orderReadyCount: { type: Function, required: true },
  isItemHeld: { type: Function, required: true },
  lowestHeldCourse: { type: Function, required: true },
  hasUnreadyItems: { type: Function, required: true },
  allItemsReady: { type: Function, required: true },
  actionBtnClass: { type: Function, required: true },
  actionLabel: { type: Function, required: true },
});

const emit = defineEmits(['toggleItem', 'fireCourse', 'markAllReady', 'advance', 'printTicket']);
</script>
