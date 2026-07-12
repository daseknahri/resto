<template>

  <!-- Vertical filter chips -->
  <div v-if="verticalFilterOptions.length > 1" class="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
    <button
      v-for="opt in verticalFilterOptions"
      :key="opt.id"
      type="button"
      class="shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition-colors"
      :class="selectedVertical === opt.id
        ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
        : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
      @click="emit('select-vertical', opt.id)"
    >{{ opt.label }}</button>
  </div>

  <!-- Order search -->
  <div class="relative">
    <svg class="pointer-events-none absolute start-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9Z" clip-rule="evenodd"/>
    </svg>
    <input
      v-model.trim="searchDraft"
      type="search"
      class="w-full rounded-xl border border-slate-700/60 bg-slate-800/50 py-2 ps-9 pe-3 text-sm text-slate-200 placeholder-slate-500 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
      :placeholder="t('customerAccount.orderSearchPlaceholder')"
    />
  </div>

  <!-- Order history across all restaurants (marketplace index) -->
  <div v-if="marketplaceOrders.length" class="ui-panel ui-reveal overflow-hidden p-0">
    <div class="border-b border-slate-800/70 px-4 py-3">
      <p class="ui-kicker">{{ t('customerAccount.allOrdersTitle') }}</p>
      <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.allOrdersHint') }}</p>
    </div>
    <div v-if="!filteredMarketplaceOrders.length" class="px-4 py-6 text-center text-sm text-slate-500">
      {{ t('customerAccount.orderSearchNoResults') }}
    </div>
    <ul v-else class="divide-y divide-slate-800/60">
      <li v-for="o in filteredMarketplaceOrders" :key="o.restaurant_slug + o.order_number">
        <div class="flex items-center gap-3 px-4 py-3">
          <!-- Status dot -->
          <span
            class="mt-0.5 h-1.5 w-1.5 shrink-0 self-start rounded-full"
            :class="{
              'animate-pulse bg-amber-400': activeStatuses.has(o.status),
              'bg-emerald-400': o.status === 'completed',
              'bg-red-400': o.status === 'cancelled',
              'bg-slate-500': !activeStatuses.has(o.status) && o.status !== 'completed' && o.status !== 'cancelled',
            }"
            aria-hidden="true"
          />
          <RouterLink
            v-if="o.restaurant_slug"
            :to="{ name: 'marketplace-order-status', params: { slug: o.restaurant_slug, orderNumber: o.order_number } }"
            class="min-w-0 flex-1"
          >
            <p class="truncate text-sm font-medium text-slate-200" :title="o.restaurant_name || o.restaurant_slug">{{ o.restaurant_name || o.restaurant_slug }}</p>
            <div class="mt-0.5 flex flex-wrap items-center gap-1.5">
              <span class="font-mono text-[11px] text-slate-500">#{{ o.order_number }}</span>
              <span
                class="rounded-full border border-slate-700/60 bg-slate-900/50 px-1.5 py-0.5 text-[10px]"
                :class="{
                  'text-amber-400': activeStatuses.has(o.status),
                  'text-emerald-400': o.status === 'completed',
                  'text-red-400': o.status === 'cancelled',
                  'text-slate-400': !activeStatuses.has(o.status) && o.status !== 'completed' && o.status !== 'cancelled',
                }"
              >{{ mktOrderStatus(o.status) }}</span>
              <span v-if="o.vertical" class="rounded-full border border-slate-700/40 bg-slate-800/50 px-1.5 py-0.5 text-[10px] text-slate-500">{{ verticalSvcLabels[o.vertical] || o.vertical }}</span>
              <span class="text-[11px] text-slate-500">{{ formatDate(o.created_at) }}</span>
            </div>
          </RouterLink>
          <div v-else class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-slate-200" :title="o.restaurant_name">{{ o.restaurant_name }}</p>
            <p class="text-[11px] text-slate-500"><span class="font-mono">#{{ o.order_number }}</span> · {{ formatDate(o.created_at) }}</p>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <span class="text-sm font-semibold tabular-nums text-slate-300">{{ formatPrice(o.total) }}</span>
            <button
              v-if="o.restaurant_slug && o.items_snapshot?.length"
              class="rounded-full border border-slate-700 px-2.5 py-1 text-[11px] font-semibold text-slate-300 hover:border-[var(--color-secondary,#f59e0b)] hover:text-[var(--color-secondary,#f59e0b)] transition-colors"
              @click="emit('reorder-marketplace', o)"
            >{{ t('customerAccount.reorder') }}</button>
            <button
              v-if="o.can_cancel && o.restaurant_slug"
              :disabled="cancellingOrderNumber === o.order_number"
              class="text-[11px] text-red-400/70 transition-colors hover:text-red-300 disabled:opacity-40"
              @click.stop="emit('cancel-marketplace-order', o)"
            >{{ cancellingOrderNumber === o.order_number ? t('common.loading') : t('customerAccount.cancelOrder') }}</button>
          </div>
        </div>
      </li>
    </ul>

    <!-- Load more button (hidden while a client-side search filter is active) -->
    <div
      v-if="!orderSearch && (marketplaceOrdersHasMore || loadingMoreMarketplaceOrders)"
      class="border-t border-slate-800/70 p-3 text-center"
    >
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-700/60 bg-slate-900/40 px-4 py-2 text-xs font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-500"
        :disabled="loadingMoreMarketplaceOrders"
        @click="emit('load-more-marketplace-orders')"
      >
        <svg v-if="loadingMoreMarketplaceOrders" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
        <AppIcon v-else name="chevronDown" class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        {{ loadingMoreMarketplaceOrders ? t('common.loading') : t('customerAccount.loadMoreOrders') }}
      </button>
    </div>
  </div>

  <!-- Unfiltered-empty: no marketplace orders at all -->
  <div
    v-else-if="!selectedVertical && !loadingMarketplaceOrders && isAuthenticated"
    class="ui-panel ui-reveal p-5 text-center space-y-2"
  >
    <div class="flex h-10 w-10 items-center justify-center rounded-full bg-slate-800/80 mx-auto">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" class="h-5 w-5 text-slate-500" aria-hidden="true"><path d="M6 2 3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4zM3 6h18M16 10a4 4 0 01-8 0"/></svg>
    </div>
    <p class="text-sm text-slate-400">{{ t('customerAccount.noOrdersYet') }}</p>
  </div>

  <!-- Filtered-empty: a service filter is active but returned no orders -->
  <div
    v-else-if="selectedVertical && !loadingMarketplaceOrders"
    class="ui-panel ui-reveal p-5 text-center space-y-2"
  >
    <div class="flex h-10 w-10 items-center justify-center rounded-full bg-slate-800/80 mx-auto">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" class="h-5 w-5 text-slate-500" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
    </div>
    <p class="text-sm text-slate-400">{{ t('customerAccount.noOrdersInService') }}</p>
  </div>

  <div class="ui-panel overflow-hidden p-0">
    <!-- Header -->
    <div class="flex items-center justify-between gap-2 border-b border-slate-800/70 px-4 py-3">
      <div>
        <p class="ui-kicker">{{ t('customerAccount.ordersTitle') }}</p>
        <p v-if="tenantName" class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.atRestaurant', { name: tenantName }) }}</p>
      </div>
      <span v-if="apiOrders.length" class="rounded-full border border-slate-700/60 bg-slate-900/50 px-2 py-0.5 text-[11px] tabular-nums text-slate-400">{{ apiOrders.length }}</span>
    </div>

    <!-- Content -->
    <div class="p-4 space-y-2">
      <div v-if="loadingOrders" class="space-y-2">
        <div v-for="i in 3" :key="i" class="h-14 animate-pulse rounded-xl bg-slate-800/50" />
      </div>
      <div v-else-if="ordersError" class="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
        </svg>
        <p class="flex-1 text-xs text-red-300">{{ t('customerAccount.fetchError') }}</p>
        <button
          class="shrink-0 rounded-lg border border-red-500/40 px-2.5 py-1 text-[10px] font-semibold text-red-300 transition hover:bg-red-500/10"
          @click="emit('retry')"
        >{{ t('common.retry') }}</button>
      </div>

      <div
        v-else-if="!apiOrders.length && !recentOrders.length"
        class="ui-empty-state text-center p-6 space-y-3"
      >
        <AppIcon name="calendar" class="mx-auto h-8 w-8 text-slate-600" aria-hidden="true" />
        <p class="text-sm font-semibold text-slate-300">{{ t('customerAccount.ordersEmpty') }}</p>
        <RouterLink
          to="/"
          class="inline-flex items-center gap-1.5 rounded-xl border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/10 px-4 py-2 text-xs font-semibold text-[var(--color-secondary)] transition-colors hover:border-[var(--color-secondary)] focus-visible:outline-none"
        >{{ t('customerAccount.ordersEmptyCta') }}</RouterLink>
      </div>

      <ul v-else-if="apiOrders.length" class="space-y-2">
        <li
          v-for="(order, idx) in apiOrders"
          :key="order.order_number"
          class="ui-reveal rounded-xl border border-slate-700/60 bg-slate-900/40 text-xs overflow-hidden"
          :style="{ '--ui-delay': `${Math.min(idx, 9) * 28}ms` }"
        >
          <div class="flex items-start gap-2.5 px-3 py-2.5">
            <span
              class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
              :class="{
                'animate-pulse bg-amber-400': activeStatuses.has(order.status),
                'bg-emerald-400': order.status === 'completed',
                'bg-red-400': order.status === 'cancelled',
                'bg-slate-500': !activeStatuses.has(order.status) && order.status !== 'completed' && order.status !== 'cancelled',
              }"
            />
            <div class="min-w-0 flex-1 space-y-1">
              <div class="flex flex-wrap items-center gap-1.5">
                <RouterLink
                  :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
                  class="font-semibold text-[var(--color-secondary)] hover:opacity-80"
                >{{ t('customerAccount.orderNumber', { number: order.order_number }) }}</RouterLink>
                <span class="rounded-full border border-slate-700/60 bg-slate-900/50 px-1.5 py-0.5 text-[10px] text-slate-400">{{ statusLabel(order.status) }}</span>
              </div>
              <!-- Order status mini-timeline — shown for active (non-cancelled) orders -->
              <div
                v-if="order.status !== 'cancelled'"
                class="flex items-center gap-0.5 overflow-x-auto pb-0.5"
                :aria-label="t('customerAccount.orderTimeline')"
                style="scrollbar-width:none"
              >
                <template
                  v-for="(step, si) in (order.fulfillment_type === 'delivery'
                    ? ['pending','confirmed','preparing','out_for_delivery','completed']
                    : ['pending','confirmed','preparing','ready','completed'])"
                  :key="step"
                >
                  <span
                    class="shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-semibold whitespace-nowrap transition-colors"
                    :class="(order.fulfillment_type === 'delivery'
                      ? ['pending','confirmed','preparing','out_for_delivery','completed']
                      : ['pending','confirmed','preparing','ready','completed']).indexOf(order.status) >= si
                      ? 'bg-[var(--color-secondary)]/20 text-[var(--color-secondary)]'
                      : 'bg-slate-800/60 text-slate-600'"
                  >{{ t(`customerAccount.timelineStep_${step}`) }}</span>
                  <span v-if="si < 4" class="h-px w-2 shrink-0 bg-slate-700/60" aria-hidden="true" />
                </template>
              </div>
              <div class="flex flex-wrap items-center gap-2 text-slate-500">
                <span v-if="order.fulfillment_type">{{
                  order.fulfillment_type === 'pickup'   ? t('orderStatus.fulfillmentPickup')   :
                  order.fulfillment_type === 'delivery' ? t('orderStatus.fulfillmentDelivery') :
                  t('orderStatus.fulfillmentTable', { table: order.table_label || '' })
                }}</span>
                <span v-if="order.total" class="font-medium tabular-nums text-slate-400">{{ formatPrice(order.total) }}</span>
                <span v-if="order.created_at">{{ formatDate(order.created_at) }}</span>
              </div>
              <div v-if="order.has_rating" class="flex items-center gap-1 text-[11px] text-amber-400">
                <span class="tracking-tight">{{ '★'.repeat(order.rating_score) }}{{ '☆'.repeat(5 - order.rating_score) }}</span>
                <span class="text-slate-600">·</span>
                <span class="text-slate-500">{{ t('customerAccount.reviewsReviewed') }}</span>
              </div>
              <button
                v-else-if="order.status === 'completed'"
                class="text-[11px] text-slate-500 transition-colors hover:text-amber-400"
                @click="emit('switch-tab', 'reviews')"
              >{{ t('customerAccount.reviewsRateNudge') }}</button>
              <button
                v-if="order.can_cancel"
                :disabled="cancellingOrderNumber === order.order_number"
                class="mt-0.5 text-[11px] text-red-400/70 transition-colors hover:text-red-300 disabled:opacity-40"
                @click.stop="emit('cancel-order', order)"
              >{{ cancellingOrderNumber === order.order_number ? t('common.loading') : t('customerAccount.cancelOrder') }}</button>
            </div>
            <div class="mt-0.5 flex shrink-0 flex-col items-end gap-1">
              <button
                v-if="order.items?.length"
                class="rounded-lg border border-slate-700/50 bg-slate-800/50 px-2 py-1 text-[10px] font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200"
                :aria-expanded="expandedOrders.has(order.order_number)"
                @click="emit('toggle-order', order.order_number)"
              >{{ expandedOrders.has(order.order_number) ? t('customerAccount.orderHideItems') : t('customerAccount.orderShowItems') }}</button>
              <button
                v-if="order.status === 'completed' && order.items?.length"
                class="rounded-lg border border-slate-700/50 bg-slate-800/50 px-2 py-1 text-[10px] font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200"
                @click="emit('view-receipt', order)"
              >{{ t('customerAccount.viewReceipt') }}</button>
            </div>
          </div>
          <Transition name="ui-expand">
            <div
              v-if="expandedOrders.has(order.order_number) && order.items?.length"
              class="border-t border-slate-700/50 px-3 pb-3 pt-2.5 space-y-2"
            >
              <ul class="space-y-1.5">
                <li v-for="(item, itemIdx) in order.items" :key="itemIdx" class="flex items-start gap-2 text-slate-300">
                  <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-700/80 bg-slate-800/70 text-[10px] font-bold text-slate-100 tabular-nums">{{ item.qty }}</span>
                  <span class="min-w-0 flex-1 leading-snug">
                    {{ item.dish_name }}
                    <span v-if="item.options?.length" class="ms-1 text-slate-500">({{ item.options.map(o => o.name).join(', ') }})</span>
                  </span>
                  <span class="shrink-0 tabular-nums font-semibold text-[var(--color-secondary)]">{{ formatPrice(item.subtotal) }}</span>
                </li>
              </ul>
              <!-- Fee/discount breakdown -->
              <div v-if="order.delivery_fee > 0 || order.tip_amount > 0 || order.promotion_discount > 0 || order.loyalty_discount > 0" class="mt-1.5 space-y-0.5 border-t border-slate-700/40 pt-1.5 text-[11px] text-slate-500">
                <div v-if="order.promotion_discount > 0" class="flex items-center justify-between gap-2">
                  <span>{{ t('customerAccount.receiptPromoDiscount') }}</span>
                  <span class="tabular-nums text-emerald-400">-{{ formatPrice(order.promotion_discount) }}</span>
                </div>
                <div v-if="order.loyalty_discount > 0" class="flex items-center justify-between gap-2">
                  <span>{{ t('customerAccount.receiptLoyaltyDiscount') }}</span>
                  <span class="tabular-nums text-emerald-400">-{{ formatPrice(order.loyalty_discount) }}</span>
                </div>
                <div v-if="order.delivery_fee > 0" class="flex items-center justify-between gap-2">
                  <span>{{ t('customerAccount.receiptDeliveryFee') }}</span>
                  <span class="tabular-nums">+{{ formatPrice(order.delivery_fee) }}</span>
                </div>
                <div v-if="order.tip_amount > 0" class="flex items-center justify-between gap-2">
                  <span>{{ t('customerAccount.receiptTip') }}</span>
                  <span class="tabular-nums">+{{ formatPrice(order.tip_amount) }}</span>
                </div>
              </div>
              <button
                class="ui-press mt-1 inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/8 px-3 py-1.5 text-[11px] font-semibold text-[var(--color-secondary)] transition hover:bg-[var(--color-secondary)]/18"
                @click="emit('reorder', order)"
              >
                <AppIcon name="refresh" class="h-3 w-3" aria-hidden="true" />
                {{ t('customerAccount.reorder') }}
              </button>
            </div>
          </Transition>
        </li>
      </ul>

      <!-- Load more button -->
      <div v-if="ordersHasMore || loadingMoreOrders" class="pt-1 text-center">
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-xl border border-slate-700/60 bg-slate-900/40 px-4 py-2 text-xs font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-500"
          :disabled="loadingMoreOrders"
          @click="emit('load-more-orders')"
        >
          <svg v-if="loadingMoreOrders" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          <AppIcon v-else name="chevronDown" class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {{ loadingMoreOrders ? t('common.loading') : t('customerAccount.loadMoreOrders') }}
        </button>
      </div>

      <!-- Local-only orders (pre-login) -->
      <template v-else-if="recentOrders.length">
        <ul class="space-y-2">
          <li
            v-for="order in recentOrders"
            :key="order.order_number"
            class="flex items-center justify-between gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 text-xs"
          >
            <RouterLink
              :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
              class="font-semibold text-[var(--color-secondary)] hover:opacity-80"
            >{{ t('customerAccount.orderNumber', { number: order.order_number }) }}</RouterLink>
            <span v-if="order.total" class="tabular-nums text-slate-400">{{ formatPrice(order.total) }}</span>
          </li>
        </ul>
      </template>
    </div>
  </div>

</template>

<script setup>
// Orders tab of CustomerAccount.vue, extracted as a standalone child component
// (RISK FE-2). CAUTION: this tab renders order history + live order STATUS, so
// — exactly like the Reviews/Reservations/Profile tabs before it — every fetch,
// retry, pagination, cancel and reorder call stays owned by the parent
// (CustomerAccount.vue); this component only renders whatever data it's given
// and asks the parent to run the underlying action via emits. In particular:
//  - apiOrders / marketplaceOrders / loading & error / pagination flags are
//    fetched and owned by the parent because they also feed the stats tile,
//    the live-order banner, the tab-nav badge dot, the overview tile and the
//    Reviews tab (all outside this component) — none of that fetch/derivation
//    logic can move here without duplicating state.
//  - expandedOrders and receiptOrder stay in the parent too: they're plain
//    refs on the *page*, so they survive switching away from this tab and back
//    (the page never unmounts, only this tab's `v-else-if` block does). Owning
//    them locally here would silently reset "expanded" state and close the
//    receipt sheet every time the customer left and re-entered the Orders tab.
//  - selectedVertical / selectVertical() stay in the parent because selecting
//    a vertical triggers an API refetch (fetchMarketplaceOrders) — that's fetch
//    logic, not presentation.
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const { t, formatPrice, currentLocale } = useI18n();

const props = defineProps({
  /** Vertical (food/shops/pharmacy) filter chips for the marketplace order list. */
  verticalFilterOptions: { type: Array, default: () => [] },
  /** Currently selected vertical filter id ('' = all), owned by the parent. */
  selectedVertical: { type: String, default: '' },

  /** Order search query — client-side filter over marketplaceOrders. */
  orderSearch: { type: String, default: '' },

  /** Cross-restaurant marketplace order history + its loading/pagination state. */
  marketplaceOrders: { type: Array, default: () => [] },
  filteredMarketplaceOrders: { type: Array, default: () => [] },
  loadingMarketplaceOrders: { type: Boolean, default: false },
  loadingMoreMarketplaceOrders: { type: Boolean, default: false },
  marketplaceOrdersHasMore: { type: Boolean, default: false },

  /** True once the customer is signed in — gates the "no orders yet" empty state. */
  isAuthenticated: { type: Boolean, default: false },

  /** Current tenant's display name, for "Orders · at <restaurant>". */
  tenantName: { type: String, default: '' },

  /** This-tenant order history + its loading/error/pagination state. */
  apiOrders: { type: Array, default: () => [] },
  loadingOrders: { type: Boolean, default: false },
  ordersError: { type: Boolean, default: false },
  ordersHasMore: { type: Boolean, default: false },
  loadingMoreOrders: { type: Boolean, default: false },

  /** Local (pre-login) recent orders from the cart store — shown as a fallback
   *  when the customer has no API-backed order history yet. */
  recentOrders: { type: Array, default: () => [] },

  /** Set of order statuses considered "active/in-progress" — owned by the
   *  parent since it also drives the live-order banner and tab-nav dot. */
  activeStatuses: { type: Object, default: () => new Set() },
  /** Set of order_numbers currently expanded to show line items — owned by the
   *  parent so the expansion state survives switching tabs away and back. */
  expandedOrders: { type: Object, default: () => new Set() },
  /** order_number currently being cancelled (in-flight), or null. */
  cancellingOrderNumber: { type: [String, Number], default: null },

  /** vertical -> display-label map, shared with the Profile/Wallet tabs. */
  verticalSvcLabels: { type: Object, default: () => ({}) },
});

const emit = defineEmits([
  'update-order-search',
  'select-vertical',
  'reorder-marketplace',
  'cancel-marketplace-order',
  'load-more-marketplace-orders',
  'retry',
  'switch-tab',
  'cancel-order',
  'toggle-order',
  'view-receipt',
  'reorder',
  'load-more-orders',
]);

// Writable local draft backed by the parent's ref — keeps the exact same
// v-model.trim input behavior the inline template had before extraction.
const searchDraft = computed({
  get: () => props.orderSearch,
  set: (v) => emit('update-order-search', v),
});

// Presentational status -> i18n label helpers, local to this tab (identical
// content to the parent's STATUS_I18N — the parent keeps its own copy because
// it also labels orders in the live-order banner and the overview re-order rail).
const STATUS_I18N = {
  pending: 'orderStatus.statusPending',
  confirmed: 'orderStatus.statusConfirmed',
  preparing: 'orderStatus.statusPreparing',
  ready: 'orderStatus.statusReady',
  out_for_delivery: 'orderStatus.stepOutForDelivery',
  completed: 'orderStatus.statusCompleted',
  cancelled: 'orderStatus.statusCancelled',
};
const statusLabel = (s) => (s ? t(STATUS_I18N[s] || 'orderStatus.statusPending') : '');
const mktOrderStatus = (s) => t(STATUS_I18N[s] || 'orderStatus.statusPending');

const formatDate = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(iso));
  } catch { return iso; }
};
</script>
