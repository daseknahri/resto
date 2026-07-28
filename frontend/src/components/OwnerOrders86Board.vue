<template>
  <!-- 86 Board (dish availability) modal — Teleported to body -->
  <Teleport to="body">
    <Transition name="ui-fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[2200] flex items-end justify-center sm:items-center"
        role="dialog"
        aria-modal="true"
        :aria-label="t('kitchen.eightySixTitle')"
        @keydown.esc="emit('close')"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" @click="emit('close')" />
        <!-- Panel -->
        <div class="relative z-10 w-full max-w-md rounded-t-2xl sm:rounded-2xl bg-slate-900 border border-slate-700/60 shadow-2xl flex flex-col max-h-[85dvh]">
          <!-- Header -->
          <div class="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 shrink-0">
            <h2 class="text-base font-bold text-white">
              {{ t('kitchen.eightySixTitle') }}
              <span v-if="soldOutCount > 0" class="ms-2 rounded-full border border-red-500/40 bg-red-500/15 px-2 py-0.5 text-xs font-semibold text-red-300 tabular-nums">{{ soldOutCount }}</span>
            </h2>
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
          <!-- Search -->
          <div class="px-4 pt-3 pb-2 shrink-0">
            <div class="relative">
              <svg class="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9Z" clip-rule="evenodd"/>
              </svg>
              <input
                v-model.trim="search"
                type="search"
                autofocus
                class="w-full rounded-xl border border-slate-700 bg-slate-800/70 py-2.5 ps-9 pe-4 text-sm text-slate-200 placeholder-slate-500 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                :placeholder="t('kitchen.eightySixSearch')"
                :aria-label="t('kitchen.eightySixSearch')"
              />
            </div>
            <!-- Reset all available / Mark all unavailable -->
            <div class="mt-2 flex items-center justify-between gap-2">
              <button
                v-if="hasAvailable"
                class="ui-press rounded-full border border-red-500/40 px-2.5 py-1 text-[10px] font-semibold text-red-300 hover:bg-red-500/10 disabled:opacity-50"
                :disabled="markingUnavailable"
                @click="emit('markAllUnavailable')"
              >{{ markingUnavailable ? t('common.loading') : t('kitchen.markAllUnavailable') }}</button>
              <span v-else />
              <button
                v-if="soldOutCount > 0"
                class="ui-press rounded-full border border-emerald-500/40 px-2.5 py-1 text-[10px] font-semibold text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-50"
                :disabled="resetting"
                @click="emit('resetAll')"
              >{{ resetting ? t('common.loading') : t('ownerHome.resetAllAvailable') }}</button>
            </div>
          </div>
          <!-- List -->
          <div class="overflow-y-auto flex-1 px-4 pb-4">
            <div v-if="fetching" class="space-y-2 pt-1">
              <div v-for="i in 6" :key="i" class="flex animate-pulse items-center justify-between gap-2 rounded-xl px-2 py-3">
                <div class="h-4 w-36 rounded bg-slate-700/60" />
                <div class="h-9 w-24 rounded-xl bg-slate-700/40" />
              </div>
            </div>
            <div v-else-if="!dishes.length" class="py-8 text-center text-sm text-slate-500">{{ t('kitchen.eightySixEmpty') }}</div>
            <ul v-else role="list" class="list-none space-y-1 pt-1">
              <li
                v-for="dish in dishes"
                :key="dish.id"
                class="flex items-center justify-between gap-3 rounded-xl px-2 py-2 transition-colors hover:bg-slate-800/50"
                :class="!dish.is_available ? 'opacity-70' : ''"
              >
                <div class="min-w-0 flex-1">
                  <p class="truncate text-sm font-medium text-slate-100">{{ dish.name }}</p>
                  <p class="truncate text-[11px] text-slate-500">{{ dish.category_name || dish.category_slug }}</p>
                </div>
                <button
                  role="switch"
                  class="ui-press shrink-0 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50 min-w-[5.5rem] text-center"
                  :class="dish.is_available
                    ? 'border-emerald-500/40 text-emerald-300 hover:border-red-400/50 hover:bg-red-500/10 hover:text-red-300'
                    : 'border-red-500/40 bg-red-500/10 text-red-300 hover:border-emerald-400/50 hover:bg-emerald-500/10 hover:text-emerald-300'"
                  :disabled="togglingId === dish.id"
                  :aria-checked="dish.is_available"
                  :aria-busy="togglingId === dish.id"
                  :aria-label="`${dish.name} — ${dish.is_available ? t('kitchen.eightySixAvailable') : t('kitchen.eightySixSoldOut')}`"
                  @click="emit('toggle', dish)"
                >
                  {{ togglingId === dish.id ? '…' : (dish.is_available ? t('kitchen.eightySixAvailable') : t('kitchen.eightySixSoldOut')) }}
                </button>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
// 86-board (dish availability) modal of OwnerOrders.vue, extracted as a standalone
// presentational child (RISK FE-2, entangled tier — a sibling of
// OwnerKitchen86Board with the extra sold-out count + bulk mark/reset actions).
//
// The complexity stays in the parent (OwnerOrders.vue): the dish data
// (`orders86Dishes`), the fetch, the toggle API (`orders86Toggle`, which mutates
// dish.is_available in place on the same refs this list renders), the bulk
// mark-all-unavailable / reset-all actions, the sold-out count, and the snapshotted
// sort-order Map + `orders86Filtered` computed. This component is the presentational
// shell: it takes the filtered dishes + flags as props, round-trips the search via
// `v-model:search` (defineModel) so the parent's filter computed stays reactive, and
// forwards intent via `close` / `toggle(dish)` / `markAllUnavailable` / `resetAll`.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

const search = defineModel('search', { type: String, default: '' });

defineProps({
  /** Whether the board is open (parent-owned orders86BoardOpen). */
  open: { type: Boolean, default: false },
  /** The already filtered + stably-sorted dishes (parent's orders86Filtered). */
  dishes: { type: Array, default: () => [] },
  /** True while the parent is (re)fetching the dish list. */
  fetching: { type: Boolean, default: false },
  /** Id of the dish whose availability toggle is in flight, or null. */
  togglingId: { type: [Number, String], default: null },
  /** Count of currently sold-out (86'd) dishes — drives the header badge + reset button. */
  soldOutCount: { type: Number, default: 0 },
  /** Whether any dish is currently available — gates the mark-all-unavailable button. */
  hasAvailable: { type: Boolean, default: false },
  /** True while the bulk mark-all-unavailable request is in flight. */
  markingUnavailable: { type: Boolean, default: false },
  /** True while the bulk reset-all-available request is in flight. */
  resetting: { type: Boolean, default: false },
});

const emit = defineEmits(['close', 'toggle', 'markAllUnavailable', 'resetAll']);
</script>
