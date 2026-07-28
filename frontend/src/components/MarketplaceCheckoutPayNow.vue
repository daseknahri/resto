<template>
  <!-- Pay now (marketplace orders are pay-now) -->
  <div class="space-y-2">
    <!-- Trusted customers: choose wallet or cash on handover -->
    <div v-if="codEligible" class="grid grid-cols-2 gap-2">
      <button
        type="button"
        class="rounded-xl border px-3 py-2.5 text-xs font-semibold transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
        :class="paymentMethod === 'wallet' ? 'border-emerald-500/55 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-600'"
        :aria-pressed="paymentMethod === 'wallet'"
        @click="paymentMethod = 'wallet'"
      >{{ t('mktMenu.payMethodWallet') }}</button>
      <button
        type="button"
        class="rounded-xl border px-3 py-2.5 text-xs font-semibold transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
        :class="paymentMethod === 'cash' ? 'border-emerald-500/55 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-600'"
        :aria-pressed="paymentMethod === 'cash'"
        @click="paymentMethod = 'cash'"
      >{{ t('mktMenu.payMethodCash') }}</button>
    </div>

    <!-- Cash on handover panel -->
    <div v-if="codChosen" class="ui-panel rounded-xl border border-emerald-500/30 bg-emerald-500/8 px-4 py-3">
      <p class="text-sm font-semibold text-emerald-300">{{ t('mktMenu.payCashOnHandoverTitle') }}</p>
      <p class="mt-0.5 text-xs text-slate-400">{{ t('mktMenu.payCashOnHandoverNote') }}</p>
    </div>

    <!-- Pay now from wallet -->
    <div
      v-else
      class="ui-panel rounded-xl border px-4 py-3"
      :class="walletCoversTotal ? 'border-emerald-500/30 bg-emerald-500/8' : 'border-amber-500/40 bg-amber-500/8'"
    >
      <p class="text-sm font-semibold" :class="walletCoversTotal ? 'text-emerald-300' : 'text-amber-300'">
        {{ t('mktMenu.payFromWalletTitle') }}
      </p>
      <p class="text-xs text-slate-400">{{ t('mktMenu.walletBalanceLine', { balance: `${walletBalance} ${currency}` }) }}</p>
      <p v-if="!walletCoversTotal" class="mt-1 text-xs text-amber-200">
        {{ t('mktMenu.walletShortNotice', { amount: fmtPrice(orderTotal - walletBalanceNum) }) }}
        <RouterLink
          :to="{ name: 'customer-account', query: { tab: 'wallet' } }"
          class="ms-1.5 underline hover:no-underline text-amber-300"
        >{{ t('mktMenu.topUpWallet') }}</RouterLink>
      </p>
    </div>
  </div>
</template>

<script setup>
// The "pay now" panel of MarketplaceMenuPage.vue's checkout drawer, extracted as a
// child (RISK FE-2). Marketplace orders are pay-now: trusted customers pick wallet vs
// cash-on-handover; otherwise it's wallet-only with a balance line + a top-up nudge
// when the balance falls short. It owns NO order logic — the chosen method is a
// two-way model bound to the parent's `paymentMethod`, and everything else (whether
// COD is eligible / chosen, whether the wallet covers the total, the balance, the
// total, the shortfall) is derived in the parent and passed as props. The parent's
// placeOrder reads `paymentMethod` verbatim. The mounting condition
// (`isAuthenticated && orderTotal > 0`) stays on the component tag in the parent.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

/** The chosen pay-now method ('wallet' | 'cash'), two-way (paymentMethod). */
const paymentMethod = defineModel('paymentMethod', { type: String, default: 'wallet' });

defineProps({
  /** Whether cash-on-handover is offered (codEligible). */
  codEligible: { type: Boolean, default: false },
  /** Whether cash-on-handover is the current choice (codChosen). */
  codChosen: { type: Boolean, default: false },
  /** Whether the wallet balance covers the total (walletCoversTotal). */
  walletCoversTotal: { type: Boolean, default: false },
  /** Displayed wallet balance (customer.wallet_balance || 0). */
  walletBalance: { type: [Number, String], default: 0 },
  /** Currency code (restaurant.currency) for the balance line. */
  currency: { type: String, default: '' },
  /** Grand total (orderTotal) for the shortfall calc. */
  orderTotal: { type: Number, default: 0 },
  /** Numeric wallet balance (walletBalanceNum) for the shortfall calc. */
  walletBalanceNum: { type: Number, default: 0 },
  /** Price formatter (fmtPrice). */
  fmtPrice: { type: Function, required: true },
});
</script>
