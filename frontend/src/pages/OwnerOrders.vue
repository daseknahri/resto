<template>
  <div class="ui-page-shell space-y-4">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal space-y-3 px-4 py-4 sm:px-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 space-y-1">
          <p class="ui-kicker">{{ t("ownerOrders.kicker") }}</p>
          <div class="flex flex-wrap items-center gap-2">
            <h1 class="ui-display text-2xl font-bold tracking-tight text-white sm:text-3xl">{{ t("ownerOrders.title") }}</h1>
            <span
              v-if="autoAcceptOn"
              class="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-200"
              :title="t('ownerOrders.autoAcceptingHint')"
            >
              <AppIcon name="check-circle" class="h-3 w-3" aria-hidden="true" />
              {{ t("ownerOrders.autoAccepting") }}
            </span>
          </div>
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

      <!-- Today's stats bar — sticky so counts stay visible while scrolling -->
      <div v-else class="sticky top-0 z-10 grid grid-cols-3 gap-2 rounded-xl border border-slate-800 bg-slate-900/95 px-3 py-3.5 backdrop-blur-sm">
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
        <!-- Active filter context strip — shown only when a filter is active (active tab only; History has its own controls) -->
        <Transition name="ui-fade">
          <div
            v-if="activeTab === 'active' && (activeStatus || searchQuery || activeFulfillmentType || activePaymentStatus || activeDateFilter !== 'all')"
            class="col-span-3 mt-1 flex flex-wrap items-center gap-1.5 border-t border-slate-800/60 pt-2 text-[10px] text-slate-500"
          >
            <span>{{ t('ownerOrders.filterContextLabel') }}</span>
            <span v-if="activeStatus" class="rounded-full bg-slate-800 px-1.5 py-0.5 font-semibold text-slate-300">
              {{ statusTabs.find(t => t.value === activeStatus)?.label || activeStatus }}
            </span>
            <span v-if="searchQuery" class="rounded-full bg-slate-800 px-1.5 py-0.5 font-semibold text-slate-300">"{{ searchQuery }}"</span>
            <span v-if="activeFulfillmentType" class="rounded-full bg-slate-800 px-1.5 py-0.5 font-semibold text-slate-300">{{ activeFulfillmentType }}</span>
            <span v-if="activePaymentStatus" class="rounded-full bg-slate-800 px-1.5 py-0.5 font-semibold text-slate-300">{{ activePaymentStatus }}</span>
            <span v-if="activeDateFilter !== 'all'" class="rounded-full bg-slate-800 px-1.5 py-0.5 font-semibold text-slate-300">{{ t(`ownerOrders.dateFilter_${activeDateFilter}`) }}</span>
            <button
              class="ms-auto rounded-full px-1.5 py-0.5 text-slate-600 hover:text-slate-400 ui-press"
              @click="searchQuery = ''; activeStatus = ''; activeDateFilter = 'all'; activeFulfillmentType = ''; customDateFrom = ''; customDateTo = ''; activePaymentStatus = ''"
            >{{ t('ownerOrders.clearFilters') }}</button>
          </div>
        </Transition>
      </div>

      <!-- Search + filter trigger row (active tab only; History has its own date-range controls) -->
      <div v-if="activeTab === 'active'" class="flex flex-wrap items-center gap-2">
        <input
          v-model.trim="searchQuery"
          type="search"
          class="ui-input min-w-0 flex-1 text-sm"
          enterkeyhint="search"
          :aria-label="t('ownerOrders.searchPlaceholder')"
          :placeholder="t('ownerOrders.searchPlaceholder')"
          @input="searchQuery = $event.target.value"
        />
        <!-- Filter sheet trigger -->
        <button
          type="button"
          class="ui-press inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors"
          :class="activeFilterCount > 0
            ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
            : 'border-slate-700 text-slate-400 hover:text-slate-200'"
          :aria-expanded="filterSheetOpen"
          :aria-label="t('ownerOrders.filterBtn')"
          @click="filterSheetOpen = true"
        >
          <AppIcon name="filter" class="h-3.5 w-3.5" aria-hidden="true" />
          {{ t('ownerOrders.filterBtn') }}
          <span
            v-if="activeFilterCount > 0"
            class="inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-[var(--color-secondary)]/20 px-1 py-0.5 text-[10px] font-bold tabular-nums leading-none"
          >{{ activeFilterCount }}</span>
        </button>
        <!-- Clear all filters -->
        <button
          v-if="searchQuery || activeDateFilter !== 'all' || activeFulfillmentType || customDateFrom || customDateTo || activePaymentStatus"
          class="ui-press rounded-full border border-slate-700 px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200"
          :aria-label="t('ownerOrders.clearFilters')"
          @click="searchQuery = ''; activeDateFilter = 'all'; activeFulfillmentType = ''; customDateFrom = ''; customDateTo = ''; activePaymentStatus = ''"
        >✕</button>
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
          <span v-if="tab.urgent" aria-hidden="true">🔴</span> {{ tab.label }}
          <span
            v-if="tab.count > 0"
            class="ms-1 inline-flex min-w-[1.25rem] items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums leading-none"
            :class="tab.urgent ? 'bg-red-500/30 text-red-200' : 'bg-slate-700/80'"
          >{{ tab.count }}</span>
        </button>
      </div>

      <!-- New-order sticky banner — appears when new orders arrive while owner is on the page -->
      <Transition name="ui-fade">
        <button
          v-if="newOrderBannerCount > 0"
          type="button"
          class="ui-press flex w-full items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-left text-sm font-semibold text-amber-300"
          @click="activeStatus = 'pending'; newOrderBannerCount = 0"
        >
          <span class="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-amber-400 shrink-0" aria-hidden="true" />
          {{ t('ownerOrders.newOrderBanner', { count: newOrderBannerCount }) }}
          <span class="ms-auto text-xs font-normal text-amber-400/70">{{ t('ownerOrders.newOrderBannerTap') }}</span>
        </button>
      </Transition>

      <!-- Active filter summary -->
      <p v-if="filteredOrders.length !== order.orders.length" class="text-xs text-slate-500">
        {{ t("ownerOrders.showingFiltered", { shown: filteredOrders.length, total: order.orders.length }) }}
      </p>

      <!-- Tab bar: Active | Past orders -->
      <div class="flex gap-1 rounded-xl border border-slate-800 bg-slate-950/50 p-1" role="tablist">
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'active'"
          class="flex-1 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors"
          :class="activeTab === 'active' ? 'bg-[var(--color-secondary)] text-slate-950' : 'text-slate-400 hover:text-slate-200'"
          @click="activeTab = 'active'"
        >{{ t("ownerOrders.tabActive") }}</button>
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'history'"
          class="flex-1 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors"
          :class="activeTab === 'history' ? 'bg-[var(--color-secondary)] text-slate-950' : 'text-slate-400 hover:text-slate-200'"
          @click="switchToHistory"
        >{{ t("ownerOrders.tabHistory") }}</button>
      </div>

      <!-- Batch action: confirm all pending (always visible while 2+ pending orders exist) -->
      <div v-if="pendingOrdersList.length > 1" class="flex items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2.5" role="status">
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

    <!-- ── UPCOMING / DUE-SOON STRIP: scheduled + near-due advance orders ──── -->
    <section
      v-if="activeTab === 'active' && upcoming.length"
      class="rounded-2xl border border-violet-500/30 bg-violet-500/5 px-4 py-3 space-y-2"
      :aria-label="t('ownerOrders.upcomingTitle')"
    >
      <p class="ui-kicker inline-flex items-center gap-1.5 text-violet-300/80">
        <span aria-hidden="true">🗓️</span>{{ t('ownerOrders.upcomingTitle') }}
      </p>
      <div
        v-for="o in upcoming"
        :key="o.id"
        class="flex items-center justify-between gap-3 rounded-xl border px-3 py-2 text-xs transition-colors"
        :class="upcomingMinutes(o) <= 0
          ? 'border-violet-500/50 bg-violet-500/10'
          : 'border-slate-700/70 bg-slate-950/40'"
      >
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <span class="font-mono font-bold tabular-nums text-white">{{ o.order_number }}</span>
          <span class="ui-data-strip font-medium">{{ fulfillmentLabel(o) }}</span>
          <span class="text-slate-500">{{ formatScheduledFor(o.scheduled_for) }}</span>
          <span
            class="rounded-full px-2 py-0.5 text-[10px] font-bold"
            :class="upcomingMinutes(o) <= 0
              ? 'bg-violet-500/25 text-violet-200'
              : upcomingMinutes(o) <= 30
                ? 'bg-amber-500/20 text-amber-300'
                : 'bg-slate-700/70 text-slate-300'"
          >
            <span aria-hidden="true">⏱</span>
            {{ upcomingMinutes(o) <= 0
              ? t('ownerOrders.dueSoonBadge')
              : t('ownerOrders.upcomingFiresIn', { min: upcomingMinutes(o) }) }}
          </span>
        </div>
        <button
          v-if="o.status === 'scheduled'"
          type="button"
          class="ui-press shrink-0 rounded-full border border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/10 px-3 py-1 text-[11px] font-semibold text-[var(--color-secondary)] transition-colors hover:bg-[var(--color-secondary)]/20 disabled:opacity-50"
          :disabled="order.updatingOrderId === o.id"
          @click="releaseNow(o)"
        >
          {{ order.updatingOrderId === o.id ? t('common.loading') : t('ownerOrders.releaseNow') }}
        </button>
      </div>
    </section>

    <!-- ── ACTIVE TAB: loading / error / empty / list ─────────────────── -->
    <template v-if="activeTab === 'active'">
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
          <div class="space-y-1.5 text-end">
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
    <div v-else-if="!filteredOrders.length" class="ui-empty-state space-y-4 p-8 text-center" role="status">
      <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-slate-700/60 bg-slate-800/50">
        <AppIcon name="chart" class="h-6 w-6 text-slate-500" aria-hidden="true" />
      </div>
      <p class="text-sm font-semibold text-slate-200">{{ t("ownerOrders.noOrdersYet") }}</p>
      <p class="text-xs text-slate-400">{{ t("ownerOrders.noOrdersYetShareHint") }}</p>
      <div class="flex flex-wrap justify-center gap-2">
        <button
          class="ui-btn-primary ui-touch-target justify-center px-4 py-2 text-sm"
          @click="copyMenuUrl"
        >
          {{ t("ownerOrders.noOrdersYetShareBtn") }}
        </button>
        <a
          :href="menuUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="ui-btn-outline ui-touch-target justify-center px-4 py-2 text-sm"
        >
          {{ t("ownerOrders.noOrdersYetStorefrontBtn") }}
        </a>
        <RouterLink
          v-if="tenant.capabilities.tables !== false"
          to="/owner/tables"
          class="ui-btn-outline ui-touch-target justify-center px-4 py-2 text-sm"
        >
          {{ t("ownerOrders.noOrdersYetQrBtn") }}
        </RouterLink>
      </div>
    </div>
    </template>

    <!-- ── HISTORY TAB ──────────────────────────────────────────────────── -->
    <template v-if="activeTab === 'history'">
      <!-- History date-range controls -->
      <div class="flex flex-wrap items-center gap-2 px-1">
        <label class="text-xs text-slate-400">{{ t("ownerOrders.dateFrom") }}</label>
        <input
          v-model="historyFrom"
          type="date"
          class="ui-input py-1 text-xs"
          :max="historyTo || undefined"
          @change="reloadHistory"
        />
        <label class="text-xs text-slate-400">{{ t("ownerOrders.dateTo") }}</label>
        <input
          v-model="historyTo"
          type="date"
          class="ui-input py-1 text-xs"
          :min="historyFrom || undefined"
          @change="reloadHistory"
        />
        <button
          v-if="historyFrom || historyTo"
          class="ui-press rounded-full border border-slate-700 px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200"
          @click="historyFrom = ''; historyTo = ''; reloadHistory()"
        >✕</button>
      </div>

      <!-- Period aggregate summary (shown when a date filter is active and orders loaded) -->
      <div
        v-if="(historyFrom || historyTo) && order.historyOrders.length && !order.historyLoading"
        class="flex items-center gap-4 rounded-xl border border-slate-700/50 bg-slate-800/40 px-4 py-2.5 text-xs text-slate-400"
        role="status"
        :aria-label="t('ownerOrders.periodSummaryLabel')"
      >
        <span>
          <span class="font-semibold text-slate-200 tabular-nums">{{ order.historyOrders.length }}</span>
          {{ t('ownerOrders.periodOrderCount') }}
        </span>
        <span class="h-3 w-px bg-slate-700 shrink-0" aria-hidden="true" />
        <span>
          {{ t('ownerOrders.periodRevenue') }}
          <span class="ms-1 font-semibold text-emerald-300 tabular-nums">{{ historyPeriodRevenue }}</span>
        </span>
        <span v-if="order.historyHasMore" class="ms-auto text-[10px] text-amber-400/80">{{ t('ownerOrders.periodPartial') }}</span>
      </div>

      <!-- History loading skeleton -->
      <div v-if="order.historyLoading && !order.historyOrders.length" class="space-y-3">
        <div v-for="i in 3" :key="i" class="ui-panel animate-pulse space-y-3 p-4">
          <div class="flex items-start justify-between gap-3">
            <div class="space-y-2">
              <div class="h-4 w-20 rounded bg-slate-700/60" />
              <div class="h-3 w-24 rounded bg-slate-800/50" />
            </div>
            <div class="h-5 w-16 rounded bg-slate-700/60" />
          </div>
        </div>
      </div>

      <!-- History error -->
      <div v-else-if="order.historyError && !order.historyOrders.length" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
        <p class="flex-1 text-sm text-red-300">{{ order.historyError }}</p>
        <button class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10" @click="reloadHistory">{{ t("common.retry") }}</button>
      </div>

      <!-- History empty -->
      <div v-else-if="!order.historyLoading && !order.historyOrders.length" class="ui-empty-state p-10 text-center" role="status">
        <p class="text-sm font-semibold text-slate-200">{{ t("ownerOrders.historyEmpty") }}</p>
      </div>

      <!-- History order cards (reuse same rendering logic) -->
      <div v-else class="space-y-2.5">
        <article
          v-for="(o, index) in order.historyOrders"
          :key="o.id"
          class="ui-panel ui-surface-lift ui-reveal space-y-3 p-4 transition-colors"
          :class="orderCardClass(o)"
          :aria-label="o.order_number"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms`, 'content-visibility': 'auto', 'contain-intrinsic-size': 'auto 200px' }"
        >
          <!-- Order header -->
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="space-y-1.5">
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-mono text-base font-bold tracking-tight text-white">{{ o.order_number }}</span>
                <span class="rounded-full px-2.5 py-0.5 text-xs font-semibold" :class="statusClass(o.status)">{{ statusLabel(o.status) }}</span>
                <span class="ui-data-strip font-medium">{{ fulfillmentLabel(o) }}</span>
                <span v-if="o.source === 'marketplace'" class="rounded-full bg-violet-500/15 border border-violet-500/30 px-2 py-0.5 text-[10px] font-semibold text-violet-300">
                  <span aria-hidden="true">🛒</span> {{ t("ownerOrders.sourceMarketplace") }}
                </span>
              </div>
              <p class="text-xs font-medium tabular-nums text-slate-400">{{ formatTime(o.created_at) }}</p>
            </div>
            <div class="shrink-0 text-end">
              <p class="text-xl font-bold tabular-nums text-[var(--color-secondary)] leading-none">{{ formatCurrency(o.total, o.currency) }}</p>
              <p class="mt-1 text-xs tabular-nums text-slate-400">{{ itemCountLabel(o.items_count) }}</p>
            </div>
          </div>

          <!-- Customer info (compact) -->
          <div v-if="o.customer_name || o.customer_phone" class="flex flex-wrap items-center gap-3 text-xs text-slate-400">
            <span v-if="o.customer_name" class="font-medium text-slate-200">{{ o.customer_name }}</span>
            <a v-if="o.customer_phone" :href="`tel:${o.customer_phone}`" class="text-sky-400 hover:text-sky-300">{{ o.customer_phone }}</a>
          </div>

          <!-- Items (compact) -->
          <div class="space-y-1">
            <div
              v-for="item in o.items"
              :key="item.dish_slug + item.note"
              class="flex items-center justify-between gap-2 rounded-xl border border-slate-800/70 bg-slate-950/30 py-1.5 pe-3 ps-3 text-xs"
            >
              <span class="font-semibold text-slate-100">{{ item.qty }}× {{ item.dish_name }}</span>
              <span class="tabular-nums text-slate-200">{{ formatCurrency(item.subtotal, o.currency) }}</span>
            </div>
          </div>

          <!-- Customer note (shown when present) -->
          <p v-if="o.customer_note" class="rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-slate-300">
            <span class="font-semibold text-slate-400">{{ t("ownerOrders.note") }}:</span> {{ o.customer_note }}
          </p>

          <!-- Print button for historical orders -->
          <div class="flex gap-2">
            <button class="ui-btn-outline ui-press inline-flex items-center gap-1.5 px-3 py-1.5 text-xs" @click="printTicket(o)">
              <span aria-hidden="true">🖨</span> {{ t("ownerOrders.printTicket") }}
            </button>
          </div>
        </article>
      </div>

      <!-- Load more -->
      <div class="py-2 text-center">
        <button
          v-if="order.historyHasMore"
          type="button"
          class="ui-btn-outline ui-press inline-flex items-center gap-2 px-5 py-2 text-sm"
          :disabled="order.historyLoading"
          :aria-busy="order.historyLoading"
          @click="loadMoreHistory"
        >
          <span v-if="order.historyLoading" class="inline-block h-3.5 w-3.5 animate-spin rounded-full border border-current border-t-transparent" aria-hidden="true" />
          {{ order.historyLoading ? t("ownerOrders.loadingMore") : t("ownerOrders.loadMore") }}
        </button>
        <p v-else-if="order.historyOrders.length && !order.historyLoading" class="text-xs text-slate-600">{{ t("ownerOrders.noMoreOrders") }}</p>
      </div>
    </template>

    <!-- ── ACTIVE TAB: order list ───────────────────────────────────────── -->
    <!-- Bulk print kitchen tickets — shown when filtering pending/confirmed with ≥2 orders -->
    <div
      v-if="activeTab === 'active' && ['pending','confirmed'].includes(activeStatus) && filteredOrders.length >= 2"
      class="flex justify-end"
    >
      <button
        class="ui-btn-outline ui-press inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
        @click="printBulkTickets(filteredOrders)"
      >
        <span aria-hidden="true">🖨</span> {{ t('ownerOrders.printAllTickets', { count: filteredOrders.length }) }}
      </button>
    </div>

    <!-- Bulk mark-all-ready — shown only when filtering by 'preparing' with ≥2 visible orders -->
    <div
      v-if="activeTab === 'active' && activeStatus === 'preparing' && filteredOrders.length >= 2"
      class="flex justify-end"
    >
      <button
        class="ui-btn-primary ui-press px-3 py-1.5 text-xs"
        :disabled="order.updatingOrderId != null"
        @click="bulkMarkPreparingReady"
      >
        {{ t('ownerOrders.markAllReady', { count: filteredOrders.length }) }}
      </button>
    </div>

    <!-- Order list (shown when active tab and there are filtered orders) -->
    <div v-if="activeTab === 'active' && filteredOrders.length" class="space-y-2.5">
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
              <button
                class="ui-press -ms-1 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-slate-500 hover:text-slate-300 focus-visible:outline-none"
                :aria-label="t('ownerOrders.copyOrderNumber')"
                @click.stop="copyOrderNumber(o)"
              >
                <svg v-if="copiedOrderId === o.id" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3 text-emerald-400"><path d="M3 8l3.5 3.5L13 4.5"/></svg>
                <svg v-else aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3"><rect x="5" y="5" width="9" height="9" rx="1.5"/><path d="M3 11V3a1.5 1.5 0 0 1 1.5-1.5H12"/></svg>
              </button>
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
              <!-- Due-soon badge — near/past fire time while still in a live status -->
              <span
                v-if="o.scheduled_for && o.status !== 'completed' && o.status !== 'cancelled' && orderIsDueSoon(o)"
                class="rounded-full bg-amber-500/20 border border-amber-500/40 px-2 py-0.5 text-[10px] font-bold text-amber-300"
              >
                <span aria-hidden="true">⏱</span> {{ t('ownerOrders.dueSoonBadge') }}
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
              <!-- Awaiting driver badge — ready delivery, no driver assigned yet -->
              <span
                v-if="o.status === 'ready' && o.fulfillment_type === 'delivery' && (!o.delivery_job || o.delivery_job.status === 'searching')"
                class="rounded-full border border-amber-500/40 bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300"
              >
                <span aria-hidden="true">🛵</span> {{ t('ownerOrders.awaitingDriver') }}
              </span>
              <!-- Age warning badge (pending / confirmed) -->
              <span
                v-if="orderAgeMin(o) >= 1 && ['pending', 'confirmed'].includes(o.status)"
                class="rounded-full px-2 py-0.5 text-[10px] font-bold"
                :class="orderAgeMin(o) >= 20
                  ? ['bg-red-500/25 text-red-300', 'animate-pulse']
                  : orderAgeMin(o) >= 10
                    ? 'bg-red-500/25 text-red-300'
                    : orderAgeMin(o) >= 5
                      ? 'bg-amber-500/25 text-amber-300'
                      : 'bg-slate-700/60 text-slate-300'"
              >
                <span aria-hidden="true">⏱</span> {{ orderAgeMin(o) }}m
              </span>
              <!-- Kitchen timer badge (preparing) -->
              <span
                v-if="o.status === 'preparing' && orderAgeMin(o) >= 1"
                class="rounded-full px-2 py-0.5 text-[10px] font-bold"
                :class="orderAgeMin(o) >= 35
                  ? ['bg-red-500/25 text-red-300', 'animate-pulse']
                  : orderAgeMin(o) >= 25
                    ? 'bg-red-500/25 text-red-300'
                    : orderAgeMin(o) >= 15
                      ? 'bg-amber-500/25 text-amber-300'
                      : 'bg-orange-500/20 text-orange-300'"
                :title="t('ownerOrders.preparingTimerTitle')"
              >
                🍳 {{ orderAgeMin(o) }}m
              </span>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <p class="text-xs font-medium tabular-nums text-slate-400">{{ formatTime(o.created_at) }}</p>
              <!-- Customer note indicator — visible on collapsed card so owner knows to check -->
              <span
                v-if="o.customer_note"
                class="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-300"
                :title="o.customer_note"
              >
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="h-2.5 w-2.5 shrink-0" aria-hidden="true"><path d="M1 9.5V11h1.5l4.7-4.7-1.5-1.5L1 9.5z"/><path d="M10.1 2.4a.95.95 0 0 0-1.5 0L7.5 3.5l1.5 1.5L10.1 4a.95.95 0 0 0 0-1.5z"/></svg>
                {{ t('ownerOrders.hasNote') }}
              </span>
            </div>
            <!-- Customer name (delivery/pickup only — dine-in already shows table info) -->
            <p
              v-if="o.customer_name && o.fulfillment_type !== 'table'"
              class="flex items-center gap-1.5 text-xs text-slate-400"
            >
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" class="h-3 w-3 shrink-0 text-slate-500" aria-hidden="true"><circle cx="6" cy="4" r="2.5"/><path d="M1.5 11c0-2.485 2.015-4.5 4.5-4.5s4.5 2.015 4.5 4.5"/></svg>
              <span class="font-medium text-slate-200">{{ o.customer_name }}</span>
            </p>
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
                <span
                  v-else-if="(item.course ?? 0) > 0"
                  class="shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold leading-none"
                  :class="item.course > (o.fired_course ?? 1)
                    ? 'border-amber-500/30 bg-amber-500/10 text-amber-400'
                    : 'border-slate-600/50 bg-slate-700/30 text-slate-400'"
                  style="text-decoration:none"
                >{{ item.course > (o.fired_course ?? 1) ? t("waiterPage.heldChip") : t("waiterPage.courseChip", { n: item.course }) }}</span>
              </p>
              <p v-if="item.options?.length" class="text-slate-400">
                {{ t("ownerOrders.options") }}: {{ item.options.map(o => o.name).join(", ") }}
              </p>
              <p v-if="item.note" class="italic text-slate-400">{{ item.note }}</p>
              <!-- Contract F: void reason surfaced -->
              <p v-if="item.is_voided && item.void_reason" class="text-[10px] text-red-400/80 italic">{{ t("ownerOrders.voidReason") }}: {{ item.void_reason }}</p>
              <!-- Combo sub-lines -->
              <ul v-if="item.combo_components?.length" class="mt-0.5 space-y-0">
                <li
                  v-for="comp in item.combo_components"
                  :key="comp.dish_id"
                  class="flex items-center gap-1.5 text-[11px] text-slate-500"
                >
                  <span aria-hidden="true">↳</span>
                  <span>{{ comp.name }} ×{{ comp.qty * item.qty }}</span>
                </li>
              </ul>
            </div>
            <p class="shrink-0 font-semibold tabular-nums" :class="item.is_voided ? 'line-through text-slate-500' : 'text-slate-200'">{{ formatCurrency(item.subtotal, o.currency) }}</p>
          </div>
          <p v-if="o.customer_note" class="rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-slate-300">
            <span class="font-semibold text-slate-400">{{ t("ownerOrders.note") }}:</span> {{ o.customer_note }}
          </p>
        </div>

        <!-- Contract F: Payment ledger rows with correction affordance -->
        <!-- Payments are lazy-loaded on demand (list endpoint returns totals only) -->
        <div v-if="o.payment_status === 'paid' || paymentsMap[o.id]" class="space-y-1">
          <div class="flex items-center gap-2">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t("ownerOrders.paymentsLedger") }}</p>
            <button
              v-if="!paymentsMap[o.id]"
              type="button"
              class="text-[10px] text-slate-500 hover:text-slate-300 underline underline-offset-2 transition"
              @click="loadPayments(o.id)"
            >{{ t("ownerOrders.loadPayments") }}</button>
          </div>
          <div
            v-for="p in (paymentsMap[o.id] || [])"
            :key="p.id"
            class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-800/60 bg-slate-950/30 px-3 py-1.5 text-xs"
          >
            <div class="flex items-center gap-2 min-w-0">
              <span
                class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="p.method === 'cash' ? 'bg-amber-500/15 text-amber-300' : 'bg-sky-500/15 text-sky-300'"
              >
                {{ p.method === 'cash' ? t("ownerOrders.methodCash") : t("ownerOrders.methodWallet") }}
              </span>
              <span class="font-semibold tabular-nums text-slate-200">{{ formatCurrency(p.amount, o.currency) }}</span>
              <span v-if="p.recorded_by_name" class="text-slate-500">{{ t("ownerOrders.recordedBy") }}: {{ p.recorded_by_name }}</span>
              <!-- Corrected indicator -->
              <span v-if="p.original_method" class="text-[10px] text-amber-400 italic">
                {{ t("ownerOrders.corrected", { from: p.original_method, by: p.corrected_by_name || t("ownerOrders.unknown") }) }}
              </span>
            </div>
            <!-- Correct method button -->
            <button
              type="button"
              class="shrink-0 rounded-full border border-slate-700/60 px-2 py-0.5 text-[10px] font-medium text-slate-400 hover:border-slate-500 hover:text-slate-200 transition ui-press focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-500"
              :disabled="correctingPaymentId === p.id"
              :aria-label="t('ownerOrders.correctMethod')"
              @click="openCorrectMethod(o, p)"
            >
              {{ correctingPaymentId === p.id ? t("common.saving") : t("ownerOrders.correctMethod") }}
            </button>
          </div>
        </div>

        <!-- Correct-method inline panel -->
        <div v-if="correctMethodPanel && correctMethodPanel.orderId === o.id" class="rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2.5 space-y-2 text-xs">
          <p class="font-semibold text-amber-200">{{ t("ownerOrders.correctMethodTitle") }}</p>
          <p class="text-slate-400">{{ t("ownerOrders.correctMethodHint") }}</p>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="method in ['cash', 'wallet']"
              :key="method"
              type="button"
              class="rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber-400/60"
              :class="correctMethodPanel.newMethod === method
                ? 'border-amber-400/60 bg-amber-500/20 text-amber-200'
                : 'border-slate-700 text-slate-300 hover:border-slate-500'"
              @click="correctMethodPanel.newMethod = method"
            >
              {{ method === 'cash' ? t("ownerOrders.methodCash") : t("ownerOrders.methodWallet") }}
            </button>
          </div>
          <div class="flex gap-2">
            <button
              type="button"
              class="ui-btn-primary px-3 py-1.5 text-xs"
              :disabled="correctingPaymentId === correctMethodPanel.paymentId || !correctMethodPanel.newMethod"
              @click="submitCorrectMethod"
            >
              {{ correctingPaymentId === correctMethodPanel.paymentId ? t("common.saving") : t("ownerOrders.correctMethodConfirm") }}
            </button>
            <button
              type="button"
              class="ui-btn-outline px-3 py-1.5 text-xs"
              @click="correctMethodPanel = null"
            >{{ t("common.cancel") }}</button>
          </div>
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

        <!-- Primary action row -->
        <div class="flex flex-wrap items-center gap-2 pt-0.5">
          <template v-if="o.status === 'scheduled'">
            <button class="ui-btn-primary ui-press px-4 py-2 text-xs font-semibold" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'pending')">
              {{ t("ownerOrders.releaseNow") }}
            </button>
          </template>
          <template v-else-if="o.status === 'pending'">
            <button class="ui-btn-primary ui-press px-4 py-2 text-xs font-semibold" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'confirmed')">
              {{ t("ownerOrders.confirm") }}
            </button>
          </template>
          <template v-else-if="o.status === 'confirmed'">
            <button class="ui-btn-primary ui-press px-4 py-2 text-xs font-semibold" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'preparing')">
              {{ t("ownerOrders.startPreparing") }}
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
            @click="cashierOrder = o"
          >
            <span v-if="settlingOrderId === o.id" class="inline-block animate-spin h-3 w-3 border border-emerald-300 border-t-transparent rounded-full" aria-hidden="true" />
            <span v-else aria-hidden="true">💵</span>
            {{ settlingOrderId === o.id ? t("common.saving") : (o.status === 'ready' ? t("ownerOrders.settleAndClose") : t("ownerOrders.markPaid")) }}
          </button>
        </div>

        <!-- Destructive actions row — separated visually to prevent fat-finger cancels -->
        <div
          v-if="['scheduled','pending','confirmed'].includes(o.status)"
          class="flex items-center gap-2 border-t border-slate-700/40 pt-2 mt-1"
        >
          <button
            class="ui-btn-outline ui-press border-red-500/30 px-3 py-1.5 text-xs text-red-400 hover:border-red-500/60 hover:text-red-300"
            :disabled="order.updatingOrderId === o.id"
            @click="updateStatus(o, 'cancelled')"
          >
            {{ t("ownerOrders.cancel") }}
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

    <!-- ── FILTER SHEET — bottom drawer for fulfillment / payment / date filters ── -->
    <Teleport to="body">
      <Transition name="ui-fade">
        <div
          v-if="filterSheetOpen"
          class="fixed inset-0 z-[2200] flex items-end justify-center"
          role="dialog"
          aria-modal="true"
          :aria-label="t('ownerOrders.filterSheetTitle')"
          @keydown.esc="filterSheetOpen = false"
        >
          <!-- Backdrop -->
          <div class="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" @click="filterSheetOpen = false" />
          <!-- Panel -->
          <div class="relative z-10 w-full max-w-lg rounded-t-2xl bg-slate-900 border border-slate-700/60 shadow-2xl flex flex-col max-h-[80dvh]">
            <!-- Handle + header -->
            <div class="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 shrink-0">
              <h2 class="text-base font-bold text-white">{{ t('ownerOrders.filterSheetTitle') }}</h2>
              <div class="flex items-center gap-2">
                <button
                  v-if="activeFilterCount > 0"
                  class="ui-press rounded-full border border-slate-700 px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200"
                  @click="activeDateFilter = 'all'; activeFulfillmentType = ''; customDateFrom = ''; customDateTo = ''; activePaymentStatus = ''"
                >{{ t('ownerOrders.clearFilters') }}</button>
                <button
                  class="ui-press flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-200"
                  :aria-label="t('common.close')"
                  @click="filterSheetOpen = false"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5" aria-hidden="true">
                    <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z"/>
                  </svg>
                </button>
              </div>
            </div>
            <!-- Filter content -->
            <div class="overflow-y-auto flex-1 px-4 py-4 space-y-5">
              <!-- Date filter -->
              <div class="space-y-2">
                <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('ownerOrders.dateAll') }}</p>
                <div class="flex flex-wrap gap-1.5">
                  <button
                    v-for="d in dateTabs"
                    :key="d.value"
                    type="button"
                    :aria-pressed="activeDateFilter === d.value"
                    class="ui-state-chip ui-press"
                    :data-active="activeDateFilter === d.value || undefined"
                    @click="activeDateFilter = d.value"
                  >{{ d.label }}</button>
                </div>
                <!-- Custom date-range inputs -->
                <div v-if="activeDateFilter === 'custom'" class="flex flex-wrap items-center gap-1.5 pt-1">
                  <label class="text-xs text-slate-400" for="fs-date-from">{{ t('ownerOrders.dateFrom') }}</label>
                  <input id="fs-date-from" v-model="customDateFrom" type="date" class="ui-input py-1 text-xs" :max="customDateTo || undefined" />
                  <label class="text-xs text-slate-400" for="fs-date-to">{{ t('ownerOrders.dateTo') }}</label>
                  <input id="fs-date-to" v-model="customDateTo" type="date" class="ui-input py-1 text-xs" :min="customDateFrom || undefined" />
                </div>
              </div>

              <!-- Fulfillment-type filter (only when 2+ types in the order list) -->
              <div v-if="fulfillmentTabs.length" class="space-y-2">
                <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('ownerOrders.fulfillmentFilter') }}</p>
                <div class="flex flex-wrap gap-1.5">
                  <button
                    v-for="tab in fulfillmentTabs"
                    :key="tab.value"
                    type="button"
                    :aria-pressed="activeFulfillmentType === tab.value"
                    class="ui-state-chip ui-press"
                    :data-active="activeFulfillmentType === tab.value || undefined"
                    @click="activeFulfillmentType = tab.value"
                  >{{ tab.label }}</button>
                </div>
              </div>

              <!-- Payment status filter -->
              <div class="space-y-2">
                <p class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{{ t('ownerOrders.paymentFilter') }}</p>
                <div class="flex flex-wrap gap-1.5">
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
              </div>
            </div>
            <!-- Apply / close -->
            <div class="border-t border-slate-800 px-4 py-3 shrink-0">
              <button
                class="ui-btn-primary w-full py-2.5 text-sm font-semibold"
                @click="filterSheetOpen = false"
              >{{ t('common.close') }}</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ── 86 BOARD MODAL — dish availability (opens from floating button) ───── -->
    <Teleport to="body">
      <Transition name="ui-fade">
        <div
          v-if="orders86BoardOpen"
          class="fixed inset-0 z-[2200] flex items-end justify-center sm:items-center"
          role="dialog"
          aria-modal="true"
          :aria-label="t('kitchen.eightySixTitle')"
          @keydown.esc="orders86BoardOpen = false"
        >
          <!-- Backdrop -->
          <div class="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" @click="orders86BoardOpen = false" />
          <!-- Panel -->
          <div class="relative z-10 w-full max-w-md rounded-t-2xl sm:rounded-2xl bg-slate-900 border border-slate-700/60 shadow-2xl flex flex-col max-h-[85dvh]">
            <!-- Header -->
            <div class="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 shrink-0">
              <h2 class="text-base font-bold text-white">
                {{ t('kitchen.eightySixTitle') }}
                <span v-if="orders86SoldOutCount > 0" class="ms-2 rounded-full border border-red-500/40 bg-red-500/15 px-2 py-0.5 text-xs font-semibold text-red-300 tabular-nums">{{ orders86SoldOutCount }}</span>
              </h2>
              <button
                class="ui-press flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-200"
                :aria-label="t('common.close')"
                @click="orders86BoardOpen = false"
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
                  v-model.trim="orders86Search"
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
                  v-if="orders86Dishes.some(d => d.is_available)"
                  class="ui-press rounded-full border border-red-500/40 px-2.5 py-1 text-[10px] font-semibold text-red-300 hover:bg-red-500/10 disabled:opacity-50"
                  :disabled="orders86MarkingUnavailable"
                  @click="orders86MarkAllUnavailable"
                >{{ orders86MarkingUnavailable ? t('common.loading') : t('kitchen.markAllUnavailable') }}</button>
                <span v-else />
                <button
                  v-if="orders86SoldOutCount > 0"
                  class="ui-press rounded-full border border-emerald-500/40 px-2.5 py-1 text-[10px] font-semibold text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-50"
                  :disabled="orders86Resetting"
                  @click="orders86ResetAll"
                >{{ orders86Resetting ? t('common.loading') : t('ownerHome.resetAllAvailable') }}</button>
              </div>
            </div>
            <!-- List -->
            <div class="overflow-y-auto flex-1 px-4 pb-4">
              <div v-if="orders86Fetching" class="space-y-2 pt-1">
                <div v-for="i in 6" :key="i" class="flex animate-pulse items-center justify-between gap-2 rounded-xl px-2 py-3">
                  <div class="h-4 w-36 rounded bg-slate-700/60" />
                  <div class="h-9 w-24 rounded-xl bg-slate-700/40" />
                </div>
              </div>
              <div v-else-if="!orders86Filtered.length" class="py-8 text-center text-sm text-slate-500">{{ t('kitchen.eightySixEmpty') }}</div>
              <ul v-else role="list" class="list-none space-y-1 pt-1">
                <li
                  v-for="dish in orders86Filtered"
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
                    :disabled="orders86TogglingId === dish.id"
                    :aria-checked="dish.is_available"
                    :aria-busy="orders86TogglingId === dish.id"
                    :aria-label="`${dish.name} — ${dish.is_available ? t('kitchen.eightySixAvailable') : t('kitchen.eightySixSoldOut')}`"
                    @click="orders86Toggle(dish)"
                  >
                    {{ orders86TogglingId === dish.id ? '…' : (dish.is_available ? t('kitchen.eightySixAvailable') : t('kitchen.eightySixSoldOut')) }}
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ── FLOATING 86 BOARD BUTTON ── -->
    <Teleport to="body">
      <Transition name="ui-fade">
        <button
          v-if="!orders86BoardOpen && !filterSheetOpen && !trackModal.open"
          type="button"
          class="ui-press fixed bottom-6 end-4 z-[2000] inline-flex items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-bold shadow-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
          :class="orders86SoldOutCount > 0
            ? 'border-red-500/50 bg-red-950 text-red-300 shadow-red-900/40'
            : 'border-slate-700 bg-slate-900 text-slate-300 shadow-slate-900/60'"
          :aria-label="t('ownerOrders.eightySixBoardBtn')"
          @click="open86BoardFromOrders"
        >
          <span aria-hidden="true" class="text-base font-black leading-none">86</span>
          {{ t('ownerOrders.eightySixBoardBtn') }}
          <span
            v-if="orders86SoldOutCount > 0"
            class="inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-red-500/20 px-1 py-0.5 text-[10px] font-bold tabular-nums leading-none text-red-300"
          >{{ orders86SoldOutCount }}</span>
        </button>
      </Transition>
    </Teleport>

    <!-- Cashier-mode big-total modal — tap settle button to open -->
    <Teleport to="body">
      <Transition name="ui-fade">
        <div
          v-if="cashierOrder"
          class="fixed inset-0 z-[3500] flex items-end justify-center sm:items-center"
          role="dialog"
          :aria-label="t('ownerOrders.cashierModalTitle')"
          @click.self="cashierOrder = null"
        >
          <div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" aria-hidden="true" @click="cashierOrder = null" />
          <div class="relative z-10 w-full max-w-sm rounded-t-3xl border border-slate-700/60 bg-slate-900 px-6 pb-8 pt-6 text-center shadow-2xl sm:rounded-2xl">
            <p class="text-sm font-medium uppercase tracking-widest text-slate-400">{{ t('ownerOrders.cashierModalTitle') }}</p>
            <p class="mt-2 font-mono text-6xl font-extrabold tabular-nums text-emerald-300 sm:text-7xl">
              {{ formatCurrency(cashierOrder.total, cashierOrder.currency) }}
            </p>
            <p v-if="cashierOrder.table_label" class="mt-2 text-sm text-slate-400">
              {{ t('ownerOrders.fulfillmentTable', { table: cashierOrder.table_label }) }}
            </p>
            <p class="mt-1 text-sm text-slate-500">#{{ cashierOrder.order_number }}</p>
            <div class="mt-6 flex gap-3">
              <button
                type="button"
                class="ui-btn-outline ui-press flex-1 py-3 text-sm"
                @click="cashierOrder = null"
              >{{ t('common.cancel') }}</button>
              <button
                type="button"
                class="ui-press flex-[2] rounded-xl bg-emerald-600 py-3 text-sm font-semibold text-white shadow-md hover:bg-emerald-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                :disabled="settlingOrderId === cashierOrder.id"
                @click="settleOrder(cashierOrder); cashierOrder = null"
              >
                <span v-if="settlingOrderId === cashierOrder?.id" class="inline-block animate-spin h-4 w-4 border-2 border-white/60 border-t-white rounded-full mr-2 align-middle" aria-hidden="true" />
                {{ cashierOrder.status === 'ready' ? t('ownerOrders.settleAndClose') : t('ownerOrders.markPaid') }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import DeliveryTracker from "../components/DeliveryTracker.vue";
import { useI18n } from "../composables/useI18n";
import { useConfirmModal } from "../composables/useConfirmModal";
import { useNowTicker } from "../composables/useNowTicker";
import { upcomingOrders, minutesUntilScheduled, isDueSoon } from "../lib/ownerLiveFocus";
import api from "../lib/api";
import { useOrderStore } from "../stores/order";
import { useToastStore } from "../stores/toast";
import { useTenantStore } from "../stores/tenant";
import { usePrintTicket } from "../composables/usePrintTicket";
import { chipClass as _statusChipClass } from "../lib/orderStatusMeta";
import { isAutoAcceptOn } from "../lib/orderHandling";
import { bustCache } from "../lib/staleCache";

// Explicit name so <KeepAlive :exclude> in OwnerLayout reliably skips this page
// (live orders — polls and must mount & unmount normally).
defineOptions({ name: "OwnerOrders" });

const { t, itemCountLabel, formatNumber, formatDateTime, currentLocale } = useI18n();
const order = useOrderStore();
const toast = useToastStore();
const tenant = useTenantStore();
const { confirm } = useConfirmModal();
const route = useRoute();

// ── Auto-accept indicator ───────────────────────────────────────────────────
// When the owner has opted into auto-accept, incoming orders are confirmed
// without a tap. Surface a subtle header chip so staff know taps aren't
// required. Defaults to false (no chip) for tenants who haven't opted in.
const autoAcceptOn = computed(
  () => isAutoAcceptOn(tenant.resolvedMeta?.profile)
);

// ── Menu URL (for empty-state CTA) ──────────────────────────────────────────
const menuUrl = computed(() =>
  typeof window !== "undefined" ? `${window.location.origin}/menu` : "/menu"
);
const copyMenuUrl = async () => {
  try {
    await navigator.clipboard.writeText(menuUrl.value);
    toast.show(t("ownerLaunchSuccess.menuUrlCopied"), "success");
  } catch {
    toast.show(t("ownerTables.copyFailed"), "error");
  }
};

// ── Filter sheet (bottom drawer for fulfillment / payment / date filters) ──────
const filterSheetOpen = ref(false);

// Count of non-default filter values so the trigger chip shows a badge.
const activeFilterCount = computed(() => {
  let n = 0;
  if (activeDateFilter.value !== "all") n++;
  if (activeFulfillmentType.value) n++;
  if (activePaymentStatus.value) n++;
  return n;
});

// ── 86 Board (dish availability) modal — opened from floating button ───────────
const orders86BoardOpen = ref(false);
const orders86Dishes = ref([]);
const orders86Fetching = ref(false);
const orders86Search = ref("");
const orders86TogglingId = ref(null);
const orders86Resetting = ref(false);
const orders86MarkingUnavailable = ref(false);

const orders86SoldOutCount = computed(
  () => orders86Dishes.value.filter((d) => d.is_published && !d.is_available).length
);

const orders86Filtered = computed(() => {
  const q = orders86Search.value.toLowerCase();
  const list = [...orders86Dishes.value]
    .filter((d) => d.is_published)
    .sort((a, b) => {
      if (!a.is_available && b.is_available) return -1;
      if (a.is_available && !b.is_available) return 1;
      return 0;
    });
  if (!q) return list;
  return list.filter(
    (d) =>
      (d.name || "").toLowerCase().includes(q) ||
      (d.category_name || "").toLowerCase().includes(q)
  );
});

const orders86Fetch = async () => {
  if (orders86Fetching.value) return;
  orders86Fetching.value = true;
  try {
    const { data } = await api.get("/dishes/", { timeout: 6000 });
    orders86Dishes.value = Array.isArray(data) ? data : [];
  } catch {
    toast.show(t("ownerHome.noDishesLoaded"), "error");
  } finally {
    orders86Fetching.value = false;
  }
};

const orders86Toggle = async (dish) => {
  if (orders86TogglingId.value === dish.id) return;
  orders86TogglingId.value = dish.id;
  const newVal = !dish.is_available;
  try {
    await api.patch(`/dishes/${dish.id}/`, { is_available: newVal });
    dish.is_available = newVal;
    bustCache("menu.categories");
  } catch (err) {
    const status = err?.response?.status;
    toast.show(status === 403 ? t("kitchen.eightySixToggleFailed403") : t("kitchen.eightySixToggleFailed"), "error");
  } finally {
    orders86TogglingId.value = null;
  }
};

const orders86ResetAll = async () => {
  if (orders86Resetting.value) return;
  orders86Resetting.value = true;
  try {
    const { data } = await api.post("/owner/dishes/reset-availability/");
    orders86Dishes.value.forEach((d) => {
      if (d.is_published && !d.is_available) d.is_available = true;
      if (d.stock_qty === 0) d.stock_qty = null;
    });
    bustCache("menu.categories");
    const count = data?.restored ?? 0;
    toast.show(
      count > 0 ? t("ownerHome.resetAvailabilityDone", { count }) : t("ownerHome.resetAvailabilityNone"),
      "success"
    );
  } catch {
    toast.show(t("ownerHome.resetAvailabilityFailed"), "error");
  } finally {
    orders86Resetting.value = false;
  }
};

const orders86MarkAllUnavailable = async () => {
  if (orders86MarkingUnavailable.value) return;
  orders86MarkingUnavailable.value = true;
  try {
    const { data } = await api.post("/owner/dishes/mark-all-unavailable/");
    orders86Dishes.value.forEach((d) => { if (d.is_available) d.is_available = false; });
    bustCache("menu.categories");
    const count = data?.marked ?? 0;
    toast.show(t("kitchen.markAllUnavailableDone", { count }), "success");
  } catch {
    toast.show(t("kitchen.markAllUnavailableFailed"), "error");
  } finally {
    orders86MarkingUnavailable.value = false;
  }
};

// Open the 86 board; auto-open when sold-out items exist on first load.
const open86BoardFromOrders = () => {
  orders86BoardOpen.value = true;
  orders86Search.value = "";
  orders86Fetch();
};

// Seed the sold-out count once the order list loads (for the floating button badge).
// Uses a lightweight check: fetch dish list once on mount, then rely on toggle state.
const _orders86Seeded = ref(false);
const seed86Count = async () => {
  if (_orders86Seeded.value || orders86Dishes.value.length) return;
  _orders86Seeded.value = true;
  try {
    const { data } = await api.get("/dishes/", { timeout: 6000 });
    orders86Dishes.value = Array.isArray(data) ? data : [];
    // Auto-open panel if there are sold-out items (spec: default open when soldOutCount>0)
    if (orders86SoldOutCount.value > 0) {
      orders86BoardOpen.value = true;
    }
  } catch { /* non-critical — badge stays at 0 */ }
};

// ── Tab: "active" (hot poll) | "history" (paginated terminal orders) ──────────
const activeTab = ref("active");

const historyFrom = ref("");
const historyTo = ref("");

const historyPeriodRevenue = computed(() => {
  const orders = order.historyOrders;
  if (!orders.length) return '';
  const currency = orders[0]?.currency ?? 'USD';
  const total = orders.reduce((sum, o) => sum + (parseFloat(o.total) || 0), 0);
  return formatCurrency(total, currency);
});

const switchToHistory = () => {
  activeTab.value = "history";
  // Load first page if not yet loaded or previously errored
  if (!order.historyOrders.length && !order.historyLoading) {
    order.fetchHistory({ reset: true, from: historyFrom.value, to: historyTo.value });
  }
};

const reloadHistory = () => {
  order.fetchHistory({ reset: true, from: historyFrom.value, to: historyTo.value });
};

const loadMoreHistory = () => {
  order.fetchHistory({ reset: false, from: historyFrom.value, to: historyTo.value });
};

const activeStatus = ref("");
const activeDateFilter = ref("all");
const customDateFrom = ref("");
const customDateTo = ref("");
const searchQuery = ref("");
const activeFulfillmentType = ref("");
const activePaymentStatus = ref(""); // "" = all, "unpaid", "paid"
const exporting = ref(false);
const confirmingAll = ref(false);
const cashierOrder = ref(null); // drives the cashier-mode big-total modal
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
  const overdueCount = order.orders.filter(
    (o) => ['pending','confirmed'].includes(o.status) && orderAgeMin(o) >= 10,
  ).length;
  return [
    { value: "", label: t("ownerOrders.allStatuses"), count: 0 },
    ...(overdueCount > 0 ? [{ value: "_overdue", label: t("ownerOrders.statusOverdue"), count: overdueCount, urgent: true }] : []),
    { value: "scheduled", label: t("ownerOrders.statusScheduled"), count: counts.scheduled || 0 },
    { value: "pending", label: t("ownerOrders.statusPending"), count: counts.pending || 0 },
    { value: "confirmed", label: t("ownerOrders.statusConfirmed"), count: counts.confirmed || 0 },
    { value: "preparing", label: t("ownerOrders.statusPreparing"), count: counts.preparing || 0 },
    { value: "ready", label: t("ownerOrders.statusReady"), count: counts.ready || 0 },
    { value: "out_for_delivery", label: t("ownerOrders.outForDelivery"), count: counts.out_for_delivery || 0 },
  ];
});

// ── Today's stats ─────────────────────────────────────────────────────────────
// Use tenant timezone so "today" is bucketed in the restaurant's local time,
// not the owner's device timezone (Contract E: timezone "today" fix).
const _tenantDateStr = (isoStr) => {
  const tz = tenant.resolvedMeta?.profile?.timezone;
  if (!tz) return new Date(isoStr).toDateString(); // fallback to device tz
  try {
    return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(isoStr));
  } catch {
    return new Date(isoStr).toDateString();
  }
};

const todayStats = computed(() => {
  const tz = tenant.resolvedMeta?.profile?.timezone;
  const todayStr = tz
    ? new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date())
    : new Date().toDateString();
  const todayOrders = order.orders.filter((o) => _tenantDateStr(o.created_at) === todayStr);
  const pending = todayOrders.filter((o) => o.status === "pending").length;
  const revenue = todayOrders.reduce((sum, o) => sum + (Number(o.total) || 0), 0);
  const currency = todayOrders.find((o) => o.currency)?.currency || "MAD";
  return { count: todayOrders.length, revenue, pending, currency };
});

// ── Filtered + sorted orders ──────────────────────────────────────────────────
const STATUS_SORT = { scheduled: -1, pending: 0, confirmed: 1, preparing: 2, ready: 3, out_for_delivery: 4, completed: 5, cancelled: 6 };

const filteredOrders = computed(() => {
  const tz = tenant.resolvedMeta?.profile?.timezone;
  const _fmt = (d) => {
    if (!tz) return d.toDateString();
    try {
      return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
    } catch { return d.toDateString(); }
  };
  const now = new Date();
  const todayStr = _fmt(now);
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const yesterdayStr = _fmt(yesterday);
  const weekAgo = new Date(now);
  weekAgo.setDate(now.getDate() - 6);
  weekAgo.setHours(0, 0, 0, 0);

  const q = searchQuery.value.toLowerCase();

  let base = order.orders.filter((o) => {
    // Status filter — '_overdue' is a synthetic filter: pending/confirmed orders aged ≥ 10 min
    if (activeStatus.value === '_overdue') {
      if (!['pending','confirmed'].includes(o.status)) return false;
      if (orderAgeMin(o) < 10) return false;
    } else if (activeStatus.value && o.status !== activeStatus.value) return false;

    // Fulfillment-type filter
    if (activeFulfillmentType.value && o.fulfillment_type !== activeFulfillmentType.value) return false;

    // Payment status filter
    if (activePaymentStatus.value && o.payment_status !== activePaymentStatus.value) return false;

    // Date filter
    if (activeDateFilter.value !== "all") {
      const d = new Date(o.created_at);
      if (activeDateFilter.value === "today" && _fmt(d) !== todayStr) return false;
      if (activeDateFilter.value === "yesterday" && _fmt(d) !== yesterdayStr) return false;
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
const copiedOrderId = ref(null);
let _orderCopyTimer = null;
const copyOrderNumber = async (o) => {
  try {
    await navigator.clipboard.writeText(String(o.order_number));
    copiedOrderId.value = o.id;
    if (_orderCopyTimer) clearTimeout(_orderCopyTimer);
    _orderCopyTimer = setTimeout(() => { copiedOrderId.value = null; _orderCopyTimer = null; }, 1500);
  } catch { /* clipboard not available */ }
};

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
// statusClass for the main order card chip — uses STATUS_META (task 1 full swap).
const statusClass = (s) => _statusChipClass(s);

const formatScheduledFor = (iso) => {
  if (!iso) return "";
  try {
    return formatDateTime(iso, { weekday: "short", dateStyle: undefined, timeStyle: undefined, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "" : d.toLocaleString();
  }
};

// ── Upcoming / advance (scheduled) orders ─────────────────────────────────────
// A "due soon" strip surfaces scheduled or near-due pre-orders proactively so a
// pre-ordered lunch isn't invisible until it's late. Recomputes off the ticker.
const { now: tickerNow } = useNowTicker();
const upcoming = computed(() => upcomingOrders(order.orders, tickerNow.value));
const upcomingMinutes = (o) => minutesUntilScheduled(o, tickerNow.value);
// True when an order carries a scheduled_for that is within (or past) its window.
const orderIsDueSoon = (o) => isDueSoon(o, tickerNow.value);

const releaseNow = async (o) => updateStatus(o, "pending");

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
// tickNow updates every 30 s so age badges stay live between order-store refreshes.
const tickNow = ref(Date.now());
let _ageTick = null;
onMounted(() => { _ageTick = setInterval(() => { tickNow.value = Date.now(); }, 30000); });
onUnmounted(() => clearInterval(_ageTick));
const orderAgeMin = (o) => Math.floor((tickNow.value - new Date(o.created_at)) / 60000);

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
const bulkMarkPreparingReady = async () => {
  const preparing = filteredOrders.value.filter((o) => o.status === 'preparing');
  if (preparing.length < 2) return;
  const ok = await confirm({
    title: t('ownerOrders.bulkReadyConfirmTitle', { count: preparing.length }),
    body: t('ownerOrders.bulkReadyConfirmBody'),
    confirmLabel: t('ownerOrders.markReady'),
  });
  if (!ok) return;
  const results = await Promise.allSettled(
    preparing.map((o) => order.updateOrderStatus(o.id, { status: 'ready' })),
  );
  const succeeded = results.filter((r) => r.status === 'fulfilled').length;
  if (succeeded > 0) toast.show(t('ownerOrders.bulkReadyDone', { count: succeeded }), 'success');
};

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
    const result = await order.updateOrderStatus(o.id, { status: newStatus });
    toast.show(t("ownerOrders.updated"), "success");
    // Warn the owner if cash was already collected — they must return it manually.
    if (newStatus === "cancelled" && result?.cash_collected) {
      toast.show(
        t("ownerOrders.cancelCashWarning", { amount: result.cash_collected }),
        "warning",
        8000,
      );
    }
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

// ── Payment ledger lazy-load ──────────────────────────────────────────────────
// The list endpoint only returns totals; payments are fetched on demand from detail.
const paymentsMap = ref({}); // orderId → OrderPayment[]

const loadPayments = async (orderId) => {
  if (paymentsMap.value[orderId]) return; // already loaded
  try {
    const { data } = await api.get(`/owner/orders/${orderId}/`);
    paymentsMap.value = { ...paymentsMap.value, [orderId]: data.payments || [] };
  } catch {
    // silently ignore — button stays visible
  }
};

// ── Payment method correction ─────────────────────────────────────────────────
const correctingPaymentId = ref(null);
// correctMethodPanel: { orderId, paymentId, currentMethod, newMethod }
const correctMethodPanel = ref(null);

const openCorrectMethod = (o, p) => {
  // Toggle: if already open for this payment, close it
  if (correctMethodPanel.value?.paymentId === p.id) {
    correctMethodPanel.value = null;
    return;
  }
  correctMethodPanel.value = {
    orderId: o.id,
    paymentId: p.id,
    currentMethod: p.method,
    newMethod: p.method === "cash" ? "wallet" : "cash",
  };
};

const submitCorrectMethod = async () => {
  const panel = correctMethodPanel.value;
  if (!panel || !panel.newMethod) return;
  if (panel.newMethod === panel.currentMethod) {
    correctMethodPanel.value = null;
    return;
  }
  correctingPaymentId.value = panel.paymentId;
  try {
    await api.post(
      `/staff/orders/${panel.orderId}/payments/${panel.paymentId}/correct-method/`,
      { method: panel.newMethod },
    );
    // Patch the paymentsMap cache
    const payments = paymentsMap.value[panel.orderId];
    if (payments) {
      const p = payments.find((x) => x.id === panel.paymentId);
      if (p) {
        p.original_method = p.original_method || p.method;
        p.method = panel.newMethod;
        p.corrected_at = new Date().toISOString();
        p.corrected_by_name = t("ownerOrders.you");
      }
      paymentsMap.value = { ...paymentsMap.value, [panel.orderId]: [...payments] };
    }
    toast.show(t("ownerOrders.correctMethodSuccess"), "success");
    correctMethodPanel.value = null;
  } catch (err) {
    toast.show(err?.response?.data?.detail || t("ownerOrders.correctMethodFailed"), "error");
  } finally {
    correctingPaymentId.value = null;
  }
};

// ── Print ticket ──────────────────────────────────────────────────────────────
// Thermal-friendly receipt printer (shared with OwnerKitchen). Includes tip + the
// restaurant thank-you note.
const { printTicket, printBulkTickets } = usePrintTicket();

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
const newOrderBannerCount = ref(0); // dismissed by clicking the banner
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
    newOrderBannerCount.value += newPending.length;
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

  // Seed the 86 board dish list so the floating button shows the correct sold-out count.
  // Non-blocking: runs after initial order fetch so it never delays the order list.
  void seed86Count();

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
