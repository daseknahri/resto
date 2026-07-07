<template>
  <!-- Customer-confirmed charge: a restaurant is requesting an above-threshold debit.
       Mounted in CustomerLayout so it surfaces on ANY customer page, not just /account. -->
  <Transition name="ui-fade">
    <div
      v-if="activeCharge"
      class="fixed inset-0 z-[3500] flex items-end justify-center bg-black/75 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="`charge-kicker-${activeCharge.id} charge-title-${activeCharge.id}`"
      @keydown.capture="onPanelKey"
    >
      <div
        ref="panelRef"
        class="ui-glass w-full max-w-sm space-y-4 rounded-t-[2rem] p-5 pb-[calc(1.25rem+var(--safe-bottom))] sm:rounded-[2rem] sm:pb-5 ui-reveal"
      >
        <!-- Header -->
        <div class="space-y-1 text-center">
          <p
            :id="`charge-kicker-${activeCharge.id}`"
            class="ui-kicker text-[var(--color-secondary)]"
          >{{ t('chargeRequest.title') }}</p>
          <p
            :id="`charge-title-${activeCharge.id}`"
            role="heading"
            aria-level="2"
            class="tabular-nums text-3xl font-bold tracking-tight text-white"
          >{{ formatPrice(activeCharge.amount) }}</p>
          <p class="ui-subtle">{{ t('chargeRequest.from', { name: activeCharge.restaurant_name || t('chargeRequest.aRestaurant') }) }}</p>
          <p v-if="activeCharge.order_number" class="text-xs text-slate-500">{{ t('chargeRequest.order', { num: activeCharge.order_number }) }}</p>
        </div>

        <!-- Balance band -->
        <div class="ui-context-band px-3 py-2 text-center text-xs text-slate-400">
          <span class="tabular-nums">{{ t('chargeRequest.balanceLine', { balance: formatPrice(walletBalance) }) }}</span>
        </div>

        <!-- Error -->
        <div
          v-if="chargeError"
          class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
        >
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
          <p class="flex-1 text-sm text-red-300">{{ chargeError }}</p>
        </div>

        <!-- Actions -->
        <div class="flex gap-2">
          <button
            ref="declineRef"
            class="ui-btn-outline ui-press ui-touch-target flex-1 text-sm font-semibold disabled:pointer-events-none disabled:opacity-50"
            :disabled="!!chargeBusy"
            :aria-busy="!!chargeBusy"
            :aria-label="chargeBusy ? t('common.loading') : t('chargeRequest.decline')"
            @click="declineCharge(activeCharge)"
          >{{ t('chargeRequest.decline') }}</button>
          <button
            class="ui-btn-primary ui-press ui-touch-target flex-1 text-sm disabled:pointer-events-none disabled:opacity-50"
            :disabled="!!chargeBusy"
            :aria-busy="chargeBusy === activeCharge.id"
            @click="approveCharge(activeCharge)"
          >
            <template v-if="chargeBusy === activeCharge.id">
              <span aria-hidden="true">…</span>
              <span class="sr-only">{{ t('common.loading') }}</span>
            </template>
            <template v-else>{{ t('chargeRequest.approve') }}</template>
          </button>
        </div>
      </div>
    </div>
  </Transition>

  <!-- Surgical 401 re-auth: /customer/ endpoints are excluded from the global
       axios sign-out redirect (see src/lib/api.js), so a stale session on
       approve/decline must be handled here instead of failing silently. -->
  <CustomerAuthModal v-if="showAuthModal" @close="showAuthModal = false" @authenticated="onAuthenticated" />
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useCustomerStore } from '../stores/customer';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';
import AppIcon from './AppIcon.vue';
import CustomerAuthModal from './CustomerAuthModal.vue';

const { t, formatPrice } = useI18n();
const customerStore = useCustomerStore();
const toast = useToastStore();

const pendingCharges = ref([]);
const chargeBusy = ref(null);  // id of the request being approved/declined
const chargeError = ref('');
const showAuthModal = ref(false);
let pollTimer = null;
const POLL_MS = 5000;

// Detects a 401 on a customer-write call, surfaces the session-expired message,
// and opens the sign-in modal so the customer can re-auth without losing the
// pending charge context (it stays in pendingCharges and re-polls after sign-in).
const handleAuthExpired = (err) => {
  if (err?.response?.status !== 401) return false;
  chargeError.value = t('customerAccount.sessionExpired');
  showAuthModal.value = true;
  return true;
};

const onAuthenticated = () => {
  showAuthModal.value = false;
  chargeError.value = '';
  fetchChargeRequests();
};

// Focus management refs
const panelRef = ref(null);
const declineRef = ref(null);
let savedFocus = null;

const activeCharge = computed(() => pendingCharges.value[0] || null);
const walletBalance = computed(() => {
  const n = Number(customerStore.customer?.wallet_balance);
  return Number.isFinite(n) ? n : 0;
});

// Save focus when dialog opens; restore when it closes. Also mark app root inert
// so background content is hidden from assistive technology while the dialog is open.
watch(activeCharge, (next, prev) => {
  if (!prev && next) {
    // Dialog just appeared — save the currently-focused element and move focus inside
    savedFocus = document.activeElement;
    document.getElementById('app')?.setAttribute('inert', '');
    // nextTick equivalent: the DOM is already updated by the time the watcher fires on the next frame
    requestAnimationFrame(() => {
      if (declineRef.value) declineRef.value.focus();
    });
  } else if (prev && !next) {
    // Dialog just closed — restore focus to where the user was
    document.getElementById('app')?.removeAttribute('inert');
    if (savedFocus && typeof savedFocus.focus === 'function') {
      savedFocus.focus();
    }
    savedFocus = null;
  }
});

// Trap focus inside the dialog panel while it is open. Also dismiss on Escape.
const onPanelKey = (e) => {
  if (!panelRef.value) return;
  if (e.key === 'Escape') {
    e.preventDefault();
    declineCharge(activeCharge.value);
    return;
  }
  if (e.key !== 'Tab') return;
  const focusable = Array.from(
    panelRef.value.querySelectorAll('button, [href], input, [tabindex]:not([tabindex="-1"])'),
  ).filter((el) => !el.disabled);
  if (!focusable.length) { e.preventDefault(); return; }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
};

const fetchChargeRequests = async () => {
  if (!customerStore.isAuthenticated) return;
  try {
    const { data } = await api.get('/customer/wallet/charge-requests/');
    pendingCharges.value = Array.isArray(data?.requests) ? data.requests : [];
  } catch {
    /* transient — keep the last known list */
  }
};

const approveCharge = async (req) => {
  if (!req || chargeBusy.value) return;
  chargeBusy.value = req.id;
  chargeError.value = '';
  try {
    const { data } = await api.post(`/customer/wallet/charge-requests/${req.id}/approve/`);
    if (data?.new_balance !== undefined && customerStore.customer) {
      customerStore.setCustomer({ ...customerStore.customer, wallet_balance: data.new_balance });
    }
    pendingCharges.value = pendingCharges.value.filter((r) => r.id !== req.id);
    toast.show(t('chargeRequest.approved', { amount: formatPrice(req.amount) }), 'success');
  } catch (err) {
    if (handleAuthExpired(err)) return;
    const d = err?.response?.data;
    if (d?.code === 'insufficient') {
      chargeError.value = t('chargeRequest.insufficient', { balance: formatPrice(d.balance) });
    } else if (d?.code === 'expired') {
      chargeError.value = t('chargeRequest.expired');
      pendingCharges.value = pendingCharges.value.filter((r) => r.id !== req.id);
    } else {
      chargeError.value = d?.detail || t('chargeRequest.failed');
    }
  } finally {
    chargeBusy.value = null;
  }
};

const declineCharge = async (req) => {
  if (!req || chargeBusy.value) return;
  chargeBusy.value = req.id;
  chargeError.value = '';
  try {
    await api.post(`/customer/wallet/charge-requests/${req.id}/decline/`);
  } catch { /* drop locally even if the call fails */ }
  pendingCharges.value = pendingCharges.value.filter((r) => r.id !== req.id);
  chargeBusy.value = null;
};

const start = () => {
  stop();
  fetchChargeRequests();
  pollTimer = setInterval(fetchChargeRequests, POLL_MS);
};
const stop = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
};

watch(() => customerStore.isAuthenticated, (auth) => {
  if (auth) start();
  else { stop(); pendingCharges.value = []; }
});

onMounted(() => { if (customerStore.isAuthenticated) start(); });
onBeforeUnmount(stop);
</script>
