<template>
  <!-- Full-screen modal overlay -->
  <Teleport to="body">
    <div
      class="fixed inset-0 z-[3000] flex flex-col bg-slate-950/98 backdrop-blur"
      role="dialog"
      aria-modal="true"
      aria-labelledby="waiter-new-order-title"
      @keydown.esc.window="$emit('close')"
    >
      <!-- Header bar -->
      <div class="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
        <h2 id="waiter-new-order-title" class="text-sm font-semibold text-slate-100">{{ t('waiterPage.newOrderTitle') }}</h2>
        <button
          class="rounded-full p-1.5 text-slate-400 hover:text-slate-200 transition-colors"
          :aria-label="t('common.close')"
          @click="$emit('close')"
        >
          <AppIcon name="close" class="h-4 w-4" />
        </button>
      </div>

      <div class="flex flex-1 overflow-hidden flex-col md:flex-row">
        <!-- ── Left panel: dish search ───────────────────────────────── -->
        <div class="flex flex-1 flex-col overflow-hidden border-b border-slate-800 md:border-b-0 md:border-r">
          <!-- Table input + customer name + search -->
          <div class="space-y-2 p-3 border-b border-slate-800/60">
            <!-- Fulfillment type toggle -->
            <div class="flex rounded-lg border border-slate-700/60 overflow-hidden text-xs font-semibold">
              <button
                class="flex-1 py-1.5 transition-colors"
                :class="fulfillmentType === 'table'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-800/40 text-slate-400 hover:text-slate-200'"
                @click="fulfillmentType = 'table'"
              >{{ t('waiterPage.newOrderFulfillmentTable') }}</button>
              <button
                class="flex-1 py-1.5 transition-colors"
                :class="fulfillmentType === 'pickup'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-800/40 text-slate-400 hover:text-slate-200'"
                @click="fulfillmentType = 'pickup'"
              >{{ t('waiterPage.newOrderFulfillmentPickup') }}</button>
            </div>
            <div v-if="fulfillmentType === 'table'" class="flex items-center gap-2">
              <AppIcon name="table" class="h-3.5 w-3.5 shrink-0 text-slate-500" />
              <input
                v-model.trim="tableLabel"
                type="text"
                maxlength="40"
                class="ui-input flex-1 text-sm"
                :placeholder="t('waiterPage.newOrderTablePlaceholder')"
              />
            </div>
            <div class="flex items-center gap-2">
              <AppIcon name="user" class="h-3.5 w-3.5 shrink-0 text-slate-500" />
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
            <div class="relative">
              <AppIcon name="search" class="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
              <input
                v-model="search"
                type="search"
                enterkeyhint="search"
                :aria-label="t('waiterPage.newOrderSearch')"
                class="ui-input w-full pl-8 text-sm"
                :placeholder="t('waiterPage.newOrderSearch')"
                @input="onSearch"
              />
            </div>
          </div>

          <!-- Category pills (only when not searching) -->
          <div
            v-if="!isSearching && categories.length > 1"
            class="flex gap-1.5 overflow-x-auto px-3 py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden border-b border-slate-800/40"
          >
            <button
              v-for="cat in categories"
              :key="cat.slug"
              class="shrink-0 rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-colors"
              :class="activeCat === cat.slug
                ? 'border-indigo-500/60 bg-indigo-500/15 text-indigo-300'
                : 'border-slate-700/50 bg-slate-800/40 text-slate-400 hover:border-slate-600'"
              @click="selectCat(cat.slug)"
            >{{ cat.name }}</button>
          </div>

          <!-- Dish list -->
          <div class="flex-1 overflow-y-auto px-3 py-2 space-y-1">
            <div v-if="loadingDishes" class="space-y-1.5 pt-1">
              <div v-for="i in 5" :key="i" class="h-11 animate-pulse rounded-xl bg-slate-800/50" />
            </div>

            <p v-else-if="isSearching && !searchResults.length" class="py-6 text-center text-xs text-slate-500">
              {{ t('waiterPage.noResults') }}
            </p>

            <button
              v-for="dish in displayedDishes"
              :key="dish.slug"
              class="flex w-full items-center justify-between gap-2 rounded-xl border border-slate-700/40 bg-slate-800/30 px-3 py-2.5 text-left transition-colors hover:border-indigo-500/40 hover:bg-indigo-500/8"
              :disabled="!dish.is_available"
              :class="!dish.is_available ? 'opacity-40 cursor-not-allowed' : ''"
              @click="addDish(dish)"
            >
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-slate-100">{{ dish.name }}</p>
                <p v-if="dish.description" class="truncate text-[10px] text-slate-500">{{ dish.description }}</p>
              </div>
              <div class="shrink-0 text-right">
                <p class="text-xs font-semibold text-[var(--color-secondary)]">{{ fmtPrice(dish.price) }}</p>
                <span v-if="cartQty(dish.slug)" class="rounded-full bg-indigo-500/20 px-1.5 py-0.5 text-[9px] font-bold text-indigo-300">
                  ×{{ cartQty(dish.slug) }}
                </span>
              </div>
            </button>
          </div>
        </div>

        <!-- ── Right panel: cart + submit ────────────────────────────── -->
        <div class="flex flex-col md:w-72 shrink-0">
          <p class="border-b border-slate-800 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
            {{ t('waiterPage.newOrderCart') }}
            <span v-if="cartItems.length" class="ml-1 font-bold text-slate-200">({{ cartItems.length }})</span>
          </p>

          <!-- Cart items -->
          <div class="flex-1 overflow-y-auto px-3 py-2 space-y-1.5">
            <p v-if="!cartItems.length" class="py-6 text-center text-xs text-slate-500">
              {{ t('waiterPage.newOrderEmpty') }}
            </p>

            <div
              v-for="item in cartItems"
              :key="item.dish_slug"
              class="rounded-xl border border-slate-700/40 bg-slate-800/30 px-2.5 py-2 space-y-1.5"
            >
              <div class="flex items-center gap-2">
                <div class="min-w-0 flex-1">
                  <p class="truncate text-xs font-medium text-slate-100">{{ item.dish_name }}</p>
                  <p class="text-[10px] text-slate-500">{{ fmtPrice(item.unit_price) }} {{ t('waiterPage.newOrderPriceEach') }}</p>
                </div>
                <!-- Qty controls -->
                <div class="flex items-center gap-1 shrink-0">
                  <button
                    class="flex h-5 w-5 items-center justify-center rounded-md border border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200 text-xs"
                    @click="decrement(item.dish_slug)"
                  >−</button>
                  <span class="w-5 text-center text-xs font-semibold text-slate-100">{{ item.qty }}</span>
                  <button
                    class="flex h-5 w-5 items-center justify-center rounded-md border border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200 text-xs"
                    @click="increment(item.dish_slug)"
                  >+</button>
                </div>
                <button
                  class="shrink-0 rounded p-0.5 text-slate-600 hover:text-red-400 transition-colors"
                  :aria-label="t('common.remove')"
                  @click="removeItem(item.dish_slug)"
                >
                  <AppIcon name="close" class="h-3 w-3" />
                </button>
              </div>
              <!-- Per-item note -->
              <input
                v-model="item.note"
                type="text"
                maxlength="120"
                class="w-full rounded-lg border border-slate-700/50 bg-slate-900/60 px-2 py-1 text-[11px] text-slate-300 placeholder-slate-600 focus:border-slate-500 focus:outline-none"
                :placeholder="t('waiterPage.newOrderItemNotePlaceholder')"
              />
            </div>
          </div>

          <!-- Total + submit -->
          <div class="border-t border-slate-800 p-3 space-y-2">
            <div v-if="cartItems.length" class="flex items-center justify-between text-sm font-semibold">
              <span class="text-slate-400">{{ t('waiterPage.newOrderTotal') }}</span>
              <span class="text-[var(--color-secondary)]">{{ fmtPrice(cartTotal) }}</span>
            </div>
            <div v-if="submitError" role="alert" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
              <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
              <p class="flex-1 text-sm text-red-300">{{ submitError }}</p>
            </div>
            <button
              class="w-full rounded-xl bg-indigo-600 py-2.5 text-sm font-semibold text-white transition-opacity hover:bg-indigo-500 disabled:opacity-50"
              :disabled="submitting || !cartItems.length"
              @click="submit"
            >
              {{ submitting ? t('waiterPage.newOrderSubmitting') : t('waiterPage.newOrderSubmit') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { useMenuStore } from '../stores/menu';
import { useTenantStore } from '../stores/tenant';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';

const emit = defineEmits(['close', 'placed']);
const { t, currentLocale } = useI18n();
const menu = useMenuStore();
const tenant = useTenantStore();
const toast = useToastStore();

// ── State ─────────────────────────────────────────────────────────────────────
const fulfillmentType = ref('table');
const tableLabel = ref('');
const customerName = ref('');
const search = ref('');
const activeCat = ref('');
const cartItems = ref([]);   // [{dish_slug, dish_name, unit_price, qty, note}]
const loadingDishes = ref(false);
const submitting = ref(false);
const submitError = ref('');

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

const cartQty = (slug) =>
  cartItems.value.find((i) => i.dish_slug === slug)?.qty ?? 0;

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

const addDish = (dish) => {
  const existing = cartItems.value.find((i) => i.dish_slug === dish.slug);
  if (existing) {
    existing.qty = Math.min(99, existing.qty + 1);
  } else {
    cartItems.value.push({
      dish_slug: dish.slug,
      dish_name: dish.name,
      unit_price: dish.price || 0,
      qty: 1,
      note: '',
    });
  }
};

const increment = (slug) => {
  const item = cartItems.value.find((i) => i.dish_slug === slug);
  if (item) item.qty = Math.min(99, item.qty + 1);
};

const decrement = (slug) => {
  const item = cartItems.value.find((i) => i.dish_slug === slug);
  if (!item) return;
  if (item.qty <= 1) removeItem(slug);
  else item.qty--;
};

const removeItem = (slug) => {
  cartItems.value = cartItems.value.filter((i) => i.dish_slug !== slug);
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

const submit = async () => {
  submitError.value = '';
  if (!cartItems.value.length) {
    submitError.value = t('waiterPage.newOrderNoItems');
    return;
  }
  if (fulfillmentType.value === 'table' && !tableLabel.value.trim()) {
    submitError.value = t('waiterPage.newOrderNoTable');
    return;
  }

  submitting.value = true;
  try {
    const payload = {
      items: cartItems.value.map((i) => ({
        slug: i.dish_slug,
        qty: i.qty,
        note: i.note?.trim() || '',
        option_ids: [],
      })),
      fulfillment_type: fulfillmentType.value,
      table_label: fulfillmentType.value === 'table' ? tableLabel.value.trim() : '',
      customer_name: customerName.value.trim(),
      customer_note: '',
    };
    await api.post('/place-order/', payload);
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

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(async () => {
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
