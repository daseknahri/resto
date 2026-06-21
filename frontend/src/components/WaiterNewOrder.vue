<template>
  <!-- Full-screen modal overlay -->
  <Teleport to="body">
    <div
      ref="dialogRef"
      class="fixed inset-0 z-[3000] flex flex-col bg-slate-950/98 backdrop-blur"
      role="dialog"
      aria-modal="true"
      aria-labelledby="waiter-new-order-title"
      @keydown.esc="$emit('close')"
    >
      <!-- Header bar -->
      <div class="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
        <div class="min-w-0">
          <p class="ui-kicker">{{ t('waiterPage.newOrderKicker') }}</p>
          <h2 id="waiter-new-order-title" class="text-base font-bold text-white leading-tight">
            {{ props.appendToOrderId ? t('waiterPage.addItemsTitle', { n: props.appendOrderNumber }) : t('waiterPage.newOrderTitle') }}
          </h2>
        </div>
        <button
          class="ui-press ui-touch-target flex items-center justify-center rounded-full p-1.5 text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
          :aria-label="t('common.close')"
          @click="$emit('close')"
        >
          <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <div class="flex flex-1 overflow-hidden flex-col md:flex-row" :inert="customizingDish != null">
        <!-- ── Left panel: dish search ───────────────────────────────── -->
        <div class="flex flex-1 min-w-0 flex-col overflow-hidden border-b border-slate-800 md:border-b-0 md:border-r">
          <!-- Table input + customer name + search -->
          <div class="space-y-2 p-3 border-b border-slate-800/60">
            <!-- Fulfillment type toggle — hidden in append mode (order type already fixed) -->
            <template v-if="!props.appendToOrderId">
              <div class="ui-segmented" role="radiogroup" :aria-label="t('waiterPage.newOrderFulfillmentLabel')">
                <button
                  class="ui-segmented-button flex-1"
                  :data-active="fulfillmentType === 'table'"
                  role="radio"
                  :aria-checked="String(fulfillmentType === 'table')"
                  @click="fulfillmentType = 'table'"
                >{{ t('waiterPage.newOrderFulfillmentTable') }}</button>
                <button
                  class="ui-segmented-button flex-1"
                  :data-active="fulfillmentType === 'pickup'"
                  role="radio"
                  :aria-checked="String(fulfillmentType === 'pickup')"
                  @click="fulfillmentType = 'pickup'"
                >{{ t('waiterPage.newOrderFulfillmentPickup') }}</button>
              </div>
              <div v-if="fulfillmentType === 'table'" class="flex flex-col gap-1.5">
                <!-- Table dropdown -->
                <div class="flex items-center gap-2">
                  <AppIcon name="table" class="h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden="true" />
                  <select
                    v-model="tableSlug"
                    class="ui-input flex-1 text-sm"
                    :aria-label="t('waiterPage.newOrderTableSelect')"
                    @change="onTableSelect"
                  >
                    <option value="">{{ t('waiterPage.newOrderTableSelect') }}</option>
                    <option
                      v-for="tbl in availableTables"
                      :key="tbl.slug"
                      :value="tbl.slug"
                    >{{ tbl.section ? `${tbl.label} — ${tbl.section}` : tbl.label }}</option>
                    <option value="__custom__">{{ t('waiterPage.newOrderTableCustom') }}</option>
                  </select>
                </div>
                <!-- Custom label escape-hatch: revealed when "__custom__" is selected -->
                <div v-if="tableSlug === '__custom__'" class="flex items-center gap-2 ps-5">
                  <input
                    v-model.trim="tableLabel"
                    type="text"
                    maxlength="40"
                    class="ui-input flex-1 text-sm"
                    :aria-label="t('waiterPage.newOrderTableCustomLabel')"
                    :placeholder="t('waiterPage.newOrderTablePlaceholder')"
                    autofocus
                  />
                </div>
                <!-- Load error notice -->
                <p v-if="tablesLoadError" class="ps-5 text-[11px] text-amber-400">{{ t('waiterPage.newOrderTableLoadError') }}</p>
              </div>
              <div class="flex items-center gap-2">
                <AppIcon name="user" class="h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden="true" />
                <input
                  v-model.trim="customerName"
                  type="text"
                  maxlength="80"
                  autocomplete="name"
                  :aria-label="t('waiterPage.newOrderCustomerNamePlaceholder')"
                  class="ui-input flex-1 text-sm"
                  :placeholder="t('waiterPage.newOrderCustomerNamePlaceholder')"
                />
              </div>
            </template>
            <div class="relative">
              <AppIcon name="search" class="pointer-events-none absolute start-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" aria-hidden="true" />
              <input
                v-model="search"
                type="search"
                enterkeyhint="search"
                :aria-label="t('waiterPage.newOrderSearch')"
                class="ui-input w-full ps-8 text-sm"
                :placeholder="t('waiterPage.newOrderSearch')"
                @input="onSearch"
              />
            </div>
          </div>

          <!-- Category pills (only when not searching) -->
          <div
            v-if="!isSearching && categories.length > 1"
            class="ui-scroll-row border-b border-slate-800/40 px-3 py-2"
            role="group"
            :aria-label="t('waiterPage.newOrderCategoryLabel')"
          >
            <button
              v-for="cat in categories"
              :key="cat.slug"
              class="ui-chip shrink-0"
              :data-active="activeCat === cat.slug"
              :aria-pressed="activeCat === cat.slug"
              @click="selectCat(cat.slug)"
            >{{ cat.name }}</button>
          </div>

          <!-- Dish list -->
          <div class="flex-1 overflow-y-auto px-3 py-2 space-y-1">
            <div v-if="loadingDishes" class="space-y-1.5 pt-1" aria-busy="true" :aria-label="t('waiterPage.loadingDishes')">
              <div v-for="i in 5" :key="i" class="ui-skeleton h-11" />
            </div>

            <div v-else-if="isSearching && !searchResults.length" class="ui-empty-state text-center p-5 space-y-1">
              <p class="text-sm font-semibold text-slate-100">{{ t('waiterPage.noResults') }}</p>
            </div>

            <button
              v-for="(dish, index) in displayedDishes"
              :key="dish.slug"
              class="ui-surface-lift ui-reveal flex w-full items-center justify-between gap-2 rounded-xl border border-slate-700/40 bg-slate-800/30 px-3 py-2.5 text-left transition-colors hover:border-[var(--color-secondary)]/30 hover:bg-[var(--color-secondary)]/5"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
              :disabled="!dish.is_available"
              :class="!dish.is_available ? 'cursor-not-allowed opacity-40' : ''"
              @click="addDish(dish)"
            >
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-slate-100">{{ dish.name }}</p>
                <p v-if="dishHasOptions(dish)" class="truncate text-[10px] font-medium text-[var(--color-secondary)]">{{ t('waiterPage.newOrderHasOptions') }}</p>
                <p v-else-if="dish.description" class="truncate text-[10px] text-slate-500">{{ dish.description }}</p>
              </div>
              <div class="flex shrink-0 items-center gap-2 text-end">
                <div>
                  <p class="tabular-nums text-xs font-semibold text-[var(--color-secondary)]">{{ fmtPrice(dish.price) }}</p>
                  <span v-if="cartQty(dish.slug)" class="tabular-nums rounded-full bg-[var(--color-secondary)]/15 px-1.5 py-0.5 text-[9px] font-bold text-[var(--color-secondary)]">
                    ×{{ cartQty(dish.slug) }}
                  </span>
                </div>
                <AppIcon :name="dishHasOptions(dish) ? 'chevronRight' : 'plus'" class="h-4 w-4 text-slate-500 rtl:scale-x-[-1]" aria-hidden="true" />
              </div>
            </button>
          </div>
        </div>

        <!-- ── Right panel: cart + submit ────────────────────────────── -->
        <div class="flex w-full flex-col md:w-72 shrink-0">
          <p class="border-b border-slate-800 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
            {{ t('waiterPage.newOrderCart') }}
            <span v-if="cartItems.length" class="ms-1 tabular-nums font-bold text-slate-200">({{ cartItems.length }})</span>
          </p>

          <!-- Cart items -->
          <div class="flex-1 overflow-y-auto px-3 py-2 space-y-1.5">
            <div v-if="!cartItems.length" class="ui-empty-state text-center p-5 space-y-1">
              <p class="text-sm font-semibold text-slate-100">{{ t('waiterPage.newOrderEmpty') }}</p>
            </div>

            <div
              v-for="(item, index) in cartItems"
              :key="item.line_key"
              class="ui-reveal rounded-xl border border-slate-700/40 bg-slate-800/30 px-2.5 py-2 space-y-1.5"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
            >
              <div class="flex items-center gap-2">
                <div class="min-w-0 flex-1">
                  <p class="truncate text-xs font-medium text-slate-100">{{ item.dish_name }}</p>
                  <p v-if="item.options_label" class="truncate text-[10px] text-[var(--color-secondary)]/80">{{ item.options_label }}</p>
                  <p class="tabular-nums text-[10px] text-slate-500">{{ fmtPrice(item.unit_price) }} {{ t('waiterPage.newOrderPriceEach') }}</p>
                </div>
                <!-- Qty controls -->
                <div class="flex items-center gap-1 shrink-0" role="group" :aria-label="`${item.dish_name} ${t('waiterPage.newOrderQtyLabel')}`">
                  <button
                    class="ui-press flex h-6 w-6 items-center justify-center rounded-md border border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
                    :aria-label="t('dishPage.decreaseQuantity')"
                    @click="decrement(item.line_key)"
                  >−</button>
                  <span class="w-5 tabular-nums text-center text-xs font-semibold text-slate-100" aria-live="polite" :aria-label="`${item.dish_name} — ${t('waiterPage.newOrderQtyLabel')}: ${item.qty}`">{{ item.qty }}</span>
                  <button
                    class="ui-press flex h-6 w-6 items-center justify-center rounded-md border border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
                    :aria-label="t('dishPage.increaseQuantity')"
                    @click="increment(item.line_key)"
                  >+</button>
                </div>
                <button
                  class="ui-press ui-touch-target shrink-0 rounded p-2 text-slate-600 transition-colors hover:text-red-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500/60"
                  :aria-label="t('common.remove')"
                  @click="removeItem(item.line_key)"
                >
                  <AppIcon name="close" class="h-3 w-3" aria-hidden="true" />
                </button>
              </div>
              <!-- Per-item note -->
              <input
                v-model="item.note"
                type="text"
                maxlength="120"
                class="ui-input w-full text-[11px]"
                :aria-label="`${item.dish_name} — ${t('waiterPage.newOrderItemNotePlaceholder')}`"
                :placeholder="t('waiterPage.newOrderItemNotePlaceholder')"
              />
              <!-- Per-line course picker (coursing at entry). Opt-in: shown only
                   when the owner enabled coursing (any category carries a course). -->
              <div
                v-if="coursingEnabled"
                class="ui-segmented w-full text-[10px]"
                role="radiogroup"
                :aria-label="`${item.dish_name} — ${t('waiterPage.courseLineLabel')}`"
              >
                <button
                  class="ui-segmented-button flex-1 px-1 py-0.5"
                  :data-active="(item.course || 0) === 0"
                  role="radio"
                  :aria-checked="String((item.course || 0) === 0)"
                  @click="item.course = 0"
                >{{ t('waiterPage.courseNone') }}</button>
                <button
                  v-for="n in 4"
                  :key="n"
                  class="ui-segmented-button flex-1 px-1 py-0.5"
                  :data-active="(item.course || 0) === n"
                  role="radio"
                  :aria-checked="String((item.course || 0) === n)"
                  :aria-label="t('waiterPage.courseN', { n })"
                  @click="item.course = n"
                >{{ t('waiterPage.courseChip', { n }) }}</button>
              </div>
            </div>
          </div>

          <!-- Total + submit -->
          <div class="border-t border-slate-800 p-3 space-y-2">
            <!-- Coursing: Send now / Hold for course (opt-in, shown only when the
                 cart actually has a held course so today's flow is untouched). -->
            <div v-if="coursingEnabled && hasHeldCourse" class="space-y-1">
              <div class="ui-segmented w-full text-xs" role="radiogroup" :aria-label="t('waiterPage.coursingTitle')">
                <button
                  class="ui-segmented-button flex-1"
                  :data-active="sendMode === 'send'"
                  role="radio"
                  :aria-checked="String(sendMode === 'send')"
                  @click="sendMode = 'send'"
                >{{ t('waiterPage.sendNow') }}</button>
                <button
                  class="ui-segmented-button flex-1"
                  :data-active="sendMode === 'hold'"
                  role="radio"
                  :aria-checked="String(sendMode === 'hold')"
                  @click="sendMode = 'hold'"
                >{{ t('waiterPage.holdForCourse') }}</button>
              </div>
              <p v-if="sendMode === 'hold'" class="text-[10px] text-slate-500">{{ t('waiterPage.coursingHint') }}</p>
            </div>
            <div v-if="cartItems.length" class="flex items-center justify-between text-sm font-semibold">
              <span class="text-slate-400">{{ t('waiterPage.newOrderTotal') }}</span>
              <span class="tabular-nums text-[var(--color-secondary)]">{{ fmtPrice(cartTotal) }}</span>
            </div>
            <div v-if="submitError" role="alert" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
              <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
              <p class="flex-1 text-sm text-red-300">{{ submitError }}</p>
            </div>
            <button
              class="ui-btn-primary w-full rounded-xl py-2.5 text-sm disabled:pointer-events-none disabled:opacity-50"
              :disabled="submitting || !cartItems.length"
              @click="submit"
            >
              {{ submitting ? t('waiterPage.newOrderSubmitting') : (props.appendToOrderId ? t('waiterPage.addItems') : t('waiterPage.newOrderSubmit')) }}
            </button>
          </div>
        </div>
      </div>

      <!-- ── Dish customization sheet (variants + add-ons) ──────────────────── -->
      <div
        v-if="customizingDish"
        class="absolute inset-0 z-[3100] flex flex-col justify-end bg-slate-950/70 sm:items-center sm:justify-center"
        @click.self="closeCustomize"
      >
        <div
          class="flex max-h-[90%] w-full flex-col overflow-hidden rounded-t-2xl border border-slate-700 bg-slate-950 sm:max-h-[85%] sm:w-[26rem] sm:rounded-2xl"
          role="dialog"
          aria-modal="true"
          aria-labelledby="customize-dialog-title"
          @keydown.esc.stop="closeCustomize"
        >
          <!-- Header -->
          <div class="flex items-start justify-between gap-3 border-b border-slate-800 px-4 py-3">
            <div class="min-w-0">
              <h3 id="customize-dialog-title" class="truncate text-base font-bold text-white">{{ customizingDish.name }}</h3>
              <p class="tabular-nums text-xs text-slate-500">{{ fmtPrice(customizingDish.price) }}</p>
            </div>
            <button
              class="ui-press ui-touch-target flex items-center justify-center rounded-full p-1.5 text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
              :aria-label="t('common.close')"
              @click="closeCustomize"
            >
              <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
            </button>
          </div>

          <!-- Options -->
          <div class="flex-1 space-y-4 overflow-y-auto px-4 py-3">
            <!-- Variant groups -->
            <fieldset v-for="group in customizingDish.option_groups || []" :key="group.id" class="space-y-2 border-0 p-0 m-0 min-w-0">
              <legend class="float-none w-full p-0 mb-2">
                <div class="flex items-center justify-between gap-2">
                  <p class="text-sm font-semibold text-slate-200">
                    {{ group.name }}
                    <span v-if="group.min_select > 0" class="ms-1 rounded-full bg-amber-400/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300">{{ t('dishPage.required') }}</span>
                  </p>
                  <span class="text-[11px] text-slate-500">{{ group.max_select > 1 ? t('dishPage.pickUpTo', { n: group.max_select }) : t('dishPage.pickOne') }}</span>
                </div>
              </legend>
              <label
                v-for="opt in group.options || []"
                :key="opt.id"
                class="flex cursor-pointer items-center justify-between gap-2 rounded-xl border px-3 py-2.5 transition-colors"
                :class="isGroupOptSelected(group.id, opt.id) ? 'border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/8' : 'border-slate-700/50 bg-slate-800/30 hover:border-slate-600'"
              >
                <span class="flex items-center gap-2.5 text-sm text-slate-200">
                  <input
                    :type="group.max_select === 1 ? 'radio' : 'checkbox'"
                    :name="`wg-${group.id}`"
                    class="h-4 w-4 accent-[var(--color-secondary)]"
                    :checked="isGroupOptSelected(group.id, opt.id)"
                    @change="toggleGroupOpt(group, opt.id)"
                  />
                  {{ opt.name }}
                </span>
                <span v-if="Number(opt.price_delta) > 0" class="tabular-nums shrink-0 text-xs font-semibold text-[var(--color-secondary)]">+{{ fmtPrice(opt.price_delta) }}</span>
              </label>
            </fieldset>

            <!-- Add-ons -->
            <fieldset v-if="customizingDish.options?.length" class="space-y-2 border-0 p-0 m-0 min-w-0">
              <legend class="float-none w-full p-0 mb-2 text-sm font-semibold text-slate-200">{{ t('dishPage.options') }}</legend>
              <label
                v-for="opt in customizingDish.options"
                :key="opt.id"
                class="flex cursor-pointer items-center justify-between gap-2 rounded-xl border px-3 py-2.5 transition-colors"
                :class="isAddonSelected(opt.id) ? 'border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/8' : 'border-slate-700/50 bg-slate-800/30 hover:border-slate-600'"
              >
                <span class="flex items-center gap-2.5 text-sm text-slate-200">
                  <input type="checkbox" class="h-4 w-4 accent-[var(--color-secondary)]" :checked="isAddonSelected(opt.id)" @change="toggleAddon(opt.id)" />
                  {{ opt.name }}
                  <span v-if="opt.is_required" class="rounded-full bg-amber-400/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300">{{ t('dishPage.required') }}</span>
                </span>
                <span v-if="Number(opt.price_delta) > 0" class="tabular-nums shrink-0 text-xs font-semibold text-[var(--color-secondary)]">+{{ fmtPrice(opt.price_delta) }}</span>
              </label>
            </fieldset>

            <!-- Note -->
            <input
              v-model="custNote"
              type="text"
              maxlength="120"
              class="ui-input w-full text-sm"
              :aria-label="t('waiterPage.newOrderItemNotePlaceholder')"
              :placeholder="t('waiterPage.newOrderItemNotePlaceholder')"
            />
          </div>

          <!-- Footer: qty + add -->
          <div class="flex items-center gap-3 border-t border-slate-800 p-3">
            <div class="flex items-center gap-1 shrink-0" role="group" :aria-label="t('waiterPage.newOrderQtyLabel')">
              <button
                class="ui-press flex h-9 w-9 items-center justify-center rounded-lg border border-slate-700 text-lg text-slate-300 hover:border-slate-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
                :aria-label="t('dishPage.decreaseQuantity')"
                @click="custQty = Math.max(1, custQty - 1)"
              >−</button>
              <span class="w-7 tabular-nums text-center text-sm font-semibold text-slate-100" aria-live="polite">{{ custQty }}</span>
              <button
                class="ui-press flex h-9 w-9 items-center justify-center rounded-lg border border-slate-700 text-lg text-slate-300 hover:border-slate-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
                :aria-label="t('dishPage.increaseQuantity')"
                @click="custQty = Math.min(99, custQty + 1)"
              >+</button>
            </div>
            <button
              class="ui-btn-primary flex-1 rounded-xl py-2.5 text-sm disabled:pointer-events-none disabled:opacity-50"
              :disabled="custRequiredUnmet"
              @click="confirmCustomize"
            >
              {{ custRequiredUnmet ? t('waiterPage.newOrderSelectRequired') : t('waiterPage.newOrderAddToOrder', { price: fmtPrice(custUnitPrice * custQty) }) }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { useMenuStore } from '../stores/menu';
import { useTenantStore } from '../stores/tenant';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';
import { newIdempotencyKey } from '../lib/idempotency';

const props = defineProps({
  // When set, the component operates in "append" mode: posts items to the
  // append endpoint instead of place-order, hides table/fulfillment inputs,
  // and emits 'appended' instead of 'placed'.
  appendToOrderId: { type: Number, default: null },
  appendOrderNumber: { type: [Number, String], default: null },
});

const emit = defineEmits(['close', 'placed', 'appended']);
const { t, currentLocale } = useI18n();
const menu = useMenuStore();
const tenant = useTenantStore();
const toast = useToastStore();

// ── State ─────────────────────────────────────────────────────────────────────
const fulfillmentType = ref('table');
// tableSlug: the selected table slug, or '' (none), or '__custom__' for free-text
const tableSlug = ref('');
// tableLabel: the display label — set automatically from dropdown, or typed manually
const tableLabel = ref('');
const customerName = ref('');

// Idempotency key minted when this modal opens; cleared on confirmed success so
// a genuine second order does not deduplicate against the first.
// A tab-crash / slow-network retry within the same modal lifecycle reuses the key,
// so the backend deduplicates instead of creating a second kitchen ticket.
const orderPlacementKey = ref(newIdempotencyKey());

// ── Table list (sourced from GET /api/staff/tables/) ─────────────────────────
const availableTables = ref([]);
const tablesLoadError = ref(false);

const loadTables = async () => {
  tablesLoadError.value = false;
  try {
    const { data } = await api.get('/staff/tables/');
    availableTables.value = Array.isArray(data) ? data : [];
  } catch {
    tablesLoadError.value = true;
  }
};

// When a real table is selected from the dropdown, sync tableLabel with its label
const onTableSelect = () => {
  if (tableSlug.value === '' || tableSlug.value === '__custom__') {
    if (tableSlug.value === '') tableLabel.value = '';
    return;
  }
  const found = availableTables.value.find((t) => t.slug === tableSlug.value);
  if (found) tableLabel.value = found.label;
};
const search = ref('');
const activeCat = ref('');
const cartItems = ref([]);   // [{line_key, dish_slug, dish_name, unit_price, qty, note, option_ids, options_label}]
const loadingDishes = ref(false);
const submitting = ref(false);
const submitError = ref('');

// ── Dish customization (variants + add-ons) ──────────────────────────────────
const customizingDish = ref(null);   // dish being customized, or null
const groupSel = ref({});            // { [groupId]: optionId | optionId[] }
const addonSel = ref([]);            // standalone dish.options ids
const custQty = ref(1);
const custNote = ref('');

let searchTimer = null;

// ── Derived ───────────────────────────────────────────────────────────────────
const categories = computed(() => menu.categories || []);
const currency = computed(() =>
  (menu.categories || []).length
    ? (tenant.resolvedMeta?.plan?.currency || 'MAD')
    : 'MAD'
);

const isSearching = computed(() => search.value.trim().length > 0);

const allDishes = computed(() => Object.values(menu.dishes || {}).flat());

// ── Coursing at entry (WAITER-COURSING) ──────────────────────────────────────
// sendMode 'send' (default) = fire everything immediately (today's behavior);
// 'hold' = keep held courses (course > 1) paced for later firing from the card.
const sendMode = ref('send');

// Map category slug → its course snapshot (0 = no course). Empty/absent course
// keeps coursing off, so restaurants that never set a course see zero change.
const categoryCourseBySlug = computed(() => {
  const map = {};
  for (const cat of (menu.categories || [])) {
    map[cat.slug] = Number(cat.course || 0) || 0;
  }
  return map;
});

// Coursing UI is opt-in: only surfaces once the owner has assigned a course to at
// least one category. Until then the per-line picker + Send/Hold toggle stay hidden
// and payloads carry no course override — byte-for-byte today's flow.
const coursingEnabled = computed(() =>
  Object.values(categoryCourseBySlug.value).some((c) => c > 0)
);

// Resolve a dish's default course from whichever category list it lives in.
const dishCourse = (slug) => {
  for (const [catSlug, list] of Object.entries(menu.dishes || {})) {
    if ((list || []).some((d) => d.slug === slug)) {
      return categoryCourseBySlug.value[catSlug] || 0;
    }
  }
  return 0;
};

// True when at least one cart line carries a course > 0 — only then is the
// Send-now / Hold toggle meaningful (otherwise everything fires regardless).
const hasHeldCourse = computed(() =>
  cartItems.value.some((i) => (i.course || 0) > 0)
);

const searchResults = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return [];
  return allDishes.value.filter((d) =>
    d.name?.toLowerCase().includes(q) ||
    d.description?.toLowerCase().includes(q)
  );
});

const catDishes = computed(() => {
  if (!activeCat.value) return [];
  return menu.dishes[activeCat.value] || [];
});

const displayedDishes = computed(() =>
  isSearching.value ? searchResults.value : catDishes.value
);

const cartTotal = computed(() =>
  cartItems.value.reduce((s, i) => s + i.unit_price * i.qty, 0)
);

// ── Helpers ───────────────────────────────────────────────────────────────────
const fmtPrice = (amount) => {
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency: currency.value,
      maximumFractionDigits: 2,
    }).format(amount || 0);
  } catch {
    return `${Number(amount || 0).toFixed(2)}`;
  }
};

// Total qty of a dish across all its cart lines (a dish can appear with
// different option combinations).
const cartQty = (slug) =>
  cartItems.value.filter((i) => i.dish_slug === slug).reduce((s, i) => s + i.qty, 0);

const dishHasOptions = (dish) =>
  Boolean(dish?.option_groups?.length || dish?.options?.length);

const lineKey = (slug, optionIds) =>
  optionIds.length ? `${slug}::${[...optionIds].sort((a, b) => a - b).join('-')}` : slug;

// ── Customization derived state ──────────────────────────────────────────────
const groupCount = (groupId) => {
  const sel = groupSel.value[groupId];
  return Array.isArray(sel) ? sel.length : sel != null ? 1 : 0;
};
const isGroupOptSelected = (groupId, optId) => {
  const sel = groupSel.value[groupId];
  return Array.isArray(sel) ? sel.includes(optId) : sel === optId;
};
const isAddonSelected = (optId) => addonSel.value.includes(optId);

const custSelectedOptions = computed(() => {
  const d = customizingDish.value;
  if (!d) return [];
  const out = [];
  (d.option_groups || []).forEach((g) => {
    const sel = groupSel.value[g.id];
    const ids = Array.isArray(sel) ? sel : sel != null ? [sel] : [];
    ids.forEach((id) => {
      const opt = (g.options || []).find((o) => o.id === id);
      if (opt) out.push(opt);
    });
  });
  (d.options || []).forEach((o) => { if (addonSel.value.includes(o.id)) out.push(o); });
  return out;
});
const custOptionIds = computed(() => custSelectedOptions.value.map((o) => o.id));
const custUnitPrice = computed(() => {
  const base = Number(customizingDish.value?.price || 0);
  return base + custSelectedOptions.value.reduce((s, o) => s + Number(o.price_delta || 0), 0);
});
const custOptionsLabel = computed(() => custSelectedOptions.value.map((o) => o.name).join(', '));
const custRequiredUnmet = computed(() => {
  const d = customizingDish.value;
  if (!d) return false;
  const groupUnmet = (d.option_groups || []).some((g) => g.min_select > 0 && groupCount(g.id) < g.min_select);
  const addonUnmet = (d.options || []).some((o) => o.is_required && !addonSel.value.includes(o.id));
  return groupUnmet || addonUnmet;
});

// ── Actions ───────────────────────────────────────────────────────────────────
const selectCat = (slug) => {
  activeCat.value = slug;
  // Lazy-load if needed
  if (!menu.dishes[slug]?.length) {
    loadingDishes.value = true;
    menu.fetchDishesByCategory(slug).finally(() => {
      loadingDishes.value = false;
    });
  }
};

// Add a fully-specified line to the cart (merging same dish + same options).
const addLine = ({ dish_slug, dish_name, unit_price, option_ids, options_label, qty, note }) => {
  const key = lineKey(dish_slug, option_ids);
  const existing = cartItems.value.find((i) => i.line_key === key);
  if (existing) {
    existing.qty = Math.min(99, existing.qty + qty);
  } else {
    cartItems.value.push({
      line_key: key,
      dish_slug,
      dish_name,
      unit_price,
      option_ids: [...option_ids],
      options_label: options_label || '',
      qty: Math.min(99, qty),
      note: note || '',
      // Default course = the dish's category snapshot (0 = no course). The waiter
      // can override per line via the picker. Stays 0 for non-coursing menus.
      course: dishCourse(dish_slug),
    });
  }
};

const addDish = (dish) => {
  if (dishHasOptions(dish)) {
    openCustomize(dish);
    return;
  }
  addLine({ dish_slug: dish.slug, dish_name: dish.name, unit_price: dish.price || 0, option_ids: [], qty: 1 });
};

// ── Customization actions ────────────────────────────────────────────────────
const openCustomize = (dish) => {
  customizingDish.value = dish;
  groupSel.value = {};
  addonSel.value = [];
  custQty.value = 1;
  custNote.value = '';
  // Pre-select the first option of required single-choice groups (sensible default).
  (dish.option_groups || []).forEach((g) => {
    if (g.min_select > 0 && g.max_select === 1 && g.options?.length) {
      groupSel.value[g.id] = g.options[0].id;
    }
  });
};
const closeCustomize = () => { customizingDish.value = null; };

const toggleGroupOpt = (group, optId) => {
  if (group.max_select === 1) {
    groupSel.value = { ...groupSel.value, [group.id]: optId };
    return;
  }
  const cur = Array.isArray(groupSel.value[group.id]) ? [...groupSel.value[group.id]] : [];
  const idx = cur.indexOf(optId);
  if (idx >= 0) cur.splice(idx, 1);
  else if (cur.length < group.max_select) cur.push(optId);
  groupSel.value = { ...groupSel.value, [group.id]: cur };
};
const toggleAddon = (optId) => {
  const idx = addonSel.value.indexOf(optId);
  if (idx >= 0) addonSel.value.splice(idx, 1);
  else addonSel.value.push(optId);
};

const confirmCustomize = () => {
  const d = customizingDish.value;
  if (!d || custRequiredUnmet.value) return;
  addLine({
    dish_slug: d.slug,
    dish_name: d.name,
    unit_price: custUnitPrice.value,
    option_ids: custOptionIds.value,
    options_label: custOptionsLabel.value,
    qty: custQty.value,
    note: custNote.value.trim(),
  });
  closeCustomize();
};

const increment = (key) => {
  const item = cartItems.value.find((i) => i.line_key === key);
  if (item) item.qty = Math.min(99, item.qty + 1);
};

const decrement = (key) => {
  const item = cartItems.value.find((i) => i.line_key === key);
  if (!item) return;
  if (item.qty <= 1) removeItem(key);
  else item.qty--;
};

const removeItem = (key) => {
  cartItems.value = cartItems.value.filter((i) => i.line_key !== key);
};

const onSearch = () => {
  clearTimeout(searchTimer);
  if (search.value.trim()) {
    // Pre-load all dishes for search (fire and forget)
    searchTimer = setTimeout(() => {
      categories.value.forEach((cat) => {
        if (!menu.dishes[cat.slug]?.length) {
          menu.fetchDishesByCategory(cat.slug);
        }
      });
    }, 200);
  }
};

// Map backend 409 error codes to user-facing messages for the append endpoint.
const _appendErrorMsg = (err) => {
  const data = err?.response?.data || {};
  const code = data.code || '';
  const detail = data.detail || data.error || '';
  if (code === 'out_of_stock') return detail || t('waiterPage.addFailed');
  if (code === 'not_table')    return t('waiterPage.addFailed');
  if (code === 'bad_status')   return t('waiterPage.addFailed');
  if (code === 'already_paid') return t('waiterPage.addFailed');
  return detail || t('waiterPage.addFailed');
};

const submit = async () => {
  submitError.value = '';
  if (!cartItems.value.length) {
    submitError.value = t('waiterPage.newOrderNoItems');
    return;
  }

  // Append mode — POST to the append endpoint.
  if (props.appendToOrderId) {
    submitting.value = true;
    try {
      const payload = {
        items: cartItems.value.map((i) => ({
          dish_slug: i.dish_slug,
          qty: i.qty,
          note: i.note?.trim() || '',
          option_ids: i.option_ids || [],
          // Only send a course override when coursing is enabled, so existing
          // (non-coursing) tenants post an identical body to before.
          ...(coursingEnabled.value ? { course: i.course || 0 } : {}),
        })),
        // 'Send now' fires the appended items immediately; 'Hold' keeps held
        // courses paced. Omitted entirely for non-coursing menus.
        ...(coursingEnabled.value && hasHeldCourse.value
          ? { send_now: sendMode.value === 'send' }
          : {}),
      };
      await api.post(`/staff/orders/${props.appendToOrderId}/items/`, payload);
      toast.show(t('waiterPage.itemsAdded'), 'success');
      emit('appended');
      emit('close');
    } catch (err) {
      submitError.value = _appendErrorMsg(err);
    } finally {
      submitting.value = false;
    }
    return;
  }

  // Normal new-order mode.
  if (fulfillmentType.value === 'table') {
    // Must have a real table selected or a custom label typed
    const hasTable = (tableSlug.value && tableSlug.value !== '__custom__') ||
                     (tableSlug.value === '__custom__' && tableLabel.value.trim());
    if (!hasTable) {
      submitError.value = t('waiterPage.newOrderNoTable');
      return;
    }
  }

  submitting.value = true;
  try {
    // Resolve the final slug and label to submit
    const resolvedSlug = (fulfillmentType.value === 'table' && tableSlug.value !== '__custom__')
      ? tableSlug.value
      : '';
    const resolvedLabel = fulfillmentType.value === 'table' ? tableLabel.value.trim() : '';

    const payload = {
      items: cartItems.value.map((i) => ({
        slug: i.dish_slug,
        qty: i.qty,
        note: i.note?.trim() || '',
        option_ids: i.option_ids || [],
        // Per-line course override only when coursing is enabled — otherwise the
        // body is identical to before and the backend uses the category snapshot.
        ...(coursingEnabled.value ? { course: i.course || 0 } : {}),
      })),
      fulfillment_type: fulfillmentType.value,
      table_slug: resolvedSlug || undefined,
      table_label: resolvedLabel,
      customer_name: customerName.value.trim(),
      customer_note: '',
      idempotency_key: orderPlacementKey.value,
      // 'Send now' fires every course at once (fired_course=4); 'Hold' leaves the
      // backend default (1) so courses 2..4 wait for an explicit fire. Sent only
      // when a held course actually exists in the cart.
      ...(coursingEnabled.value && hasHeldCourse.value && sendMode.value === 'send'
        ? { fired_course: 4 }
        : {}),
    };
    await api.post('/place-order/', payload);
    // Clear the key on confirmed success — the next order opened by this waiter
    // must get a fresh key so it is not deduplicated against this one.
    orderPlacementKey.value = null;
    toast.show(t('waiterPage.newOrderSuccess'), 'success');
    emit('placed');
    emit('close');
  } catch (err) {
    const detail = err?.response?.data?.detail || err?.response?.data?.error || '';
    submitError.value = detail || t('waiterPage.newOrderError');
  } finally {
    submitting.value = false;
  }
};

// ── Focus trap ────────────────────────────────────────────────────────────────
const dialogRef = ref(null);
const FOCUSABLE_SEL = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapFocus = (e) => {
  if (!dialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(dialogRef.value.querySelectorAll(FOCUSABLE_SEL));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

onUnmounted(() => document.removeEventListener('keydown', trapFocus));

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  document.addEventListener('keydown', trapFocus);
  dialogRef.value?.querySelector(FOCUSABLE_SEL)?.focus();
  // Load tables for the dropdown (parallel with categories fetch)
  loadTables();
  if (!categories.value.length) {
    loadingDishes.value = true;
    await menu.fetchCategories();
    loadingDishes.value = false;
  }
  // Auto-select first category
  const first = categories.value[0];
  if (first) {
    activeCat.value = first.slug;
    if (!menu.dishes[first.slug]?.length) {
      loadingDishes.value = true;
      await menu.fetchDishesByCategory(first.slug);
      loadingDishes.value = false;
    }
  }
});

watch(currentLocale, () => menu.fetchCategories(true));
</script>
