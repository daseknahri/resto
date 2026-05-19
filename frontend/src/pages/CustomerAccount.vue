<template>
  <div class="space-y-3 px-3 py-2 pb-28 sm:space-y-4 sm:px-4 sm:py-4 sm:pb-6 ui-safe-bottom">
    <header class="ui-hero-ribbon ui-reveal p-3 md:p-5">
      <div class="space-y-1.5">
        <p class="ui-kicker">{{ t('customerAccount.kicker') }}</p>
        <h1 class="ui-display text-2xl font-semibold tracking-tight text-white md:text-3xl">
          {{ t('customerAccount.title') }}
        </h1>
      </div>
    </header>

    <!-- Loading skeleton (before session fetch resolves) -->
    <div v-if="!customerStore.loaded" class="ui-panel ui-reveal p-6 space-y-4 text-center">
      <div class="flex justify-center">
        <span class="flex h-14 w-14 animate-pulse items-center justify-center rounded-full border border-slate-700/70 bg-slate-900/60" />
      </div>
      <div class="space-y-2">
        <div class="mx-auto h-4 w-32 animate-pulse rounded bg-slate-800" />
        <div class="mx-auto h-3 w-48 animate-pulse rounded bg-slate-800/70" />
      </div>
      <div class="mx-auto h-9 w-44 animate-pulse rounded-full bg-slate-800" />
    </div>

    <!-- Not signed in -->
    <div v-else-if="!customerStore.isAuthenticated" class="ui-panel ui-reveal p-6 space-y-4 text-center">
      <div class="flex justify-center">
        <span class="flex h-14 w-14 items-center justify-center rounded-full border border-slate-700/70 bg-slate-900/60">
          <AppIcon name="user" class="h-7 w-7 text-slate-400" />
        </span>
      </div>
      <div class="space-y-1">
        <p class="text-base font-semibold text-slate-100">{{ t('customerAccount.notSignedInTitle') }}</p>
        <p class="text-sm text-slate-400">{{ t('customerAccount.notSignedInBody') }}</p>
      </div>
      <button class="ui-btn-primary mx-auto justify-center" @click="showAuthModal = true">
        <AppIcon name="user" class="h-3.5 w-3.5" />
        {{ t('customerAccount.signIn') }}
      </button>
    </div>

    <!-- Signed in: profile + orders -->
    <template v-else>  <!-- customerStore.loaded && isAuthenticated -->
      <!-- Profile card -->
      <section class="ui-panel ui-reveal p-4 space-y-4">
        <p class="ui-kicker">{{ t('customerAccount.profileTitle') }}</p>

        <div class="flex flex-wrap items-start gap-3">
          <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-slate-700/70 bg-slate-900/60">
            <AppIcon name="user" class="h-5 w-5 text-slate-400" />
          </span>
          <div class="min-w-0 flex-1 space-y-2">
            <!-- Inline name edit -->
            <div class="flex items-center gap-2">
              <input
                v-model.trim="editableName"
                type="text"
                maxlength="80"
                class="ui-input flex-1"
                :placeholder="t('customerAccount.namePlaceholder')"
                :disabled="savingName"
              />
              <button
                v-if="editableName !== (customerStore.customer?.name || '')"
                class="ui-btn-primary shrink-0 px-3 py-1.5 text-xs"
                :disabled="savingName"
                @click="saveName"
              >
                {{ savingName ? t('customerAccount.saving') : t('customerAccount.saveName') }}
              </button>
            </div>

            <!-- Verified badges -->
            <div class="flex flex-wrap gap-2">
              <span
                v-if="customerStore.customer?.phone_verified"
                class="ui-chip border-emerald-500/40 bg-emerald-500/10 text-emerald-300 text-[10px]"
              >
                <AppIcon name="check" class="h-3 w-3" />
                {{ t('customerAccount.verifiedPhone') }}
              </span>
              <span
                v-if="customerStore.customer?.email_verified"
                class="ui-chip border-emerald-500/40 bg-emerald-500/10 text-emerald-300 text-[10px]"
              >
                <AppIcon name="check" class="h-3 w-3" />
                {{ t('customerAccount.verifiedEmail') }}
              </span>
              <span
                v-if="customerStore.customer?.has_google"
                class="ui-chip border-sky-500/40 bg-sky-500/10 text-sky-300 text-[10px]"
              >
                <AppIcon name="info" class="h-3 w-3" />
                {{ t('customerAccount.googleConnected') }}
              </span>
              <span
                v-if="!customerStore.isVerified"
                class="ui-chip border-amber-500/40 bg-amber-500/10 text-amber-300 text-[10px]"
              >
                {{ t('customerAccount.notVerified') }}
              </span>
              <span
                v-if="walletBalance > 0"
                class="ui-chip border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)] text-[10px]"
              >
                💰 {{ walletBalance }} {{ t('customerAccount.walletTitle') }}
              </span>
            </div>

            <p v-if="customerStore.customer?.phone" class="text-xs text-slate-400">
              {{ customerStore.customer.phone }}
            </p>
            <p v-if="customerStore.customer?.email" class="text-xs text-slate-400">
              {{ customerStore.customer.email }}
            </p>

            <!-- Add phone CTA — shown when signed in but no phone yet -->
            <button
              v-if="!customerStore.customer?.phone"
              class="mt-1 inline-flex items-center gap-1.5 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-300 hover:border-amber-500/70 transition-colors"
              @click="showAddPhone = true"
            >
              <AppIcon name="plus" class="h-3 w-3" />
              {{ t('customerAccount.addPhone') }}
            </button>
          </div>
        </div>

        <!-- Locale preference -->
        <div class="rounded-xl border border-slate-800 bg-slate-900/50 p-3 space-y-2">
          <div class="space-y-0.5">
            <p class="text-xs font-semibold text-slate-300">{{ t('customerAccount.localeTitle') }}</p>
            <p class="text-[11px] text-slate-500">{{ t('customerAccount.localeHint') }}</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="lang in [{ code: 'en', label: 'English' }, { code: 'fr', label: 'Français' }, { code: 'ar', label: 'العربية' }]"
              :key="lang.code"
              class="rounded-full border px-3 py-1 text-xs transition-colors"
              :class="selectedLocale === lang.code
                ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
                : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
              :disabled="savingLocale"
              @click="setLocale(lang.code)"
            >{{ lang.label }}</button>
          </div>
        </div>

        <button
          class="ui-btn-outline w-full justify-center text-sm text-red-300 hover:border-red-400/50"
          @click="handleLogout"
        >
          <AppIcon name="close" class="h-3.5 w-3.5" />
          {{ t('customerAccount.signOut') }}
        </button>
      </section>

      <!-- API orders -->
      <section class="ui-panel ui-reveal p-4 space-y-3">
        <p class="ui-kicker">{{ t('customerAccount.ordersTitle') }}</p>

        <div v-if="loadingOrders" class="text-xs text-slate-400">
          {{ t('customerAccount.loading') }}
        </div>
        <div v-else-if="ordersError" class="text-xs text-red-300">
          {{ t('customerAccount.fetchError') }}
        </div>
        <div v-else-if="!apiOrders.length" class="text-xs text-slate-500">
          {{ t('customerAccount.ordersEmpty') }}
        </div>
        <ul v-else class="space-y-2">
          <li
            v-for="order in apiOrders"
            :key="order.order_number"
            class="rounded-xl border border-slate-700/60 bg-slate-900/40 text-xs"
          >
            <!-- Order header row -->
            <div class="flex items-start gap-2 px-3 py-2.5">
              <div class="flex-1 min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <RouterLink
                    :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
                    class="font-semibold text-[var(--color-secondary)] hover:opacity-80"
                  >
                    {{ t('customerAccount.orderNumber', { number: order.order_number }) }}
                  </RouterLink>
                  <span class="ui-chip text-[10px]">{{ statusLabel(order.status) }}</span>
                </div>
                <div class="mt-1 flex flex-wrap items-center gap-2 text-slate-400">
                  <span v-if="order.fulfillment_type">{{
                    order.fulfillment_type === 'pickup' ? t('orderStatus.fulfillmentPickup') :
                    order.fulfillment_type === 'delivery' ? t('orderStatus.fulfillmentDelivery') :
                    order.fulfillment_type === 'table' ? t('orderStatus.fulfillmentTable', { table: order.table_label || '' }) :
                    order.fulfillment_type
                  }}</span>
                  <span v-if="order.total">{{ formatCurrency(order.total, order.currency) }}</span>
                  <span v-if="order.created_at">{{ formatDate(order.created_at) }}</span>
                </div>
                <!-- Rating -->
                <div v-if="order.has_rating" class="mt-1 flex items-center gap-1">
                  <span class="text-amber-400 tracking-tight text-[11px]">{{ '★'.repeat(order.rating_score) }}{{ '☆'.repeat(5 - order.rating_score) }}</span>
                  <span class="text-slate-500 text-[10px]">{{ t('customerAccount.orderRatingStars', { score: order.rating_score }) }}</span>
                </div>
              </div>

              <!-- Expand toggle -->
              <button
                v-if="order.items?.length"
                class="shrink-0 mt-0.5 rounded-lg border border-slate-700/50 bg-slate-800/50 px-2 py-1 text-[10px] font-medium text-slate-400 hover:border-slate-600 hover:text-slate-200 transition-colors"
                @click="toggleOrder(order.order_number)"
              >
                {{ expandedOrders.has(order.order_number) ? t('customerAccount.orderHideItems') : t('customerAccount.orderShowItems') }}
              </button>
            </div>

            <!-- Expanded: item list + reorder button -->
            <Transition name="ui-expand">
              <div v-if="expandedOrders.has(order.order_number) && order.items?.length"
                class="border-t border-slate-700/50 px-3 pb-3 pt-2.5 space-y-2"
              >
                <ul class="space-y-1">
                  <li
                    v-for="(item, idx) in order.items"
                    :key="idx"
                    class="flex items-start justify-between gap-2 text-slate-300"
                  >
                    <span class="min-w-0 flex-1">
                      <span class="text-slate-400">{{ item.qty }}×</span>
                      {{ item.dish_name }}
                      <span v-if="item.options?.length" class="ml-1 text-slate-500">
                        ({{ item.options.map(o => o.name).join(', ') }})
                      </span>
                      <span v-if="item.note" class="ml-1 italic text-slate-500">— {{ item.note }}</span>
                    </span>
                    <span class="shrink-0 text-slate-400">{{ formatCurrency(item.subtotal, order.currency) }}</span>
                  </li>
                </ul>
                <button
                  class="mt-1 inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/10 px-3 py-1.5 text-[11px] font-semibold text-[var(--color-secondary)] hover:bg-[var(--color-secondary)]/20 transition-colors"
                  @click="reorder(order)"
                >
                  <AppIcon name="cart" class="h-3 w-3" />
                  {{ t('customerAccount.reorder') }}
                </button>
              </div>
            </Transition>
          </li>
        </ul>
      </section>

      <!-- Wallet -->
      <section class="ui-panel ui-reveal p-4 space-y-3">
        <div class="flex items-center justify-between gap-2">
          <p class="ui-kicker">{{ t('customerAccount.walletTitle') }}</p>
          <p class="text-lg font-bold text-[var(--color-secondary)]">
            {{ walletBalance }} <span class="text-xs font-normal text-slate-400">{{ t('customerAccount.walletTitle') }}</span>
          </p>
        </div>

        <div v-if="loadingWallet" class="text-xs text-slate-400">{{ t('customerAccount.loading') }}</div>
        <div v-else-if="!walletTransactions.length" class="text-xs text-slate-500">{{ t('customerAccount.walletNoTransactions') }}</div>
        <ul v-else class="space-y-1.5">
          <li
            v-for="tx in walletTransactions"
            :key="tx.id"
            class="flex items-center justify-between gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2 text-xs"
          >
            <div class="min-w-0 space-y-0.5">
              <p class="font-medium text-slate-200">{{ txLabel(tx) }}</p>
              <p class="text-slate-500">{{ formatDate(tx.created_at) }}</p>
            </div>
            <span
              class="shrink-0 font-semibold"
              :class="tx.type === 'payment' ? 'text-red-300' : 'text-emerald-300'"
            >
              {{ tx.type === 'payment' ? '-' : '+' }}{{ tx.amount }}
            </span>
          </li>
        </ul>
      </section>

      <!-- Loyalty Points -->
      <section v-if="loyaltyPoints > 0 || loyaltyConfig" class="ui-panel ui-reveal p-4 space-y-3">
        <div class="flex items-center justify-between gap-2">
          <p class="ui-kicker">{{ t('customerAccount.loyaltyTitle') }}</p>
          <p class="text-lg font-bold text-indigo-300">
            {{ loyaltyPoints }} <span class="text-xs font-normal text-slate-400">{{ t('customerAccount.loyaltyPts') }}</span>
          </p>
        </div>

        <div v-if="loyaltyConfig && loyaltyConfig.enabled">
          <p class="text-xs text-slate-400">
            {{ t('customerAccount.loyaltyEarnRate', { pts: loyaltyConfig.points_per_unit }) }}
          </p>
          <p v-if="loyaltyPoints >= loyaltyConfig.redeem_threshold" class="text-xs text-emerald-300 mt-1">
            {{ t('customerAccount.loyaltyCanRedeem', {
              threshold: loyaltyConfig.redeem_threshold,
              credit: redeemableCredit,
            }) }}
          </p>
          <p v-else class="text-xs text-slate-500 mt-1">
            {{ t('customerAccount.loyaltyNeedMore', {
              need: loyaltyConfig.redeem_threshold - loyaltyPoints,
            }) }}
          </p>

          <div v-if="loyaltyPoints >= loyaltyConfig.redeem_threshold" class="mt-3 flex items-center gap-3">
            <div class="flex items-center gap-2">
              <label class="text-xs text-slate-400">{{ t('customerAccount.loyaltyRedeemLabel') }}</label>
              <input
                v-model.number="redeemAmount"
                type="number"
                :min="loyaltyConfig.redeem_threshold"
                :max="loyaltyPoints"
                :step="loyaltyConfig.redeem_threshold"
                class="ui-input w-24 text-sm"
              />
            </div>
            <button
              class="ui-btn-primary px-3 py-1.5 text-xs"
              :disabled="redeeming || redeemAmount < loyaltyConfig.redeem_threshold"
              @click="redeemPoints"
            >
              {{ redeeming ? t('customerAccount.loyaltyRedeeming') : t('customerAccount.loyaltyRedeem') }}
            </button>
          </div>
          <p v-if="redeemError" class="mt-1 text-xs text-red-300">{{ redeemError }}</p>
          <p v-if="redeemSuccess" class="mt-1 text-xs text-emerald-300">{{ redeemSuccess }}</p>
        </div>
        <p v-else class="text-xs text-slate-500">{{ t('customerAccount.loyaltyNotActive') }}</p>
      </section>

      <!-- Local (localStorage) recent orders -->
      <section v-if="cart.recentOrders?.length" class="ui-panel ui-reveal p-4 space-y-3">
        <p class="ui-kicker">{{ t('customerAccount.localOrdersTitle') }}</p>
        <ul class="space-y-2">
          <li
            v-for="order in cart.recentOrders"
            :key="order.order_number"
            class="rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 text-xs"
          >
            <RouterLink
              :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
              class="font-semibold text-[var(--color-secondary)] hover:opacity-80"
            >
              {{ t('customerAccount.orderNumber', { number: order.order_number }) }}
            </RouterLink>
            <div class="mt-1 text-slate-400">
              <span v-if="order.total">{{ formatCurrency(order.total, order.currency) }}</span>
            </div>
          </li>
        </ul>
      </section>
    </template>

    <CustomerAuthModal
      v-if="showAuthModal"
      @close="showAuthModal = false"
      @authenticated="onAuthenticated"
    />

    <!-- Add phone modal (reuses auth modal, phone tab only) -->
    <CustomerAuthModal
      v-if="showAddPhone"
      :initial-tab="'phone'"
      @close="showAddPhone = false"
      @authenticated="onPhoneAdded"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import CustomerAuthModal from '../components/CustomerAuthModal.vue';
import { useI18n } from '../composables/useI18n';
import { useCartStore } from '../stores/cart';
import { useCustomerStore } from '../stores/customer';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';

const { t, formatCurrency } = useI18n();
const customerStore = useCustomerStore();
const cart = useCartStore();
const toast = useToastStore();
const router = useRouter();

const showAuthModal = ref(false);
const showAddPhone = ref(false);

// ── Order expand / reorder ────────────────────────────────────────────────────
const expandedOrders = ref(new Set());

const toggleOrder = (orderNumber) => {
  const s = new Set(expandedOrders.value);
  if (s.has(orderNumber)) s.delete(orderNumber);
  else s.add(orderNumber);
  expandedOrders.value = s;
};

const reorder = (order) => {
  const items = order.items || [];
  if (!items.length) {
    toast.show(t('customerAccount.reorderEmpty'), 'info');
    return;
  }
  items.forEach((item) => {
    cart.add({
      slug: item.dish_slug,
      name: item.dish_name,
      price: parseFloat(item.unit_price) || 0,
      currency: order.currency || 'USD',
      qty: item.qty,
      note: item.note || '',
      option_ids: (item.options || []).map((o) => o.id).filter(Boolean),
      option_labels: (item.options || []).map((o) => o.name).filter(Boolean),
    });
  });
  toast.show(t('customerAccount.reorderAdded'), 'success');
  router.push({ name: 'cart' });
};
const editableName = ref('');
const savingName = ref(false);
const savingLocale = ref(false);
const selectedLocale = ref('en');
const loadingOrders = ref(false);
const ordersError = ref(false);
const apiOrders = ref([]);
const loadingWallet = ref(false);
const walletTransactions = ref([]);
const walletBalance = computed(() => {
  const raw = customerStore.customer?.wallet_balance;
  const n = Number(raw);
  return Number.isFinite(n) ? n : 0;
});

// ── Loyalty ───────────────────────────────────────────────────────────────────
const loyaltyPoints = computed(() => customerStore.customer?.loyalty_points || 0);
const loyaltyConfig = ref(null);
const redeemAmount = ref(0);
const redeeming = ref(false);
const redeemError = ref('');
const redeemSuccess = ref('');

const redeemableCredit = computed(() => {
  if (!loyaltyConfig.value || !loyaltyPoints.value) return '0.00';
  const pts = Math.min(redeemAmount.value || loyaltyConfig.value.redeem_threshold, loyaltyPoints.value);
  return (pts * Number(loyaltyConfig.value.points_value)).toFixed(2);
});

const fetchLoyaltyConfig = async () => {
  try {
    const res = await api.get('/owner/loyalty/');
    loyaltyConfig.value = res.data;
    redeemAmount.value = res.data.redeem_threshold;
  } catch {
    // Silent — loyalty section will show nothing if not configured
  }
};

const redeemPoints = async () => {
  redeemError.value = '';
  redeemSuccess.value = '';
  redeeming.value = true;
  try {
    const res = await api.post('/customer/loyalty/redeem/', { points: redeemAmount.value });
    // Update customer store with new balances
    if (customerStore.customer) {
      customerStore.setCustomer({
        ...customerStore.customer,
        loyalty_points: res.data.new_points_balance,
        wallet_balance: res.data.new_wallet_balance,
      });
    }
    redeemSuccess.value = t('customerAccount.loyaltyRedeemSuccess', {
      pts: res.data.redeemed_points,
      credit: res.data.credit_amount,
    });
    redeemAmount.value = loyaltyConfig.value?.redeem_threshold || 100;
  } catch (err) {
    redeemError.value = err?.response?.data?.detail || t('customerAccount.loyaltyRedeemFailed');
  } finally {
    redeeming.value = false;
  }
};

const formatDate = (iso) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return iso;
  }
};

const STATUS_I18N = {
  pending: 'orderStatus.statusPending',
  confirmed: 'orderStatus.statusConfirmed',
  preparing: 'orderStatus.statusPreparing',
  ready: 'orderStatus.statusReady',
  completed: 'orderStatus.statusCompleted',
  cancelled: 'orderStatus.statusCancelled',
};
const statusLabel = (s) => s ? t(STATUS_I18N[s] || 'orderStatus.statusPending') : '';

const TX_LABEL_MAP = {
  topup: 'customerAccount.walletTxTopup',
  payment: 'customerAccount.walletTxPayment',
  refund: 'customerAccount.walletTxRefund',
  bonus: 'customerAccount.walletTxBonus',
  loyalty: 'customerAccount.walletTxLoyalty',
};
const txLabel = (tx) => {
  const base = t(TX_LABEL_MAP[tx.type] || 'customerAccount.walletTxFallback');
  return tx.reference ? `${base} ${tx.reference}` : base;
};

const fetchWallet = async () => {
  if (!customerStore.isAuthenticated) return;
  loadingWallet.value = true;
  try {
    const res = await api.get('/customer/wallet/');
    walletTransactions.value = res.data.transactions || [];
    // Sync the live balance into the customer store (balance may have changed)
    if (res.data.balance !== undefined && customerStore.customer) {
      customerStore.setCustomer({ ...customerStore.customer, wallet_balance: res.data.balance });
    }
  } catch {
    // Silent — wallet section shows empty state
  } finally {
    loadingWallet.value = false;
  }
};

const fetchOrders = async () => {
  if (!customerStore.isAuthenticated) return;
  loadingOrders.value = true;
  ordersError.value = false;
  try {
    const res = await api.get('/customer/orders/');
    apiOrders.value = res.data.orders || [];
  } catch {
    ordersError.value = true;
  } finally {
    loadingOrders.value = false;
  }
};

const saveName = async () => {
  const trimmed = editableName.value.trim();
  if (!trimmed) return;
  savingName.value = true;
  try {
    const res = await api.patch('/customer/profile/', { name: trimmed });
    customerStore.setCustomer(res.data.customer);
  } catch {
    // revert to server value on failure
    editableName.value = customerStore.customer?.name || '';
  } finally {
    savingName.value = false;
  }
};

const setLocale = async (code) => {
  if (savingLocale.value || code === selectedLocale.value) return;
  savingLocale.value = true;
  try {
    const res = await api.patch('/customer/profile/', { locale: code });
    customerStore.setCustomer(res.data.customer);
    selectedLocale.value = code;
    toast.show(t('customerAccount.localeSaved'), 'success');
  } catch {
    toast.show(t('customerAccount.localeSaveFailed'), 'error');
  } finally {
    savingLocale.value = false;
  }
};

const handleLogout = async () => {
  await customerStore.logout();
  apiOrders.value = [];
  walletTransactions.value = [];
  editableName.value = '';
  selectedLocale.value = 'en';
};

const onAuthenticated = (customer) => {
  customerStore.setCustomer(customer);
  editableName.value = customer?.name || '';
  selectedLocale.value = customer?.locale || 'en';
  fetchOrders();
  fetchWallet();
};

const onPhoneAdded = (customer) => {
  customerStore.setCustomer(customer);
  editableName.value = customer?.name || '';
  selectedLocale.value = customer?.locale || 'en';
  showAddPhone.value = false;
};

watch(
  () => customerStore.customer,
  (val) => {
    editableName.value = val?.name || '';
    selectedLocale.value = val?.locale || 'en';
  },
  { immediate: true }
);

onMounted(async () => {
  await customerStore.fetchCustomer();
  if (customerStore.isAuthenticated) {
    fetchOrders();
    fetchWallet();
    fetchLoyaltyConfig();
  }
});
</script>

<style scoped>
/* Expand / collapse transition for order item lists */
.ui-expand-enter-active,
.ui-expand-leave-active {
  transition: opacity 0.2s ease, max-height 0.25s ease;
  overflow: hidden;
  max-height: 600px;
}
.ui-expand-enter-from,
.ui-expand-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
