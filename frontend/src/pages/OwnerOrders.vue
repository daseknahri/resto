<template>
  <div class="ui-page-shell space-y-4">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal space-y-3 px-4 py-4 sm:px-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 space-y-1">
          <p class="ui-kicker">{{ t("ownerOrders.kicker") }}</p>
          <h1 class="ui-display text-2xl font-bold tracking-tight text-white sm:text-3xl">{{ t("ownerOrders.title") }}</h1>
          <p class="ui-subtle">{{ t("ownerOrders.description") }}</p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            class="ui-btn-outline ui-press ui-touch-target px-3 py-1.5 text-sm"
            :class="soundEnabled ? '' : 'opacity-50'"
            :aria-label="soundEnabled ? t('ownerOrders.muteAlerts') : t('ownerOrders.unmuteAlerts')"
            @click="soundEnabled = !soundEnabled"
          >
            <span aria-hidden="true">{{ soundEnabled ? "🔔" : "🔕" }}</span>
          </button>
          <button
            class="ui-btn-outline ui-press inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
            :disabled="exporting || !order.orders.length"
            :aria-label="exporting ? t('ownerOrders.exporting') : t('ownerOrders.exportCsv')"
            @click="exportCsv"
          >
            <AppIcon name="download" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ exporting ? t("ownerOrders.exporting") : t("ownerOrders.exportCsv") }}
          </button>
          <button
            class="ui-btn-outline ui-press inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
            :disabled="order.ordersLoading"
            :aria-label="t('ownerOrders.refreshOrders')"
            @click="refresh"
          >
            <AppIcon name="refresh" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ t("ownerOrders.refreshOrders") }}
          </button>
          <span v-if="polling && order.orders.length" class="text-[11px] text-slate-500 tabular-nums" role="status" aria-live="polite">{{ t('adminAnalytics.updating') }}</span>
        </div>
      </div>

      <!-- Today's stats bar skeleton -->
      <div v-if="order.ordersLoading && !order.orders.length" class="animate-pulse grid grid-cols-3 gap-2 rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-3">
        <div class="flex flex-col items-center gap-1.5">
          <div class="h-6 w-10 rounded bg-slate-700/50" />
          <div class="h-2.5 w-16 rounded bg-slate-800/50" />
        </div>
        <div class="flex flex-col items-center gap-1.5 border-x border-slate-800">
          <div class="h-6 w-14 rounded bg-slate-700/50" />
          <div class="h-2.5 w-16 rounded bg-slate-800/50" />
        </div>
        <div class="flex flex-col items-center gap-1.5">
          <div class="h-6 w-8 rounded bg-slate-700/50" />
          <div class="h-2.5 w-16 rounded bg-slate-800/50" />
        </div>
      </div>

      <!-- Today's stats bar -->
      <div v-else class="grid grid-cols-3 gap-2 rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-3.5">
        <div class="text-center">
          <p class="text-2xl font-bold text-white tabular-nums leading-none">{{ todayStats.count }}</p>
          <p class="mt-1 text-[10px] uppercase tracking-[0.15em] text-slate-500">{{ t("ownerOrders.todayOrders") }}</p>
        </div>
        <div class="border-x border-slate-800 text-center">
          <p class="text-2xl font-bold text-[var(--color-secondary)] tabular-nums leading-none">{{ formatCurrency(todayStats.revenue, todayStats.currency) }}</p>
          <p class="mt-1 text-[10px] uppercase tracking-[0.15em] text-slate-500">{{ t("ownerOrders.todayRevenue") }}</p>
        </div>
        <div class="text-center">
          <p
            class="text-2xl font-bold tabular-nums leading-none transition-colors"
            :class="todayStats.pending > 0 ? 'text-amber-400' : 'text-white'"
          >{{ todayStats.pending }}</p>
          <p class="mt-1 text-[10px] uppercase tracking-[0.15em] text-slate-500">{{ t("ownerOrders.todayPending") }}</p>
        </div>
      </div>

      <!-- Search + date filter row -->
      <div class="flex flex-wrap items-center gap-2">
        <input
          v-model.trim="searchQuery"
          type="search"
          class="ui-input min-w-0 flex-1 text-sm"
          enterkeyhint="search"
          :aria-label="t('ownerOrders.searchPlaceholder')"
          :placeholder="t('ownerOrders.searchPlaceholder')"
          @input="searchQuery = $event.target.value"
        />
        <div class="flex flex-wrap gap-1">
          <button
            v-for="d in dateTabs"
            :key="d.value"
            type="button"
            :aria-pressed="activeDateFilter === d.value"
            class="ui-state-chip ui-press"
            :data-active="activeDateFilter === d.value || undefined"
            @click="activeDateFilter = d.value"
          >
            {{ d.label }}
          </button>
        </div>
        <!-- Custom date-range inputs — shown only when the Custom chip is active -->
        <div v-if="activeDateFilter === 'custom'" class="flex flex-wrap items-center gap-1.5">
          <label class="text-xs text-slate-400" :for="'ord-date-from'">{{ t('ownerOrders.dateFrom') }}</label>
          <input
            id="ord-date-from"
            v-model="customDateFrom"
            type="date"
            class="ui-input py-1 text-xs"
            :max="customDateTo || undefined"
          />
          <label class="text-xs text-slate-400" :for="'ord-date-to'">{{ t('ownerOrders.dateTo') }}</label>
          <input
            id="ord-date-to"
            v-model="customDateTo"
            type="date"
            class="ui-input py-1 text-xs"
            :min="customDateFrom || undefined"
          />
        </div>
        <button
          v-if="searchQuery || activeDateFilter !== 'all' || activeFulfillmentType || customDateFrom || customDateTo || activePaymentStatus"
          class="ui-press rounded-full border border-slate-700 px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200"
          :aria-label="t('ownerOrders.clearFilters')"
          @click="searchQuery = ''; activeDateFilter = 'all'; activeFulfillmentType = ''; customDateFrom = ''; customDateTo = ''; activePaymentStatus = ''"
        >✕</button>
      </div>

      <!-- Fulfillment-type filter chips (only rendered when 2+ types exist in the order list) -->
      <div v-if="fulfillmentTabs.length" class="flex flex-wrap items-center gap-1">
        <span class="me-1 shrink-0 text-[11px] uppercase tracking-wider text-slate-500" aria-hidden="true">{{ t('ownerOrders.fulfillmentFilter') }}</span>
        <button
          v-for="tab in fulfillmentTabs"
          :key="tab.value"
          type="button"
          :aria-pressed="activeFulfillmentType === tab.value"
          class="ui-state-chip ui-press"
          :data-active="activeFulfillmentType === tab.value || undefined"
          @click="activeFulfillmentType = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Payment status filter chips -->
      <div class="flex flex-wrap items-center gap-1">
        <span class="me-1 shrink-0 text-[11px] uppercase tracking-wider text-slate-500" aria-hidden="true">{{ t('ownerOrders.paymentFilter') }}</span>
        <button
          v-for="p in paymentStatusTabs"
          :key="p.value"
          type="button"
          :aria-pressed="activePaymentStatus === p.value"
          class="ui-state-chip ui-press"
          :data-active="activePaymentStatus === p.value || undefined"
          @click="activePaymentStatus = p.value"
        >
          {{ p.label }}
          <span
            v-if="p.count > 0"
            class="ms-1 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-slate-700/80 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums leading-none"
          >{{ p.count }}</span>
        </button>
      </div>

      <!-- Status filter tabs: horizontal scroll on mobile (keeps the order list in view),
           wraps on larger screens where there's room. -->
      <div class="ui-scroll-row gap-1.5 sm:flex-wrap sm:overflow-x-visible sm:pb-0">
        <button
          v-for="tab in statusTabs"
          :key="tab.value"
          type="button"
          :aria-pressed="activeStatus === tab.value"
          class="ui-state-chip ui-press shrink-0 whitespace-nowrap"
          :data-active="activeStatus === tab.value || undefined"
          @click="setFilter(tab.value)"
        >
          {{ tab.label }}
          <span
            v-if="tab.count > 0"
            class="ms-1 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-slate-700/80 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums leading-none"
          >{{ tab.count }}</span>
        </button>
      </div>

      <!-- Active filter summary -->
      <p v-if="filteredOrders.length !== order.orders.length" class="text-xs text-slate-500">
        {{ t("ownerOrders.showingFiltered", { shown: filteredOrders.length, total: order.orders.length }) }}
      </p>
      <!-- Truncation notice when server has more orders than the 200-row display cap -->
      <p v-if="order.ordersHasMore" class="text-xs text-amber-400/80">
        {{ t("ownerOrders.hasMore", { total: order.ordersTotal }) }}
      </p>

      <!-- Batch action: confirm all pending (hidden when search/date filters are narrowing the view) -->
      <div v-if="pendingOrdersList.length > 1 && !activeStatus && !searchQuery && activeDateFilter !== 'yesterday'" class="flex items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2.5" role="status">
        <span class="ui-live-dot shrink-0" aria-hidden="true"></span>
        <span class="min-w-0 flex-1 text-xs text-amber-200 tabular-nums">{{ pendingOrdersList.length }} {{ t("ownerOrders.statusPending").toLowerCase() }}</span>
        <button
          class="ui-press shrink-0 rounded-full border border-amber-500/50 bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-300 transition-colors hover:bg-amber-500/20 disabled:opacity-50"
          :disabled="confirmingAll"
          :aria-busy="confirmingAll"
          :aria-label="confirmingAll ? t('common.loading') : undefined"
          @click="confirmAllPending"
        >
          <span v-if="confirmingAll" class="inline-block animate-spin me-1 h-3 w-3 border border-amber-300 border-t-transparent rounded-full align-middle" aria-hidden="true" />{{ confirmingAll ? t("ownerOrders.confirmingAll") : t("ownerOrders.confirmAllPending", { n: pendingOrdersList.length }) }}
        </button>
      </div>
    </header>

    <!-- Loading: skeleton order cards -->
    <div v-if="order.ordersLoading && !order.orders.length" class="space-y-3">
      <div v-for="i in 3" :key="i" class="ui-panel animate-pulse space-y-3 p-4">
        <div class="flex items-start justify-between gap-3">
          <div class="space-y-2">
            <div class="flex items-center gap-2">
              <div class="h-4 w-20 rounded bg-slate-700/60"></div>
              <div class="h-5 w-16 rounded-full bg-slate-700/50"></div>
              <div class="h-4 w-12 rounded bg-slate-800/60"></div>
            </div>
            <div class="h-3 w-24 rounded bg-slate-800/50"></div>
          </div>
          <div class="space-y-1.5 text-right">
            <div class="h-5 w-16 rounded bg-slate-700/60"></div>
            <div class="h-3 w-10 rounded bg-slate-800/50"></div>
          </div>
        </div>
        <div class="space-y-1.5">
          <div class="h-8 w-full rounded-xl bg-slate-800/50"></div>
          <div class="h-8 w-3/4 rounded-xl bg-slate-800/40"></div>
        </div>
        <div class="flex gap-2">
          <div class="h-7 w-20 rounded-full bg-slate-700/50"></div>
          <div class="h-7 w-16 rounded-full bg-slate-800/50"></div>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="order.ordersError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ order.ordersError }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="refresh"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Empty: filters active but no matches -->
    <div v-else-if="!filteredOrders.length && (activeStatus || activeDateFilter !== 'all' || searchQuery || activeFulfillmentType || customDateFrom || customDateTo || activePaymentStatus)" class="ui-empty-state space-y-3 p-10 text-center" role="status">
      <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-slate-700/60 bg-slate-800/50">
        <AppIcon name="close" class="h-5 w-5 text-slate-500" aria-hidden="true" />
      </div>
      <p class="text-sm font-semibold text-slate-200">{{ t("ownerOrders.noOrders") }}</p>
      <button
        class="ui-btn-outline ui-press inline-flex items-center gap-1.5 px-4 py-1.5 text-xs"
        @click="searchQuery = ''; activeStatus = ''; activeDateFilter = 'all'; activeFulfillmentType = ''; customDateFrom = ''; customDateTo = ''; activePaymentStatus = ''"
      >
        <AppIcon name="close" class="h-3 w-3" aria-hidden="true" />
        {{ t("ownerOrders.clearFilters") }}
      </button>
    </div>

    <!-- Empty: no orders at all -->
    <div v-else-if="!filteredOrders.length" class="ui-empty-state p-12 text-center" role="status">
      <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-slate-700/60 bg-slate-800/50">
        <AppIcon name="refresh" class="h-6 w-6 text-slate-500" aria-hidden="true" />
      </div>
      <p class="mt-4 text-sm font-semibold text-slate-200">{{ t("ownerOrders.noOrdersYet") }}</p>
    </div>

    <!-- Order list -->
    <div v-else class="space-y-2.5">
      <article
        v-for="(o, index) in filteredOrders"
        :key="o.id"
        class="ui-panel ui-surface-lift ui-reveal space-y-3 p-4 transition-colors"
        :class="orderCardClass(o)"
        :aria-label="o.order_number"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms`, 'content-visibility': 'auto', 'contain-intrinsic-size': 'auto 220px' }"
      >
        <!-- Order header -->
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="space-y-1.5">
            <div class="flex flex-wrap items-center gap-2">
              <span class="font-mono text-base font-bold tracking-tight text-white">{{ o.order_number }}</span>
              <span class="rounded-full px-2.5 py-0.5 text-xs font-semibold" :class="statusClass(o.status)">
                {{ statusLabel(o.status) }}
              </span>
              <span class="ui-data-strip font-medium">{{ fulfillmentLabel(o) }}</span>
              <!-- Scheduled-for badge (advance orders) -->
              <span
                v-if="o.scheduled_for"
                class="rounded-full bg-violet-500/15 border border-violet-500/30 px-2 py-0.5 text-[10px] font-semibold text-violet-300"
              >
                <span aria-hidden="true">🗓️</span> {{ formatScheduledFor(o.scheduled_for) }}
              </span>
              <!-- Payment badge -->
              <span
                v-if="o.status !== 'cancelled'"
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="o.payment_status === 'paid' ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'"
              >
                {{ o.payment_status === 'paid' ? t('ownerOrders.paid') : t('ownerOrders.unpaid') }}
              </span>
              <!-- Marketplace source badge -->
              <span
                v-if="o.source === 'marketplace'"
                class="rounded-full bg-violet-500/15 border border-violet-500/30 px-2 py-0.5 text-[10px] font-semibold text-violet-300"
              >
                <span aria-hidden="true">🛒</span> {{ t('ownerOrders.sourceMarketplace') }}
              </span>
              <!-- Age warning badge -->
              <span
                v-if="orderAgeMin(o) >= 5 && ['pending', 'confirmed'].includes(o.status)"
                class="rounded-full px-2 py-0.5 text-[10px] font-bold"
                :class="orderAgeMin(o) >= 10
                  ? 'bg-red-500/25 text-red-300'
                  : 'bg-amber-500/25 text-amber-300'"
              >
                <span aria-hidden="true">⏱</span> {{ orderAgeMin(o) }}m
              </span>
            </div>
            <p class="text-xs font-medium tabular-nums text-slate-400">{{ formatTime(o.created_at) }}</p>
            <!-- Floor section + responsible waiter (table orders) -->
            <p v-if="o.section_name || (o.responsible_waiters && o.responsible_waiters.length)" class="flex flex-wrap items-center gap-1.5 text-xs text-slate-400">
              <span v-if="o.section_name" class="inline-flex items-center gap-1 rounded-full bg-slate-800/70 px-2 py-0.5 text-[10px] font-medium text-slate-300">{{ o.section_name }}</span>
              <span v-if="o.responsible_waiters && o.responsible_waiters.length" class="text-slate-400">
                {{ t('ownerOrders.servedBy', { waiters: o.responsible_waiters.join(', ') }) }}
              </span>
              <span v-else-if="o.fulfillment_type === 'table'" class="text-amber-400/80">{{ t('ownerOrders.noWaiterAssigned') }}</span>
            </p>
          </div>
          <div class="shrink-0 text-end">
            <p class="text-xl font-bold tabular-nums text-[var(--color-secondary)] leading-none">{{ formatCurrency(o.total, o.currency) }}</p>
            <p class="mt-1 text-xs tabular-nums text-slate-400">{{ itemCountLabel(o.items_count) }}</p>
            <p v-if="o.promotion_discount && Number(o.promotion_discount) > 0" class="mt-0.5 text-[10px] tabular-nums text-emerald-400">
              {{ o.applied_promotion_name || t('ownerOrders.promoDiscount') }} −{{ formatCurrency(o.promotion_discount, o.currency) }}
            </p>
            <p v-if="o.tip_amount && Number(o.tip_amount) > 0" class="text-[10px] tabular-nums text-sky-400">
              {{ t('ownerOrders.tip') }} +{{ formatCurrency(o.tip_amount, o.currency) }}
            </p>
            <p v-if="o.wallet_amount_paid && Number(o.wallet_amount_paid) > 0" class="text-[10px] tabular-nums text-emerald-300">
              <span aria-hidden="true">💰</span> {{ t('ownerOrders.walletPaid') }} {{ formatCurrency(o.wallet_amount_paid, o.currency) }}
            </p>
            <p v-if="Number(o.amount_paid) > 0 && o.payment_status !== 'paid'" class="text-[10px] tabular-nums text-amber-400">
              {{ t('waiterPage.paidSoFar', { paid: formatCurrency(o.amount_paid, o.currency), left: formatCurrency(o.outstanding, o.currency) }) }}
            </p>
          </div>
        </div>

        <!-- Customer info -->
        <div v-if="o.customer_name || o.customer_phone || o.customer_email" class="grid gap-2 rounded-xl border border-slate-800/80 bg-slate-950/40 px-3 py-2.5 text-xs sm:grid-cols-2">
          <div v-if="o.customer_name" class="flex flex-wrap items-center gap-2">
            <div>
              <span class="text-slate-500">{{ t("ownerOrders.customer") }}</span>
              <span class="ms-1.5 font-medium text-slate-100" :title="o.customer_name">{{ o.customer_name }}</span>
            </div>
            <!-- Customer trust badge -->
            <template v-if="o.customer_trust?.rating_count">
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="o.customer_trust.avg_score >= 4
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : o.customer_trust.avg_score >= 3
                    ? 'bg-amber-500/15 text-amber-300'
                    : 'bg-red-500/15 text-red-300'"
              >
                <span aria-hidden="true">★</span> {{ o.customer_trust.avg_score }}
                <span class="opacity-70">({{ o.customer_trust.rating_count }})</span>
              </span>
            </template>
          </div>
          <!-- When no name but trust exists (phone/email-only orders) -->
          <template v-else-if="o.customer_trust?.rating_count">
            <div class="flex items-center gap-2">
              <span class="text-slate-500">{{ t("ownerOrders.customerTrustScore") }}</span>
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="o.customer_trust.avg_score >= 4
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : o.customer_trust.avg_score >= 3
                    ? 'bg-amber-500/15 text-amber-300'
                    : 'bg-red-500/15 text-red-300'"
              >
                <span aria-hidden="true">★</span> {{ o.customer_trust.avg_score }}
                <span class="opacity-70">({{ o.customer_trust.rating_count }})</span>
              </span>
            </div>
          </template>
          <div v-if="o.customer_phone" class="flex flex-wrap items-center gap-2">
            <a :href="`tel:${o.customer_phone}`" class="font-medium text-sky-300 hover:text-sky-200">{{ o.customer_phone }}</a>
            <a
              :href="orderWhatsappUrl(o.customer_phone)"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 hover:border-emerald-400/60 hover:bg-emerald-500/20"
            >
              <span aria-hidden="true">💬</span> {{ t("ownerOrders.whatsapp") }}
            </a>
          </div>
          <div v-if="o.customer_email">
            <a :href="`mailto:${o.customer_email}`" class="font-medium text-sky-300 hover:text-sky-200">{{ o.customer_email }}</a>
          </div>
          <div v-if="o.delivery_fee && Number(o.delivery_fee) > 0" class="sm:col-span-2">
            <span class="text-slate-500">{{ t("ownerOrders.deliveryFee") }}</span>
            <span class="ms-1.5 font-medium text-slate-200">{{ formatCurrency(o.delivery_fee, o.currency) }}</span>
          </div>
          <div v-if="o.tip_amount && Number(o.tip_amount) > 0" class="sm:col-span-2">
            <span class="text-slate-500">{{ t("ownerOrders.tip") }}</span>
            <span class="ms-1.5 font-medium text-emerald-300">{{ formatCurrency(o.tip_amount, o.currency) }}</span>
          </div>
          <div v-if="o.wallet_amount_paid && Number(o.wallet_amount_paid) > 0" class="sm:col-span-2">
            <span class="text-slate-500">💰 {{ t("ownerOrders.walletPaid") }}</span>
            <span class="ms-1.5 font-medium text-emerald-300">{{ formatCurrency(o.wallet_amount_paid, o.currency) }}</span>
          </div>
          <div v-if="Number(o.amount_paid) > 0 && o.payment_status !== 'paid'" class="sm:col-span-2">
            <span class="text-slate-500">{{ t('waiterPage.paidSoFar', { paid: formatCurrency(o.amount_paid, o.currency), left: formatCurrency(o.outstanding, o.currency) }) }}</span>
          </div>
          <div v-if="o.delivery_address" class="sm:col-span-2">
            <div class="flex flex-wrap items-start gap-x-2 gap-y-1">
              <span class="shrink-0 text-slate-500">{{ t("ownerOrders.delivery") }}</span>
              <span class="min-w-0 flex-1 break-words text-slate-200">{{ o.delivery_address }}</span>
              <div class="flex shrink-0 items-center gap-1.5">
                <button
                  type="button"
                  class="inline-flex items-center gap-1 rounded-full border border-slate-700/80 px-2 py-0.5 text-[10px] font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200 active:scale-95 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-500"
                  :aria-label="t('ownerOrders.copyAddress')"
                  @click="copyAddress(o)"
                >
                  <svg v-if="copiedAddressId === o.id" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3 text-emerald-400"><path d="M3 8l3.5 3.5L13 4.5"/></svg>
                  <svg v-else aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3"><rect x="4" y="4" width="9" height="11" rx="1.5"/><path d="M3 11V3.5A1.5 1.5 0 0 1 4.5 2H11"/></svg>
                  <span :class="copiedAddressId === o.id ? 'text-emerald-400' : ''">{{ copiedAddressId === o.id ? t('ownerOrders.copied') : t('ownerOrders.copy') }}</span>
                </button>
                <a
                  v-if="orderMapUrl(o)"
                  :href="orderMapUrl(o)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-1 rounded-full border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 text-[10px] font-semibold text-sky-300 hover:border-sky-400/60 hover:bg-sky-500/20"
                >
                  <span aria-hidden="true">📍</span> {{ t("ownerOrders.openMap") }}
                </a>
              </div>
            </div>
          </div>

          <!-- Delivery job panel -->
          <div v-if="o.delivery_job" class="sm:col-span-2 rounded-xl border border-slate-700/50 bg-slate-800/40 p-3 space-y-2 text-xs">
            <div class="flex items-center justify-between gap-2">
              <span class="font-semibold text-slate-300"><span aria-hidden="true">🛵</span> {{ t('ownerOrders.deliveryJobTitle') }}</span>
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="{
                  'bg-amber-500/15 border border-amber-500/30 text-amber-300': o.delivery_job.status === 'searching',
                  'bg-sky-500/15 border border-sky-500/30 text-sky-300': ['assigned','at_restaurant'].includes(o.delivery_job.status),
                  'bg-violet-500/15 border border-violet-500/30 text-violet-300': o.delivery_job.status === 'picked_up',
                  'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300': o.delivery_job.status === 'delivered',
                  'bg-red-500/15 border border-red-500/30 text-red-300': o.delivery_job.status === 'failed',
                }"
              >{{ t(`ownerOrders.djStatus_${o.delivery_job.status}`) }}</span>
            </div>
            <div v-if="o.delivery_job.driver" class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span>{{ o.delivery_job.driver.name || t('ownerOrders.djDriverUnnamed') }}</span>
                <span v-if="o.delivery_job.driver.is_online" class="text-emerald-400">● {{ t('ownerOrders.djOnline') }}</span>
              </div>
              <a
                v-if="o.delivery_job.driver.phone"
                :href="`tel:${o.delivery_job.driver.phone}`"
                class="text-sky-400 hover:text-sky-300"
              >{{ o.delivery_job.driver.phone }}</a>
            </div>
            <p v-else class="text-slate-500">{{ t('ownerOrders.djSearching') }}</p>

            <!-- Failed delivery → the restaurant decides what happens next -->
            <div v-if="o.delivery_job.status === 'failed'" class="space-y-2 rounded-lg border border-red-500/30 bg-red-900/15 p-2">
              <p class="text-[11px] font-semibold text-red-200">
                {{ t('ownerOrders.djFailedTitle') }}
                <span v-if="o.delivery_job.failure_reason" class="font-normal text-red-300/90">· {{ t(`ownerOrders.djReason_${o.delivery_job.failure_reason}`) }}</span>
              </p>
              <p v-if="o.delivery_job.failure_note" class="text-[11px] italic text-slate-400">“{{ o.delivery_job.failure_note }}”</p>
              <Transition name="ui-fade" mode="out-in">
                <!-- Inline refund_cancel confirm -->
                <div
                  v-if="djConfirmId === o.id"
                  key="confirm"
                  class="space-y-2 rounded-xl border border-rose-500/25 bg-rose-500/8 p-3"
                >
                  <div class="flex items-start gap-2.5">
                    <svg class="mt-0.5 h-4 w-4 shrink-0 text-rose-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                      <path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/>
                    </svg>
                    <div class="space-y-0.5">
                      <p class="text-xs font-semibold text-rose-100">{{ t('ownerOrders.djRefundCancelConfirm') }}</p>
                      <p class="text-[11px] leading-relaxed text-rose-200/75">{{ t('ownerOrders.djRefundCancelBody') }}</p>
                    </div>
                  </div>
                  <div class="flex gap-2">
                    <button
                      class="flex-1 rounded-full border border-rose-500/40 bg-rose-500/20 px-2.5 py-1 text-[11px] font-semibold text-rose-200 hover:bg-rose-500/30 disabled:opacity-50"
                      :disabled="deliveryActing === o.id"
                      @click="deliveryAction(o, 'refund_cancel')"
                    >
                      {{ deliveryActing === o.id ? t('common.saving') : t('ownerOrders.djRefundCancelYes') }}
                    </button>
                    <button
                      class="rounded-full border border-slate-600/60 px-2.5 py-1 text-[11px] font-semibold text-slate-400 hover:border-slate-500/60 hover:text-slate-300 disabled:opacity-50"
                      :disabled="deliveryActing === o.id"
                      @click="djConfirmId = null"
                    >{{ t('common.back') }}</button>
                  </div>
                </div>

                <!-- Normal action buttons -->
                <div v-else key="init" class="flex flex-wrap gap-2">
                  <button
                    class="rounded-full border border-sky-500/30 bg-sky-500/15 px-2.5 py-1 text-[11px] font-semibold text-sky-300 hover:bg-sky-500/25 disabled:opacity-50"
                    :disabled="deliveryActing === o.id"
                    @click="deliveryAction(o, 'redispatch')"
                  >{{ t('ownerOrders.djRedispatch') }}</button>
                  <button
                    class="rounded-full border border-red-500/30 bg-red-500/15 px-2.5 py-1 text-[11px] font-semibold text-red-300 hover:bg-red-500/25 disabled:opacity-50"
                    :disabled="deliveryActing === o.id"
                    @click="djConfirmId = o.id"
                  >{{ t('ownerOrders.djRefundCancel') }}</button>
                  <button
                    v-if="o.delivery_job.failure_reason === 'customer_no_show'"
                    class="rounded-full border border-amber-500/30 bg-amber-500/15 px-2.5 py-1 text-[11px] font-semibold text-amber-300 hover:bg-amber-500/25 disabled:opacity-50"
                    :disabled="deliveryActing === o.id"
                    @click="deliveryAction(o, 'confirm_noshow')"
                  >{{ t('ownerOrders.djPayNoshow') }}</button>
                </div>
              </Transition>
              <p v-if="o.delivery_job.resolution" class="text-[11px] text-emerald-400">
                <span aria-hidden="true">✓</span> {{ t(`ownerOrders.djResolution_${o.delivery_job.resolution}`) }}
              </p>
            </div>

            <!-- Rate driver button (only when delivered and not yet rated) -->
            <div v-if="o.delivery_job.status === 'delivered' && !o.delivery_job.restaurant_driver_rating">
              <div v-if="ratingJobId === o.id" class="space-y-1.5">
                <div role="group" :aria-label="t('ownerOrders.djRateDriver')">
                  <div class="flex gap-1">
                    <button
                      v-for="n in 5"
                      :key="n"
                      class="text-lg transition-transform hover:scale-110"
                      :class="ratingScore >= n ? 'text-amber-400' : 'text-slate-600'"
                      :aria-label="t('ownerOrders.djRateStar', { n })"
                      @click="ratingScore = n"
                    ><span aria-hidden="true">★</span></button>
                  </div>
                </div>
                <input
                  v-model="ratingNote"
                  type="text"
                  class="ui-input text-xs"
                  :aria-label="t('ownerOrders.djRatingNotePlaceholder')"
                  :placeholder="t('ownerOrders.djRatingNotePlaceholder')"
                />
                <div class="flex gap-2">
                  <button
                    class="inline-flex items-center gap-1.5 rounded-full bg-[var(--color-secondary,#f59e0b)] px-3 py-1 text-[11px] font-semibold text-slate-950 disabled:opacity-50"
                    :disabled="!ratingScore || submittingRating"
                    :aria-busy="submittingRating"
                    @click="submitJobRating(o)"
                  >
                    <svg v-if="submittingRating" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                    {{ submittingRating ? t('common.loading') : t('ownerOrders.djSubmitRating') }}
                  </button>
                  <button class="text-slate-500 hover:text-slate-300 text-[11px]" @click="ratingJobId = null; ratingScore = 0; ratingNote = ''">{{ t('common.cancel') }}</button>
                </div>
              </div>
              <button
                v-else
                class="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-300 hover:bg-amber-500/20"
                @click="ratingJobId = o.id; ratingScore = 0; ratingNote = ''"
              ><span aria-hidden="true">★</span> {{ t('ownerOrders.djRateDriver') }}</button>
            </div>
            <div v-else-if="o.delivery_job.restaurant_driver_rating" class="text-slate-500">
              {{ t('ownerOrders.djRated', { score: o.delivery_job.restaurant_driver_rating }) }}
            </div>
          </div>
        </div>

        <!-- Items -->
        <div class="space-y-1">
          <div
            v-for="item in o.items"
            :key="item.dish_slug + item.note"
            class="flex items-start justify-between gap-2 rounded-xl border border-slate-800/70 bg-slate-950/30 py-2 pe-3 ps-3 text-xs"
            :class="item.is_voided ? 'opacity-60' : ''"
          >
            <div class="min-w-0 space-y-0.5">
              <p class="flex items-start gap-2 font-semibold leading-snug" :class="item.is_voided ? 'line-through text-slate-500' : 'text-slate-100'">
                <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-700/80 bg-slate-800/70 text-[10px] font-bold tabular-nums" :class="item.is_voided ? 'text-slate-500' : 'text-slate-100'">{{ item.qty }}</span>
                <span class="min-w-0 flex-1">{{ item.dish_name }}</span>
                <span
                  v-if="item.is_voided"
                  class="shrink-0 rounded-full border border-red-500/30 bg-red-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-red-400 leading-none"
                  style="text-decoration:none"
                >{{ t("ownerOrders.voidedBadge") }}</span>
              </p>
              <p v-if="item.options?.length" class="text-slate-400">
                {{ t("ownerOrders.options") }}: {{ item.options.map(o => o.name).join(", ") }}
              </p>
              <p v-if="item.note" class="italic text-slate-400">{{ item.note }}</p>
            </div>
            <p class="shrink-0 font-semibold tabular-nums" :class="item.is_voided ? 'line-through text-slate-500' : 'text-slate-200'">{{ formatCurrency(item.subtotal, o.currency) }}</p>
          </div>
          <p v-if="o.customer_note" class="rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-slate-300">
            <span class="font-semibold text-slate-400">{{ t("ownerOrders.note") }}:</span> {{ o.customer_note }}
          </p>
        </div>

        <!-- Owner note + estimate -->
        <div v-if="editingId === o.id" class="space-y-2 rounded-xl border border-slate-700 bg-slate-900/60 p-3">
          <label class="block space-y-1 text-xs text-slate-400">
            {{ t("ownerOrders.ownerNote") }}
            <input
              v-model="editNote"
              type="text"
              maxlength="300"
              class="ui-input mt-1 text-sm"
              :aria-invalid="noteError ? 'true' : undefined"
              aria-describedby="owner-orders-note-error"
            />
          </label>
          <!-- ETA: quick-pick presets + free-entry input -->
          <div class="space-y-1">
            <p class="text-xs text-slate-400">{{ t("ownerOrders.setEstimate") }}</p>
            <div class="flex flex-wrap items-center gap-1.5">
              <button
                v-for="preset in [10, 15, 20, 25, 30, 45]"
                :key="preset"
                type="button"
                :aria-pressed="editMinutes === preset"
                class="rounded-full border px-2.5 py-0.5 text-[11px] font-semibold transition-colors"
                :class="editMinutes === preset
                  ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
                  : 'border-slate-700 text-slate-300 hover:border-slate-500'"
                @click="editMinutes = preset"
              >{{ preset }}m</button>
              <input
                v-model.number="editMinutes"
                type="number"
                min="1"
                max="180"
                class="ui-input w-20 text-sm"
                :placeholder="t('ownerOrders.minutesPlaceholder')"
              />
            </div>
          </div>
          <div class="flex gap-2">
            <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="order.updatingOrderId === o.id" @click="saveNote(o)">
              {{ order.updatingOrderId === o.id ? t("common.saving") : t("ownerOrders.saveNote") }}
            </button>
            <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="editingId = null">{{ t("common.close") }}</button>
          </div>
          <p v-if="noteError" id="owner-orders-note-error" class="text-xs text-red-400">{{ noteError }}</p>
        </div>

        <div v-else class="flex flex-wrap items-center gap-2">
          <span v-if="o.owner_note" class="rounded-full border border-slate-700/50 bg-slate-800/40 px-2.5 py-0.5 text-xs text-slate-300">
            <span class="font-semibold text-slate-400">{{ t("ownerOrders.ownerNote") }}:</span> {{ o.owner_note }}
          </span>
          <span v-if="o.estimated_ready_minutes" class="ui-data-strip font-semibold text-emerald-200">
            {{ t("ownerOrders.estimatedReady", { minutes: o.estimated_ready_minutes }) }}
          </span>
        </div>

        <!-- Action buttons -->
        <div class="flex flex-wrap items-center gap-2 pt-0.5">
          <template v-if="o.status === 'scheduled'">
            <button class="ui-btn-primary ui-press px-4 py-2 text-xs font-semibold" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'pending')">
              {{ t("ownerOrders.releaseNow") }}
            </button>
            <button class="ui-btn-outline ui-press border-red-500/40 px-3 py-1.5 text-xs text-red-300 hover:border-red-400" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'cancelled')">
              {{ t("ownerOrders.cancel") }}
            </button>
          </template>
          <template v-else-if="o.status === 'pending'">
            <button class="ui-btn-primary ui-press px-4 py-2 text-xs font-semibold" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'confirmed')">
              {{ t("ownerOrders.confirm") }}
            </button>
            <button class="ui-btn-outline ui-press border-red-500/40 px-3 py-1.5 text-xs text-red-300 hover:border-red-400" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'cancelled')">
              {{ t("ownerOrders.cancel") }}
            </button>
          </template>
          <template v-else-if="o.status === 'confirmed'">
            <button class="ui-btn-primary ui-press px-4 py-2 text-xs font-semibold" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'preparing')">
              {{ t("ownerOrders.startPreparing") }}
            </button>
            <button class="ui-btn-outline ui-press border-red-500/40 px-3 py-1.5 text-xs text-red-300 hover:border-red-400" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'cancelled')">
              {{ t("ownerOrders.cancel") }}
            </button>
          </template>
          <template v-else-if="o.status === 'preparing'">
            <button class="ui-btn-primary ui-press px-4 py-2 text-xs font-semibold" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'ready')">
              {{ t("ownerOrders.markReady") }}
            </button>
          </template>
          <template v-else-if="o.status === 'ready'">
            <!-- Delivery: dispatch. Pickup / prepaid dine-in: complete. Unpaid dine-in
                 is finished by the Settle & close button (the pay step). -->
            <button
              v-if="o.fulfillment_type === 'delivery'"
              class="ui-btn-primary ui-press px-4 py-2 text-xs font-semibold" :disabled="order.updatingOrderId === o.id"
              @click="updateStatus(o, 'out_for_delivery')"
            >
              {{ t("ownerOrders.outForDelivery") }}
            </button>
            <button
              v-else-if="o.fulfillment_type !== 'table' || o.payment_status === 'paid'"
              class="ui-btn-primary ui-press px-4 py-2 text-xs font-semibold" :disabled="order.updatingOrderId === o.id"
              @click="updateStatus(o, 'completed')"
            >
              {{ t("ownerOrders.complete") }}
            </button>
          </template>
          <template v-else-if="o.status === 'out_for_delivery'">
            <button class="ui-btn-primary ui-press px-4 py-2 text-xs font-semibold" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'completed')">
              {{ t("ownerOrders.markDelivered") }}
            </button>
            <button
              v-if="o.fulfillment_type === 'delivery'"
              class="ui-btn-outline ui-press inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
              @click="openTrack(o)"
            >
              <span aria-hidden="true">📍</span> {{ t("ownerOrders.trackDelivery") }}
            </button>
          </template>

          <button
            v-if="['pending','confirmed','preparing','ready','out_for_delivery'].includes(o.status)"
            class="ui-btn-outline ui-press px-3 py-1.5 text-xs"
            @click="openEdit(o)"
          >
            {{ t("ownerOrders.noteEtaBtn") }}
          </button>

          <!-- Print ticket -->
          <button
            class="ui-btn-outline ui-press inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
            @click="printTicket(o)"
          >
            <span aria-hidden="true">🖨</span> {{ t("ownerOrders.printTicket") }}
          </button>

          <!-- Settle / Mark paid — record payment collected (cash/card); on a
               ready dine-in order this also closes the open tab. -->
          <button
            v-if="o.payment_status !== 'paid' && o.status !== 'cancelled'"
            class="ui-btn-outline ui-press inline-flex items-center gap-1.5 border-emerald-500/40 px-3 py-1.5 text-xs text-emerald-300 hover:border-emerald-400"
            :disabled="settlingOrderId === o.id"
            :aria-busy="settlingOrderId === o.id"
            :aria-label="settlingOrderId === o.id ? t('common.loading') : undefined"
            @click="settleOrder(o)"
          >
            <span v-if="settlingOrderId === o.id" class="inline-block animate-spin h-3 w-3 border border-emerald-300 border-t-transparent rounded-full" aria-hidden="true" />
            <span v-else aria-hidden="true">💵</span>
            {{ settlingOrderId === o.id ? t("common.saving") : (o.status === 'ready' ? t("ownerOrders.settleAndClose") : t("ownerOrders.markPaid")) }}
          </button>
        </div>
      </article>
    </div>

    <!-- Live delivery tracking modal (owner follows the driver on a map) -->
    <div
      v-if="trackModal.open"
      class="fixed inset-0 z-[2100] flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4"
      @click.self="closeTrack"
      @keydown.esc="closeTrack"
    >
      <div class="ui-panel w-full max-w-lg overflow-hidden rounded-t-2xl sm:rounded-2xl" role="dialog" aria-modal="true" aria-labelledby="track-modal-heading">
        <div class="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <h3 id="track-modal-heading" class="text-sm font-semibold text-slate-100">
            {{ t("ownerOrders.trackTitle") }} <span class="text-slate-500">#{{ trackModal.orderNumber }}</span>
          </h3>
          <button class="ui-btn-outline ui-press px-3 py-1.5 text-xs" @click="closeTrack">{{ t("common.close") }}</button>
        </div>
        <div class="p-4">
          <p v-if="trackModal.error" class="ui-empty-state py-6 text-center text-sm text-slate-400">
            {{ trackModal.error }}
          </p>
          <DeliveryTracker v-else-if="trackModal.delivery" :delivery="trackModal.delivery" />
          <div v-else class="ui-skeleton h-48" aria-busy="true" :aria-label="t('common.loading')" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import DeliveryTracker from "../components/DeliveryTracker.vue";
import { useI18n } from "../composables/useI18n";
import { useConfirmModal } from "../composables/useConfirmModal";
import api from "../lib/api";
import { useOrderStore } from "../stores/order";
import { useToastStore } from "../stores/toast";
import { usePrintTicket } from "../composables/usePrintTicket";

// Explicit name so <KeepAlive :exclude> in OwnerLayout reliably skips this page
// (live orders — polls and must mount & unmount normally).
defineOptions({ name: "OwnerOrders" });

const { t, itemCountLabel, formatNumber, currentLocale } = useI18n();
const order = useOrderStore();
const toast = useToastStore();
const { confirm } = useConfirmModal();
const route = useRoute();

const activeStatus = ref("");
const activeDateFilter = ref("all");
const customDateFrom = ref("");
const customDateTo = ref("");
const searchQuery = ref("");
const activeFulfillmentType = ref("");
const activePaymentStatus = ref(""); // "" = all, "unpaid", "paid"
const exporting = ref(false);
const confirmingAll = ref(false);
const editingId = ref(null);
const editNote = ref("");
const editMinutes = ref(null);
const noteError = ref("");

// Driver rating (from restaurant side — shared score/note refs)
const ratingJobId = ref(null);
const ratingScore = ref(5);
const ratingNote = ref("");
const submittingRating = ref(false);

// Sound preference — persisted in localStorage per hostname
const SOUND_KEY = typeof window === "undefined" ? "orders:sound" : `orders:sound:${window.location.hostname}`;
const soundEnabled = ref((() => {
  try { return localStorage.getItem(SOUND_KEY) !== "off"; } catch { return true; }
})());
watch(soundEnabled, (val) => {
  try { localStorage.setItem(SOUND_KEY, val ? "on" : "off"); } catch { /* ignore */ }
});

// Shared AudioContext — created once on first user gesture so Chrome's autoplay
// policy is satisfied. Any click on the page (including the mute toggle) will
// initialise it; subsequent calls from setInterval simply reuse the same ctx.
let _audioCtx = null;
const _getAudioCtx = () => {
  if (!_audioCtx) {
    try { _audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch { /* not supported */ }
  }
  return _audioCtx;
};
// Prime the context on the first user interaction on this page
if (typeof window !== "undefined") {
  const _prime = () => { _getAudioCtx(); window.removeEventListener("click", _prime, true); };
  window.addEventListener("click", _prime, { capture: true, once: true });
}

// ── Date filter tabs ──────────────────────────────────────────────────────────
const dateTabs = computed(() => [
  { value: "all",       label: t("ownerOrders.dateAll") },
  { value: "today",     label: t("ownerOrders.dateToday") },
  { value: "yesterday", label: t("ownerOrders.dateYesterday") },
  { value: "week",      label: t("ownerOrders.dateLast7") },
  { value: "custom",    label: t("ownerOrders.dateCustom") },
]);

// ── Fulfillment-type filter chips (only shown when 2+ types present) ──────────
const fulfillmentTabs = computed(() => {
  const types = new Set(order.orders.map((o) => o.fulfillment_type).filter(Boolean));
  const tabs = [{ value: "", label: t("ownerOrders.fulfillmentAll") }];
  if (types.has("pickup"))   tabs.push({ value: "pickup",   label: t("ownerOrders.fulfillmentPickup") });
  if (types.has("delivery")) tabs.push({ value: "delivery", label: t("ownerOrders.fulfillmentDelivery") });
  if (types.has("table"))    tabs.push({ value: "table",    label: t("ownerOrders.fulfillmentDineIn") });
  return tabs.length > 2 ? tabs : [];
});

// ── Payment status filter tabs ────────────────────────────────────────────────
const paymentStatusTabs = computed(() => {
  const counts = { unpaid: 0, paid: 0 };
  order.orders.forEach((o) => { if (o.payment_status) counts[o.payment_status] = (counts[o.payment_status] || 0) + 1; });
  return [
    { value: "",       label: t("ownerOrders.paymentAll"),    count: 0 },
    { value: "unpaid", label: t("ownerOrders.paymentUnpaid"), count: counts.unpaid || 0 },
    { value: "paid",   label: t("ownerOrders.paymentPaid"),   count: counts.paid   || 0 },
  ];
});

// ── Status tabs ───────────────────────────────────────────────────────────────
const statusTabs = computed(() => {
  const counts = {};
  order.orders.forEach((o) => { counts[o.status] = (counts[o.status] || 0) + 1; });
  return [
    { value: "", label: t("ownerOrders.allStatuses"), count: 0 },
    { value: "scheduled", label: t("ownerOrders.statusScheduled"), count: counts.scheduled || 0 },
    { value: "pending", label: t("ownerOrders.statusPending"), count: counts.pending || 0 },
    { value: "confirmed", label: t("ownerOrders.statusConfirmed"), count: counts.confirmed || 0 },
    { value: "preparing", label: t("ownerOrders.statusPreparing"), count: counts.preparing || 0 },
    { value: "ready", label: t("ownerOrders.statusReady"), count: counts.ready || 0 },
    { value: "out_for_delivery", label: t("ownerOrders.outForDelivery"), count: counts.out_for_delivery || 0 },
    { value: "completed", label: t("ownerOrders.statusCompleted"), count: counts.completed || 0 },
    { value: "cancelled", label: t("ownerOrders.statusCancelled"), count: counts.cancelled || 0 },
  ];
});

// ── Today's stats ─────────────────────────────────────────────────────────────
const todayStats = computed(() => {
  const today = new Date().toDateString();
  const todayOrders = order.orders.filter((o) => new Date(o.created_at).toDateString() === today);
  const pending = todayOrders.filter((o) => o.status === "pending").length;
  const revenue = todayOrders.reduce((sum, o) => sum + (Number(o.total) || 0), 0);
  const currency = todayOrders.find((o) => o.currency)?.currency || "MAD";
  return { count: todayOrders.length, revenue, pending, currency };
});

// ── Filtered + sorted orders ──────────────────────────────────────────────────
const STATUS_SORT = { scheduled: -1, pending: 0, confirmed: 1, preparing: 2, ready: 3, out_for_delivery: 4, completed: 5, cancelled: 6 };

const filteredOrders = computed(() => {
  const now = new Date();
  const todayStr = now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const yesterdayStr = yesterday.toDateString();
  const weekAgo = new Date(now);
  weekAgo.setDate(now.getDate() - 6);
  weekAgo.setHours(0, 0, 0, 0);

  const q = searchQuery.value.toLowerCase();

  let base = order.orders.filter((o) => {
    // Status filter
    if (activeStatus.value && o.status !== activeStatus.value) return false;

    // Fulfillment-type filter
    if (activeFulfillmentType.value && o.fulfillment_type !== activeFulfillmentType.value) return false;

    // Payment status filter
    if (activePaymentStatus.value && o.payment_status !== activePaymentStatus.value) return false;

    // Date filter
    if (activeDateFilter.value !== "all") {
      const d = new Date(o.created_at);
      if (activeDateFilter.value === "today" && d.toDateString() !== todayStr) return false;
      if (activeDateFilter.value === "yesterday" && d.toDateString() !== yesterdayStr) return false;
      if (activeDateFilter.value === "week" && d < weekAgo) return false;
      if (activeDateFilter.value === "custom") {
        const dateStr = o.created_at.slice(0, 10);
        if (customDateFrom.value && dateStr < customDateFrom.value) return false;
        if (customDateTo.value && dateStr > customDateTo.value) return false;
      }
    }

    // Search filter
    if (q) {
      const haystack = [
        o.order_number,
        o.customer_name,
        o.customer_phone,
        o.customer_email,
        o.delivery_address,
        o.table_label,
      ].filter(Boolean).join(" ").toLowerCase();
      if (!haystack.includes(q)) return false;
    }

    return true;
  });

  return [...base].sort((a, b) => {
    const sd = (STATUS_SORT[a.status] ?? 9) - (STATUS_SORT[b.status] ?? 9);
    if (sd !== 0) return sd;
    // Within same status: newest first
    return new Date(b.created_at) - new Date(a.created_at);
  });
});

const setFilter = (val) => { activeStatus.value = val; };
const refresh = () => order.fetchOrders();

// Copy delivery address to clipboard
const copiedAddressId = ref(null);
let _addrCopyTimer = null;
const copyAddress = async (o) => {
  if (!o.delivery_address) return;
  try {
    await navigator.clipboard.writeText(o.delivery_address);
    copiedAddressId.value = o.id;
    if (_addrCopyTimer) clearTimeout(_addrCopyTimer);
    _addrCopyTimer = setTimeout(() => { copiedAddressId.value = null; _addrCopyTimer = null; }, 1800);
  } catch { /* clipboard not available */ }
};

const pendingOrdersList = computed(() =>
  order.orders.filter((o) => o.status === "pending")
);

const confirmAllPending = async () => {
  if (confirmingAll.value) return;
  const toConfirm = pendingOrdersList.value.slice();
  if (!toConfirm.length) return;
  confirmingAll.value = true;
  try {
    const res = await api.post("/owner/orders/bulk-status/", {
      order_ids: toConfirm.map((o) => o.id),
      status: "confirmed",
    });
    const updated = res.data?.updated ?? toConfirm.length;
    const skipped = res.data?.skipped ?? 0;
    // Refresh list to show the new confirmed statuses
    await order.fetchOrders();
    if (skipped === 0) {
      toast.show(t("ownerOrders.confirmAllDone", { n: updated }), "success");
    } else if (updated > 0) {
      toast.show(t("ownerOrders.confirmAllPartial", { ok: updated, total: toConfirm.length, failed: skipped }), "info");
    } else {
      toast.show(t("ownerOrders.confirmAllFailed"), "error");
    }
  } catch {
    toast.show(t("ownerOrders.confirmAllFailed"), "error");
  } finally {
    confirmingAll.value = false;
  }
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const statusClass = (s) => ({
  scheduled: "bg-violet-500/20 text-violet-200 border border-violet-500/30",
  pending: "bg-amber-500/20 text-amber-200 border border-amber-500/30",
  confirmed: "bg-sky-500/20 text-sky-200 border border-sky-500/30",
  preparing: "bg-orange-500/20 text-orange-200 border border-orange-500/30",
  ready: "bg-emerald-500/20 text-emerald-200 border border-emerald-500/30",
  out_for_delivery: "bg-indigo-500/20 text-indigo-200 border border-indigo-500/30",
  completed: "bg-slate-700 text-slate-300",
  cancelled: "bg-red-500/20 text-red-300 border border-red-500/30",
}[s] || "bg-slate-700 text-slate-300");

const formatScheduledFor = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  try {
    return d.toLocaleString(undefined, {
      weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return d.toLocaleString();
  }
};

const statusLabel = (s) => ({
  scheduled: t("ownerOrders.statusScheduled"),
  pending: t("ownerOrders.statusPending"),
  confirmed: t("ownerOrders.statusConfirmed"),
  preparing: t("ownerOrders.statusPreparing"),
  ready: t("ownerOrders.statusReady"),
  out_for_delivery: t("ownerOrders.outForDelivery"),
  completed: t("ownerOrders.statusCompleted"),
  cancelled: t("ownerOrders.statusCancelled"),
}[s] || s);

const fulfillmentLabel = (o) => {
  if (o.fulfillment_type === "table") return t("ownerOrders.fulfillmentTable", { table: o.table_label || "?" });
  if (o.fulfillment_type === "delivery") return t("ownerOrders.fulfillmentDelivery");
  if (o.fulfillment_type === "pickup") return t("ownerOrders.fulfillmentPickup");
  return "";
};

const formatCurrency = (amount, currency = "USD") => {
  try {
    return formatNumber(Number(amount) || 0, { style: "currency", currency });
  } catch {
    return `${currency} ${Number(amount).toFixed(2)}`;
  }
};

const formatTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diffMin = Math.floor((now - d) / 60000);
  if (diffMin < 1) return t("ownerOrders.justNow");
  if (diffMin < 60) return `${diffMin}m`;
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)}h ${diffMin % 60}m`;
  return new Intl.DateTimeFormat(currentLocale.value, { dateStyle: "short" }).format(d);
};

// ── Delivery helpers ──────────────────────────────────────────────────────────
// Return a safe map URL — only http/https are allowed to prevent javascript: injection.
const orderMapUrl = (o) => {
  const loc = o.delivery_location_url;
  if (loc && (loc.startsWith('http://') || loc.startsWith('https://'))) return loc;
  const lat = o.delivery_lat;
  const lng = o.delivery_lng;
  if (lat != null && lng != null) return `https://maps.google.com/?q=${lat},${lng}`;
  return null;
};

const orderWhatsappUrl = (phone) => {
  if (!phone) return "#";
  const digits = String(phone).replace(/\D/g, "");
  return `https://wa.me/${digits}`;
};

// ── Order age ─────────────────────────────────────────────────────────────────
const orderAgeMin = (o) => Math.floor((Date.now() - new Date(o.created_at)) / 60000);

const orderCardClass = (o) => {
  if (["pending", "confirmed"].includes(o.status)) {
    const age = orderAgeMin(o);
    if (age >= 10) return "border-red-500/60 bg-red-950/5";
    if (age >= 5)  return "border-amber-400/60";
    return "border-amber-500/40";
  }
  if (o.status === "cancelled") return "border-red-500/20";
  return "";
};

// ── Status actions ────────────────────────────────────────────────────────────
const updateStatus = async (o, newStatus) => {
  if (newStatus === "cancelled") {
    const ok = await confirm({
      title: t("ownerOrders.cancelConfirmTitle"),
      body: t("ownerOrders.cancelConfirmBody"),
      confirmLabel: t("ownerOrders.statusCancelled"),
    });
    if (!ok) return;
  }
  try {
    await order.updateOrderStatus(o.id, { status: newStatus });
    toast.show(t("ownerOrders.updated"), "success");
    // After confirming, immediately open the note/ETA panel so the owner can
    // set an estimated ready time in the same action without a second click.
    if (newStatus === "confirmed") {
      const fresh = order.orders.find((x) => x.id === o.id) || o;
      openEdit(fresh);
    }
  } catch {
    toast.show(t("ownerOrders.updateFailed"), "error");
  }
};

const openEdit = (o) => {
  editingId.value = o.id;
  editNote.value = o.owner_note || "";
  editMinutes.value = o.estimated_ready_minutes ?? null;
  noteError.value = "";
};

const saveNote = async (o) => {
  noteError.value = "";
  try {
    await order.updateOrderStatus(o.id, {
      owner_note: editNote.value,
      estimated_ready_minutes: editMinutes.value ?? null,
    });
    editingId.value = null;
    toast.show(t("ownerOrders.updated"), "success");
  } catch {
    noteError.value = t("ownerOrders.updateFailed");
  }
};

// ── Live delivery tracking (owner follows the driver on a map) ─────────────────
const trackModal = ref({ open: false, orderId: null, orderNumber: "", delivery: null, error: "" });
let _trackPoll = null;

const fetchTrack = async () => {
  const id = trackModal.value.orderId;
  if (!id || !trackModal.value.open) return;
  try {
    const { data } = await api.get(`/owner/orders/${id}/delivery-track/`);
    // The modal may have been closed (or switched to another order) while this
    // request was in flight — don't write stale data back.
    if (!trackModal.value.open || trackModal.value.orderId !== id) return;
    trackModal.value.delivery = data;
    trackModal.value.error = "";
    if (data?.is_terminal && _trackPoll) { clearInterval(_trackPoll); _trackPoll = null; }
  } catch (err) {
    if (trackModal.value.open && trackModal.value.orderId === id && !trackModal.value.delivery) {
      trackModal.value.error = err?.response?.data?.detail || t("ownerOrders.trackUnavailable");
    }
  }
};

const openTrack = (o) => {
  trackModal.value = { open: true, orderId: o.id, orderNumber: o.order_number, delivery: null, error: "" };
  fetchTrack();
  if (_trackPoll) clearInterval(_trackPoll);
  _trackPoll = setInterval(fetchTrack, 10000);
};

const closeTrack = () => {
  trackModal.value = { open: false, orderId: null, orderNumber: "", delivery: null, error: "" };
  if (_trackPoll) { clearInterval(_trackPoll); _trackPoll = null; }
};

onUnmounted(() => { if (_trackPoll) clearInterval(_trackPoll); });

// ── Settle / mark order paid ──────────────────────────────────────────────────
// Customer trust ratings are no longer submitted from the owner dashboard — only
// the staff/waiter who served the customer rates them (see the waiter view).
const settlingOrderId = ref(null);
const settleOrder = async (o) => {
  if (settlingOrderId.value) return;
  settlingOrderId.value = o.id;
  try {
    // On a READY order, settling the bill also closes it out (dine-in "settle & close").
    const res = await api.post(`/owner/orders/${o.id}/mark-paid/`, {
      complete: o.status === "ready",
    });
    o.payment_status = res.data.payment_status;
    if (res.data.completed) o.status = res.data.status;
    toast.show(t("ownerOrders.markedPaid"), "success");
  } catch {
    toast.show(t("ownerOrders.markPaidFailed"), "error");
  } finally {
    settlingOrderId.value = null;
  }
};

// ── Driver rating (restaurant rates driver) ───────────────────────────────────
const submitJobRating = async (o) => {
  if (!ratingScore.value || submittingRating.value) return;
  submittingRating.value = true;
  try {
    await api.post(`/marketplace/track/${o.order_number}/rate/`, {
      role: 'restaurant',
      score: ratingScore.value,
      note: ratingNote.value,
    });
    // Update in-place so the rate button disappears
    if (o.delivery_job) {
      o.delivery_job.restaurant_driver_rating = ratingScore.value;
      o.delivery_job.restaurant_driver_note = ratingNote.value;
    }
    ratingJobId.value = null;
    ratingScore.value = 0;
    ratingNote.value = '';
    toast.show(t('ownerOrders.djRatingSubmitted'), 'success');
  } catch {
    toast.show(t('ownerOrders.djRatingFailed'), 'error');
  } finally {
    submittingRating.value = false;
  }
};

// ── Failed-delivery resolution ──────────────────────────────────────────────────
const deliveryActing = ref(null);  // order id currently being resolved
const djConfirmId = ref(null);     // order id awaiting refund_cancel inline confirm
const deliveryAction = async (o, action) => {
  if (deliveryActing.value) return;
  deliveryActing.value = o.id;
  try {
    const { data } = await api.post(`/owner/orders/${o.id}/delivery-action/`, { action });
    toast.show(t(`ownerOrders.djAction_${data.resolution || action}`), 'success');
    djConfirmId.value = null;
    await order.fetchOrders();
  } catch (err) {
    toast.show(err?.response?.data?.detail || t('ownerOrders.djActionFailed'), 'error');
    djConfirmId.value = null;
  } finally {
    deliveryActing.value = null;
  }
};

// ── Print ticket ──────────────────────────────────────────────────────────────
// Thermal-friendly receipt printer (shared with OwnerKitchen). Includes tip + the
// restaurant thank-you note.
const { printTicket } = usePrintTicket();

// ── CSV export ────────────────────────────────────────────────────────────────
// Calls the server export endpoint (up to 5 000 rows, BOM-prefixed for Excel)
// so owners always get the full history, not just the 200 currently in memory.
const _toIsoDate = (d) => {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

const _buildExportParams = () => {
  const params = {};
  if (activeStatus.value) params.status = activeStatus.value;
  const now = new Date();
  if (activeDateFilter.value === "today") {
    params.from = params.to = _toIsoDate(now);
  } else if (activeDateFilter.value === "yesterday") {
    const y = new Date(now); y.setDate(now.getDate() - 1);
    params.from = params.to = _toIsoDate(y);
  } else if (activeDateFilter.value === "week") {
    const w = new Date(now); w.setDate(now.getDate() - 6);
    params.from = _toIsoDate(w);
  } else if (activeDateFilter.value === "custom") {
    if (customDateFrom.value) params.from = customDateFrom.value;
    if (customDateTo.value) params.to = customDateTo.value;
  }
  return params;
};

const exportCsv = async () => {
  exporting.value = true;
  try {
    const response = await api.get("/owner/orders/export/", {
      params: _buildExportParams(),
      responseType: "blob",
      headers: { Accept: "text/csv" },
    });
    const url = URL.createObjectURL(response.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `orders-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch {
    toast.show(t("ownerOrders.exportFailed"), "error");
  } finally {
    exporting.value = false;
  }
};

// ── New-order alert ───────────────────────────────────────────────────────────
const knownOrderIds = ref(new Set());
const lastAlertTime = ref(0);
const RECURRING_ALERT_MS = 2 * 60 * 1000; // re-ping every 2 min while pending orders sit

const playAlertSound = () => {
  if (!soundEnabled.value) return;
  try {
    const ctx = _getAudioCtx();
    if (!ctx) return;
    // Resume if suspended (e.g., tab was backgrounded and context auto-suspended)
    const play = () => {
      [0, 0.18].forEach((delay, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = "sine";
        osc.frequency.setValueAtTime(i === 0 ? 780 : 980, ctx.currentTime + delay);
        gain.gain.setValueAtTime(0.35, ctx.currentTime + delay);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.25);
        osc.start(ctx.currentTime + delay);
        osc.stop(ctx.currentTime + delay + 0.25);
      });
    };
    if (ctx.state === "suspended") {
      ctx.resume().then(play).catch(() => {});
    } else {
      play();
    }
  } catch {
    // AudioContext not available
  }
};

const showBrowserNotification = (count) => {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission !== "granted") return;
  new Notification(t(count === 1 ? "ownerOrders.newOrderNotifTitle_one" : "ownerOrders.newOrderNotifTitle_other", { count }), {
    body: t("ownerOrders.newOrderNotifBody"),
    icon: "/favicon.ico",
    tag: "new-order",
    renotify: true,
  });
};

const checkForNewOrders = (freshOrders) => {
  if (!knownOrderIds.value.size) {
    // First load — seed known IDs, no alert
    freshOrders.forEach((o) => knownOrderIds.value.add(o.id));
    return;
  }
  const newPending = freshOrders.filter(
    (o) => o.status === "pending" && !knownOrderIds.value.has(o.id),
  );
  freshOrders.forEach((o) => knownOrderIds.value.add(o.id));
  if (newPending.length) {
    playAlertSound();
    showBrowserNotification(newPending.length);
    toast.show(t(newPending.length === 1 ? "ownerOrders.newOrderNotifTitle_one" : "ownerOrders.newOrderNotifTitle_other", { count: newPending.length }), "info");
    lastAlertTime.value = Date.now();
  }
};

const requestNotificationPermission = async () => {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission === "default") await Notification.requestPermission();
};

// ── Polling (visibility-aware) ────────────────────────────────────────────────
let pollTimer = null;
const polling = ref(false);

const doPoll = async () => {
  polling.value = true;
  try {
    // Always fetch all orders (no status filter) — filtering is client-side only.
    // Passing activeStatus to the API would replace the full list with a subset,
    // making other status groups disappear until the next manual refresh.
    const fresh = await order.fetchOrders("", { silent: true });
    const orders = Array.isArray(fresh) ? fresh : order.orders;
    checkForNewOrders(orders);

    // Recurring alert: re-ping if there are still unhandled pending orders
    const hasPending = orders.some((o) => o.status === "pending");
    const cooldownPassed = Date.now() - lastAlertTime.value > RECURRING_ALERT_MS;
    if (hasPending && knownOrderIds.value.size > 0 && cooldownPassed) {
      playAlertSound();
      lastAlertTime.value = Date.now();
    }
  } finally {
    polling.value = false;
  }
};

const onPageVisible = () => {
  // Immediately refresh when the owner switches back to this tab
  if (typeof document !== "undefined" && document.visibilityState === "visible") {
    doPoll();
  }
};

onMounted(async () => {
  // Pre-populate search from ?q= query param (e.g. deep-linked from Ratings page)
  if (route.query.q) searchQuery.value = String(route.query.q);

  await requestNotificationPermission();
  const initial = await order.fetchOrders();
  checkForNewOrders(Array.isArray(initial) ? initial : order.orders);

  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", onPageVisible);
  }

  pollTimer = setInterval(() => {
    // Skip the API call when the tab is in the background — runs on resume instead
    if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
    doPoll();
  }, 15000); // 15 s — faster than layout's 30 s
});

onUnmounted(() => {
  clearInterval(pollTimer);
  if (typeof document !== "undefined") {
    document.removeEventListener("visibilitychange", onPageVisible);
  }
});
</script>
