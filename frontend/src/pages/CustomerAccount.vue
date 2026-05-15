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

    <!-- Not signed in -->
    <div v-if="!customerStore.isAuthenticated" class="ui-panel ui-reveal p-6 space-y-4 text-center">
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
    <template v-else>
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
                v-if="!customerStore.customer?.phone_verified && !customerStore.customer?.email_verified && !customerStore.customer?.has_google"
                class="ui-chip border-amber-500/40 bg-amber-500/10 text-amber-300 text-[10px]"
              >
                {{ t('customerAccount.notVerified') }}
              </span>
            </div>

            <p v-if="customerStore.customer?.phone" class="text-xs text-slate-400">
              {{ customerStore.customer.phone }}
            </p>
            <p v-if="customerStore.customer?.email" class="text-xs text-slate-400">
              {{ customerStore.customer.email }}
            </p>
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
            class="rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 text-xs"
          >
            <div class="flex items-center justify-between gap-2">
              <RouterLink
                :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
                class="font-semibold text-[var(--color-secondary)] hover:opacity-80"
              >
                {{ t('customerAccount.orderNumber', { number: order.order_number }) }}
              </RouterLink>
              <span class="ui-chip text-[10px]">{{ order.status }}</span>
            </div>
            <div class="mt-1 flex flex-wrap items-center gap-2 text-slate-400">
              <span v-if="order.fulfillment_type">{{ order.fulfillment_type }}</span>
              <span v-if="order.total">{{ order.total }} {{ order.currency }}</span>
              <span v-if="order.created_at">{{ formatDate(order.created_at) }}</span>
            </div>
          </li>
        </ul>
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
              <span v-if="order.total">{{ order.total }} {{ order.currency }}</span>
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
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import CustomerAuthModal from '../components/CustomerAuthModal.vue';
import { useI18n } from '../composables/useI18n';
import { useCartStore } from '../stores/cart';
import { useCustomerStore } from '../stores/customer';
import api from '../lib/api';

const { t } = useI18n();
const customerStore = useCustomerStore();
const cart = useCartStore();

const showAuthModal = ref(false);
const editableName = ref('');
const savingName = ref(false);
const loadingOrders = ref(false);
const ordersError = ref(false);
const apiOrders = ref([]);

const formatDate = (iso) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return iso;
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
  if (!editableName.value.trim()) return;
  savingName.value = true;
  try {
    // Optimistically update the store while we wait for a future PATCH endpoint
    customerStore.customer = { ...customerStore.customer, name: editableName.value.trim() };
  } finally {
    savingName.value = false;
  }
};

const handleLogout = async () => {
  await customerStore.logout();
  apiOrders.value = [];
  editableName.value = '';
};

const onAuthenticated = (customer) => {
  customerStore.setCustomer(customer);
  editableName.value = customer?.name || '';
  fetchOrders();
};

watch(
  () => customerStore.customer,
  (val) => {
    editableName.value = val?.name || '';
  },
  { immediate: true }
);

onMounted(async () => {
  await customerStore.fetchCustomer();
  if (customerStore.isAuthenticated) {
    fetchOrders();
  }
});
</script>
