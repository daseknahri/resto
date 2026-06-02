<template>
  <div class="min-h-screen bg-slate-950 pb-32">

    <!-- Back link -->
    <div class="mx-auto max-w-3xl px-4 pt-5">
      <router-link to="/order" class="text-xs text-slate-400 hover:text-slate-200">
        {{ t('mktMenu.backToList') }}
      </router-link>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="mx-auto max-w-3xl px-4 py-5 space-y-5">
      <!-- Restaurant header skeleton -->
      <div class="flex items-start gap-4 animate-pulse">
        <div class="h-16 w-16 shrink-0 rounded-xl bg-slate-800" />
        <div class="flex-1 space-y-2">
          <div class="h-5 w-40 rounded bg-slate-700/60" />
          <div class="h-3 w-56 rounded bg-slate-800/50" />
          <div class="flex gap-2">
            <div class="h-3 w-16 rounded bg-slate-800/40" />
            <div class="h-3 w-12 rounded bg-slate-800/40" />
          </div>
        </div>
      </div>
      <!-- Category + dish skeletons -->
      <div v-for="i in 2" :key="i" class="space-y-3 animate-pulse">
        <div class="h-4 w-28 rounded bg-slate-700/50" />
        <div v-for="j in 3" :key="j" class="flex items-center justify-between gap-3 rounded-xl border border-slate-700/40 bg-slate-900/50 p-4">
          <div class="space-y-1.5">
            <div class="h-3.5 w-36 rounded bg-slate-700/60" />
            <div class="h-2.5 w-52 rounded bg-slate-800/50" />
            <div class="h-4 w-14 rounded bg-slate-700/40" />
          </div>
          <div class="h-14 w-14 shrink-0 rounded-lg bg-slate-800/60" />
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" role="alert" class="mx-auto max-w-sm px-4 py-8">
      <div class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
        </svg>
        <p class="flex-1 text-sm text-red-300">{{ t('mktMenu.error') }}</p>
        <button
          class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
          @click="fetchMenu"
        >{{ t('common.retry') }}</button>
      </div>
    </div>

    <template v-else-if="restaurant">
      <!-- Restaurant header -->
      <div class="mx-auto max-w-3xl px-4 py-5">
        <div class="flex items-start gap-4">
          <div class="h-16 w-16 shrink-0 rounded-xl overflow-hidden bg-slate-800 flex items-center justify-center">
            <img v-if="restaurant.logo_url" :src="restaurant.logo_url" :alt="restaurant.name" loading="eager" decoding="async" class="h-full w-full object-cover" @error="$event.target.style.display='none'" />
            <span v-else class="text-2xl">🍽️</span>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <h1 class="text-xl font-bold text-white">{{ restaurant.name }}</h1>
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="restaurant.is_open
                  ? 'bg-emerald-900/80 text-emerald-300'
                  : 'bg-slate-800 text-slate-400'"
              >
                {{ restaurant.is_open ? t('mktMenu.open') : t('mktMenu.closed') }}
              </span>
            </div>
            <p v-if="restaurant.tagline" class="mt-0.5 text-xs text-slate-400">{{ restaurant.tagline }}</p>
            <div class="mt-1 flex flex-wrap gap-2 text-[11px] text-slate-500">
              <span v-if="restaurant.cuisine_type">{{ restaurant.cuisine_type }}</span>
              <span v-if="restaurant.city">· {{ restaurant.city }}</span>
              <span v-if="restaurant.delivery_enabled">
                · <span class="text-sky-400">{{ t('mktMenu.deliveryFee') }}:
                  {{ Number(restaurant.delivery_fee) > 0 ? restaurant.delivery_fee : t('mktMenu.freeDelivery') }}
                </span>
              </span>
              <span v-if="restaurant.delivery_enabled && Number(restaurant.delivery_minimum_order) > 0">
                · {{ t('mktMenu.minOrder', { amount: restaurant.delivery_minimum_order }) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Menu -->
      <div class="mx-auto max-w-3xl px-4 space-y-8">
        <div
          v-for="sc in restaurant.super_categories"
          :key="sc.id"
        >
          <h2 class="mb-3 text-xs font-bold uppercase tracking-widest text-slate-500">{{ sc.name }}</h2>
          <div
            v-for="cat in sc.categories"
            :key="cat.id"
            class="mb-6"
          >
            <h3 class="mb-2 text-sm font-semibold text-slate-300">{{ cat.name }}</h3>
            <div class="space-y-2">
              <div
                v-for="dish in cat.dishes"
                :key="dish.slug"
                class="flex items-start gap-3 rounded-xl border border-slate-800 bg-slate-900/60 p-3"
                :class="{ 'opacity-50': !dish.is_available }"
              >
                <!-- Image -->
                <div v-if="dish.image_url" class="h-14 w-14 shrink-0 rounded-lg overflow-hidden">
                  <img :src="dish.image_url" :alt="dish.name" loading="lazy" decoding="async" class="h-full w-full object-cover" @error="$event.target.style.display='none'" />
                </div>
                <!-- Info -->
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium text-slate-100 leading-snug">{{ dish.name }}</p>
                  <p v-if="dish.description" class="mt-0.5 text-xs text-slate-500 line-clamp-2">{{ dish.description }}</p>
                  <div class="mt-1.5 flex items-center justify-between gap-2">
                    <span class="text-sm font-semibold text-[var(--color-secondary,#f59e0b)]">
                      {{ fmtPrice(dish.price) }}
                    </span>
                    <button
                      v-if="dish.is_available"
                      class="rounded-full bg-[var(--color-secondary,#f59e0b)] px-3 py-1 text-xs font-semibold text-slate-950 hover:opacity-90 transition-opacity"
                      @click="addToCart(dish)"
                    >
                      {{ t('mktMenu.addToCart') }}
                      <span v-if="cartQty(dish.slug)" class="ml-1 opacity-70">+{{ cartQty(dish.slug) }}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Cart bottom bar (visible when cart has items) -->
    <div
      v-if="cart.length && !checkoutOpen"
      class="fixed bottom-0 inset-x-0 z-30 flex justify-center px-4 pb-4"
    >
      <button
        class="w-full max-w-md rounded-2xl bg-[var(--color-secondary,#f59e0b)] px-6 py-3.5 text-sm font-bold text-slate-950 shadow-xl hover:opacity-90 transition-opacity flex items-center justify-between"
        @click="checkoutOpen = true"
      >
        <span class="rounded-full bg-slate-950/20 px-2 py-0.5 text-xs">{{ cartTotalQty }}</span>
        <span>{{ t('mktMenu.checkout') }}</span>
        <span>{{ fmtPrice(cartTotal) }}</span>
      </button>
    </div>

    <!-- Checkout drawer -->
    <Transition name="slide-up">
      <div
        v-if="checkoutOpen"
        ref="checkoutDialogRef"
        role="dialog"
        aria-modal="true"
        aria-labelledby="marketplace-menu-checkout-dialog-title"
        class="fixed inset-0 z-40 flex flex-col bg-slate-950/95 backdrop-blur-sm overflow-y-auto"
        @keydown.esc="checkoutOpen = false"
      >
        <div class="mx-auto w-full max-w-md px-4 py-6 space-y-5">
          <!-- Header -->
          <div class="flex items-center justify-between">
            <h2 id="marketplace-menu-checkout-dialog-title" class="text-base font-bold text-white">{{ t('mktMenu.yourOrder') }}</h2>
            <button class="text-slate-400 hover:text-white text-xl leading-none" :aria-label="t('common.close')" @click="checkoutOpen = false">✕</button>
          </div>

          <!-- Cart items -->
          <div class="space-y-2">
            <div
              v-for="item in cart"
              :key="item.slug"
              class="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900 px-3 py-2"
            >
              <div class="flex-1 min-w-0">
                <p class="text-sm text-slate-100 truncate">{{ item.name }}</p>
                <p class="text-xs text-slate-500">{{ fmtPrice(item.price) }} × {{ item.qty }}</p>
              </div>
              <div class="flex items-center gap-2">
                <button
                  class="h-6 w-6 rounded-full border border-slate-700 text-slate-300 text-xs hover:border-slate-500"
                  :aria-label="t('dishPage.decreaseQuantity')"
                  @click="removeFromCart(item.slug)"
                >−</button>
                <span class="text-sm text-white w-4 text-center" aria-hidden="true">{{ item.qty }}</span>
                <button
                  class="h-6 w-6 rounded-full border border-slate-700 text-slate-300 text-xs hover:border-slate-500"
                  :aria-label="t('dishPage.increaseQuantity')"
                  @click="addToCartBySlug(item.slug)"
                >+</button>
              </div>
            </div>
          </div>

          <!-- Fulfillment type -->
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1.5">{{ t('mktMenu.fulfillmentLabel') }}</label>
            <div class="flex gap-2">
              <button
                class="flex-1 rounded-xl border py-2 text-xs font-medium transition-colors"
                :class="form.fulfillment_type === 'pickup'
                  ? 'border-[var(--color-secondary,#f59e0b)]/60 bg-[var(--color-secondary,#f59e0b)]/10 text-[var(--color-secondary,#f59e0b)]'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                :aria-pressed="form.fulfillment_type === 'pickup'"
                @click="form.fulfillment_type = 'pickup'"
              >{{ t('mktMenu.fulfillmentPickup') }}</button>
              <button
                v-if="restaurant?.delivery_enabled"
                class="flex-1 rounded-xl border py-2 text-xs font-medium transition-colors"
                :class="form.fulfillment_type === 'delivery'
                  ? 'border-sky-500/60 bg-sky-500/10 text-sky-300'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                :aria-pressed="form.fulfillment_type === 'delivery'"
                @click="form.fulfillment_type = 'delivery'"
              >{{ t('mktMenu.fulfillmentDelivery') }}</button>
            </div>
          </div>

          <!-- Customer info -->
          <div class="space-y-3">
            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">
                {{ t('mktMenu.customerName') }}
                <input
                  v-model="form.customer_name"
                  type="text"
                  autocomplete="name"
                  aria-required="true"
                  class="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:border-slate-500 focus:outline-none"
                />
              </label>
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">
                {{ t('mktMenu.customerPhone') }}
                <input
                  v-model="form.customer_phone"
                  type="tel"
                  inputmode="tel"
                  autocomplete="tel"
                  class="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:border-slate-500 focus:outline-none"
                />
              </label>
            </div>
            <div v-if="form.fulfillment_type === 'delivery'">
              <label class="block text-xs font-medium text-slate-400 mb-1">
                {{ t('mktMenu.deliveryAddress') }}
                <textarea
                  v-model="form.delivery_address"
                  rows="2"
                  class="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:border-slate-500 focus:outline-none resize-none"
                />
              </label>
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">
                {{ t('mktMenu.note') }}
                <input
                  v-model="form.customer_note"
                  type="text"
                  class="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:border-slate-500 focus:outline-none"
                />
              </label>
            </div>
          </div>

          <!-- Wallet toggle -->
          <div v-if="customer && Number(customer.wallet_balance) > 0">
            <label class="flex items-center gap-2 cursor-pointer">
              <input v-model="form.use_wallet" type="checkbox" class="rounded" />
              <span class="text-sm text-slate-300">
                {{ t('mktMenu.walletApply', { balance: `${customer.wallet_balance} ${restaurant?.currency}` }) }}
              </span>
            </label>
          </div>

          <!-- Totals -->
          <div class="rounded-xl border border-slate-800 bg-slate-900 px-4 py-3 space-y-1.5 text-sm">
            <div class="flex justify-between text-slate-400">
              <span>{{ t('mktMenu.subtotal') }}</span>
              <span>{{ fmtPrice(cartTotal) }}</span>
            </div>
            <div v-if="form.fulfillment_type === 'delivery'" class="flex justify-between text-slate-400">
              <span>{{ t('mktMenu.deliveryFeeLabel') }}</span>
              <span>{{ fmtPrice(restaurant?.delivery_fee || 0) }}</span>
            </div>
            <div class="flex justify-between font-bold text-white border-t border-slate-800 pt-1.5 mt-1.5">
              <span>{{ t('mktMenu.total') }}</span>
              <span>{{ fmtPrice(orderTotal) }}</span>
            </div>
          </div>

          <!-- Error -->
          <div v-if="checkoutError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
            <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm text-red-300">{{ checkoutError }}</p>
          </div>

          <!-- Submit -->
          <button
            class="w-full rounded-2xl bg-[var(--color-secondary,#f59e0b)] py-3.5 text-sm font-bold text-slate-950 hover:opacity-90 disabled:opacity-50 transition-opacity"
            :disabled="placing"
            @click="placeOrder"
          >
            {{ placing ? t('mktMenu.placing') : t('mktMenu.placeOrder') }}
          </button>
        </div>
      </div>
    </Transition>

    <!-- Inline sign-in modal — triggered when a delivery order requires auth -->
    <CustomerAuthModal
      v-if="showAuthModal"
      @close="showAuthModal = false"
      @authenticated="onAuthenticated"
    />

  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from '../composables/useI18n';
import { useCustomerStore } from '../stores/customer';
import CustomerAuthModal from '../components/CustomerAuthModal.vue';
import api from '../lib/api';

const { t, currentLocale } = useI18n();
const route = useRoute();
const router = useRouter();
const customerStore = useCustomerStore();

const slug = route.params.slug;

// ── State ─────────────────────────────────────────────────────────────────────
const loading = ref(true);
const fetchError = ref(false);
const restaurant = ref(null);
const checkoutOpen = ref(false);
const checkoutDialogRef = ref(null);

const FOCUSABLE_CO = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapCheckoutFocus = (e) => {
  if (!checkoutDialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(checkoutDialogRef.value.querySelectorAll(FOCUSABLE_CO));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

watch(checkoutOpen, async (open) => {
  if (open) {
    await nextTick();
    checkoutDialogRef.value?.querySelector(FOCUSABLE_CO)?.focus();
    document.addEventListener('keydown', trapCheckoutFocus);
  } else {
    document.removeEventListener('keydown', trapCheckoutFocus);
  }
});
onBeforeUnmount(() => document.removeEventListener('keydown', trapCheckoutFocus));
const placing = ref(false);
const checkoutError = ref('');
const showAuthModal = ref(false); // opens when delivery order requires sign-in

// After the customer signs in mid-checkout, retry placing the order automatically.
const onAuthenticated = async () => {
  showAuthModal.value = false;
  checkoutError.value = '';
  await customerStore.fetchCustomer(true);
  placeOrder(); // retry with the newly established session
};

// Cart: [{slug, name, price, qty}]
const cart = ref([]);

const form = reactive({
  fulfillment_type: 'pickup',
  customer_name: '',
  customer_phone: '',
  delivery_address: '',
  customer_note: '',
  use_wallet: false,
});

// ── Customer ─────────────────────────────────────────────────────────────────
const customer = computed(() => customerStore.customer);

// ── Cart helpers ──────────────────────────────────────────────────────────────
const cartQty = (dishSlug) => {
  const item = cart.value.find((i) => i.slug === dishSlug);
  return item ? item.qty : 0;
};

const addToCart = (dish) => {
  const existing = cart.value.find((i) => i.slug === dish.slug);
  if (existing) {
    existing.qty++;
  } else {
    cart.value.push({ slug: dish.slug, name: dish.name, price: dish.price, qty: 1 });
  }
};

const addToCartBySlug = (dishSlug) => {
  const existing = cart.value.find((i) => i.slug === dishSlug);
  if (existing) existing.qty++;
};

const removeFromCart = (dishSlug) => {
  const idx = cart.value.findIndex((i) => i.slug === dishSlug);
  if (idx < 0) return;
  if (cart.value[idx].qty > 1) {
    cart.value[idx].qty--;
  } else {
    cart.value.splice(idx, 1);
  }
};

const cartTotalQty = computed(() => cart.value.reduce((s, i) => s + i.qty, 0));

const cartTotal = computed(() =>
  cart.value.reduce((s, i) => s + Number(i.price) * i.qty, 0)
);

const orderTotal = computed(() => {
  let total = cartTotal.value;
  if (form.fulfillment_type === 'delivery' && restaurant.value) {
    total += Number(restaurant.value.delivery_fee || 0);
  }
  return total;
});

const fmtPrice = (amount) => {
  const cur = restaurant.value?.currency;
  if (!cur) return Number(amount || 0).toFixed(2);
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency: cur,
      maximumFractionDigits: 2,
    }).format(amount || 0);
  } catch {
    return `${Number(amount || 0).toFixed(2)} ${cur}`;
  }
};

// ── API ───────────────────────────────────────────────────────────────────────
const fetchMenu = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const res = await api.get(`/marketplace/menu/${slug}/`);
    restaurant.value = res.data;
    // Pre-fill customer info if signed in
    if (customer.value) {
      form.customer_name = customer.value.name || '';
      form.customer_phone = customer.value.phone || '';
    }
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const placeOrder = async () => {
  checkoutError.value = '';
  if (!form.customer_name.trim()) {
    checkoutError.value = t('mktMenu.nameRequired');
    return;
  }
  placing.value = true;
  try {
    const items = cart.value.map((i) => ({ slug: i.slug, qty: i.qty }));
    const payload = {
      restaurant: slug,
      items,
      fulfillment_type: form.fulfillment_type,
      customer_name: form.customer_name,
      customer_phone: form.customer_phone,
      customer_note: form.customer_note,
      delivery_address: form.delivery_address,
      use_wallet: form.use_wallet,
    };
    const res = await api.post('/marketplace/order/', payload);
    // Navigate to order status page
    router.push({ name: 'marketplace-order-status', params: { slug, orderNumber: res.data.order_number } });
  } catch (err) {
    const code = err?.response?.data?.code;
    if (code === 'auth_required') {
      // Don't leave the customer stuck with an error — open the sign-in modal so
      // they can sign in inline and retry without losing their cart.
      showAuthModal.value = true;
    } else if (code === 'restaurant_closed') {
      checkoutError.value = t('mktMenu.restaurantClosed');
    } else if (code === 'items_unavailable') {
      checkoutError.value = t('mktMenu.itemsUnavailable');
    } else {
      checkoutError.value = t('mktMenu.orderError');
    }
  } finally {
    placing.value = false;
  }
};

onMounted(async () => {
  await customerStore.fetchCustomer();
  fetchMenu();
});
</script>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}
.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
</style>
