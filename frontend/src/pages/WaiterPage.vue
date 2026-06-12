<template>
  <div class="space-y-4">
    <!-- Install-the-app banner (waiters work from the installed app) -->
    <div
      v-if="!isStandalone && !installDismissed"
      class="ui-reveal flex items-center gap-3 rounded-2xl border border-indigo-500/30 bg-indigo-500/8 px-4 py-3 text-xs"
      role="status"
    >
      <span class="flex-1 font-medium text-indigo-200">
        {{ canInstall ? t('waiterInstall.prompt') : t('waiterInstall.manual') }}
      </span>
      <button v-if="canInstall" class="ui-btn-primary ui-press shrink-0 px-3 py-1.5 text-[11px]" @click="install">
        {{ t('waiterInstall.cta') }}
      </button>
      <button
        class="ui-touch-target ui-press flex shrink-0 items-center justify-center rounded-full p-1.5 text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/60"
        :aria-label="t('waiterInstall.dismiss')"
        @click="installDismissed = true"
      >✕</button>
    </div>

    <!-- Status tabs + action buttons — single scroll row so nothing clips on narrow screens -->
    <div class="overflow-x-auto" style="scrollbar-width:none;-webkit-overflow-scrolling:touch">
      <div class="flex min-w-max items-center gap-2 pb-0.5">
        <!-- Tablist (ARIA-correct container for the tab buttons) -->
        <div
          class="flex shrink-0 items-center gap-2"
          role="tablist"
          :aria-label="t('waiterPage.tablistLabel')"
          @keydown.left.prevent="focusPrevTab"
          @keydown.right.prevent="focusNextTab"
        >
          <button
            v-for="tab in tabs"
            :id="`waiter-tab-${tab.key}`"
            :key="tab.key"
            role="tab"
            :aria-selected="activeTab === tab.key"
            :aria-controls="`waiter-panel-${tab.key}`"
            class="ui-state-chip ui-press ui-touch-target shrink-0"
            :data-active="activeTab === tab.key"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
            <span
              v-if="tab.count > 0"
              class="ms-1 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full px-1 text-[10px] font-bold tabular-nums leading-none"
              :class="['pending', 'unpaid'].includes(tab.key) ? 'bg-amber-500 text-white shadow-sm shadow-amber-900/30' : 'bg-slate-700/80 text-slate-100'"
            >{{ tab.count }}</span>
          </button>
          <!-- Recent / past orders tab -->
          <button
            id="waiter-tab-recent"
            role="tab"
            :aria-selected="activeTab === 'recent'"
            aria-controls="waiter-panel-recent"
            class="ui-state-chip ui-press ui-touch-target shrink-0"
            :data-active="activeTab === 'recent'"
            @click="activeTab = 'recent'"
          >
            {{ t('waiterPage.tabRecent') }}
          </button>
          <!-- Shift summary tab -->
          <button
            id="waiter-tab-shift"
            role="tab"
            :aria-selected="activeTab === 'shift'"
            aria-controls="waiter-panel-shift"
            class="ui-state-chip ui-press ui-touch-target shrink-0"
            :data-active="activeTab === 'shift'"
            @click="openShiftSummary"
          >
            {{ t('waiterPage.tabShift') }}
          </button>
        </div>
        <!-- Separator -->
        <span class="waiter-tab-sep h-5 w-px shrink-0 self-center bg-slate-600/50" aria-hidden="true" />
        <!-- Action buttons — outside the tablist per ARIA spec but scroll with the tabs -->
        <div class="flex shrink-0 items-center gap-2">
          <button
            v-if="canManageOrders"
            class="ui-state-chip ui-press ui-touch-target shrink-0 border-[var(--color-secondary)]/40 font-semibold text-[var(--color-secondary)]"
            @click="openCharge()"
          >
            {{ t('waiterPage.chargeWalletBtn') }}
          </button>
          <button
            v-if="canManageOrders"
            class="ui-state-chip ui-press ui-touch-target shrink-0 border-emerald-500/50 bg-emerald-500/10 font-semibold text-emerald-300"
            @click="showNewOrder = true"
          >
            + {{ t('waiterPage.newOrderBtn') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Quick search (shown on non-shift tabs, fades in when there's something to search) -->
    <Transition name="fade">
      <label v-if="activeTab !== 'shift'" class="relative block">
        <span class="sr-only">{{ t('waiterPage.searchPlaceholder') }}</span>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="pointer-events-none absolute start-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" aria-hidden="true">
          <path fill-rule="evenodd" d="M9.965 11.026a5 5 0 1 1 1.06-1.06l2.755 2.754a.75.75 0 1 1-1.06 1.06l-2.755-2.754ZM10.5 7a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0Z" clip-rule="evenodd"/>
        </svg>
        <input
          v-model="searchQuery"
          type="search"
          autocomplete="off"
          :placeholder="t('waiterPage.searchPlaceholder')"
          class="ui-input ps-8 text-sm placeholder:text-slate-600"
        />
      </label>
    </Transition>

    <!-- New Order modal (normal mode) -->
    <WaiterNewOrder
      v-if="showNewOrder"
      @close="showNewOrder = false"
      @placed="onOrderPlaced"
    />

    <!-- Append items modal -->
    <WaiterNewOrder
      v-if="appendOrder"
      :append-to-order-id="appendOrder.id"
      :append-order-number="appendOrder.order_number"
      @close="appendOrder = null"
      @appended="onAppended"
    />

    <!-- Charge wallet sheet -->
    <WalletChargeSheet
      v-if="showCharge"
      :prefill-amount="chargeContext.amount"
      :order-number="chargeContext.orderNumber"
      @close="showCharge = false"
      @charged="onWalletCharged"
    />

    <!-- Offline / queue indicator -->
    <Transition name="ui-fade">
      <div
        v-if="!waiter.isOnline || waiter.offlineQueue.length > 0"
        class="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2 text-xs text-amber-300"
        role="status"
        aria-live="polite"
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0">
          <path fill-rule="evenodd" d="M6.701 2.25c.577-1 2.02-1 2.598 0l5.196 9a1.5 1.5 0 0 1-1.299 2.25H2.804a1.5 1.5 0 0 1-1.3-2.25l5.197-9ZM8 4a.75.75 0 0 1 .75.75v3a.75.75 0 0 1-1.5 0v-3A.75.75 0 0 1 8 4Zm0 7a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z" clip-rule="evenodd"/>
        </svg>
        <span v-if="!waiter.isOnline">{{ t('waiterPage.offline') }}</span>
        <span v-else>{{ t('waiterPage.syncingQueue', { n: waiter.offlineQueue.length }) }}</span>
      </div>
    </Transition>

    <!-- Loading skeleton (orders only) -->
    <div
      v-if="activeTab !== 'shift' && (activeTab === 'recent' ? waiter.recentLoading : waiter.loading)"
      :id="`waiter-panel-${activeTab}`"
      class="space-y-3"
      role="tabpanel"
      :aria-labelledby="`waiter-tab-${activeTab}`"
      aria-live="polite"
      aria-busy="true"
      :aria-label="t('common.loading')"
    >
      <div
        v-for="i in 3"
        :key="i"
        class="ui-skeleton h-36"
      />
    </div>

    <!-- Error (orders only) -->
    <div
      v-else-if="activeTab !== 'shift' && waiter.error"
      :id="`waiter-panel-${activeTab}`"
      role="tabpanel"
      :aria-labelledby="`waiter-tab-${activeTab}`"
    >
      <div role="alert" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3.5">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-sm text-red-300">{{ waiter.error }}</p>
        <button class="ui-press shrink-0 rounded-lg px-2 py-0.5 text-xs font-medium text-slate-300 underline hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber-500/60" @click="reload">{{ t('waiterPage.retry') }}</button>
      </div>
    </div>

    <!-- Empty state (orders only) -->
    <div
      v-else-if="activeTab !== 'shift' && visibleOrders.length === 0"
      :id="`waiter-panel-${activeTab}`"
      role="tabpanel"
      :aria-labelledby="`waiter-tab-${activeTab}`"
      class="ui-empty-state py-10 text-center"
    >
      <p class="text-3xl" aria-hidden="true">{{ activeTab === 'recent' ? '🗒️' : '✓' }}</p>
      <p class="mt-3 text-sm font-semibold text-slate-100">{{ activeTab === 'recent' ? t('waiterPage.noRecentOrders') : t('waiterPage.noActiveOrders') }}</p>
      <p class="mt-1.5 text-xs text-slate-400">{{ activeTab === 'recent' ? t('waiterPage.noRecentOrdersBody') : t('waiterPage.noActiveOrdersBody') }}</p>
    </div>

    <!-- Shift summary panel -->
    <div
      v-else-if="activeTab === 'shift'"
      id="waiter-panel-shift"
      role="tabpanel"
      aria-labelledby="waiter-tab-shift"
      class="space-y-4 ui-reveal"
    >
      <!-- Shift start picker -->
      <div class="flex flex-wrap items-end gap-3">
        <div class="min-w-0 flex-1 space-y-1 sm:flex-none">
          <label class="ui-stat-label block" for="shift-since-input">{{ t('waiterPage.shiftSince') }}</label>
          <input
            id="shift-since-input"
            v-model="shiftSinceInput"
            type="datetime-local"
            :aria-label="t('waiterPage.shiftSince')"
            class="ui-input"
          />
        </div>
        <button
          class="ui-btn-outline ui-press ui-touch-target disabled:opacity-50"
          :disabled="waiter.shiftSummaryLoading"
          @click="loadShiftSummary"
        >
          {{ waiter.shiftSummaryLoading ? t('waiterPage.shiftLoading') : t('waiterPage.shiftRefresh') }}
        </button>
      </div>

      <!-- Error -->
      <div v-if="waiter.shiftSummaryError" class="flex items-start gap-2 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-sm text-red-300">{{ waiter.shiftSummaryError }}</p>
      </div>

      <!-- Stats grid -->
      <div v-else-if="waiter.shiftSummary" class="grid gap-3" :class="showShiftRevenue ? 'grid-cols-3' : 'grid-cols-2'">
        <div class="ui-stat-tile space-y-1.5 text-center">
          <p class="ui-stat-value tabular-nums text-2xl font-bold">{{ waiter.shiftSummary.orders_handled }}</p>
          <p class="ui-stat-label">{{ t('waiterPage.shiftOrders') }}</p>
        </div>
        <div v-if="showShiftRevenue" class="ui-stat-tile space-y-1.5 text-center">
          <p class="ui-stat-value tabular-nums text-2xl font-bold text-emerald-300">{{ shiftRevenue }}</p>
          <p class="ui-stat-label">{{ t('waiterPage.shiftRevenue') }}</p>
        </div>
        <div class="ui-stat-tile space-y-1.5 text-center">
          <p class="ui-stat-value tabular-nums text-2xl font-bold text-sky-300">
            {{ waiter.shiftSummary.average_prep_time_minutes != null ? waiter.shiftSummary.average_prep_time_minutes : '—' }}<span v-if="waiter.shiftSummary.average_prep_time_minutes != null" class="text-base font-normal text-sky-400/70">m</span>
          </p>
          <p class="ui-stat-label">{{ t('waiterPage.shiftAvgPrep') }}</p>
        </div>
      </div>

      <!-- Period caption -->
      <p v-if="waiter.shiftSummary" class="text-center text-xs text-slate-500 tabular-nums">
        {{ t('waiterPage.shiftPeriod', { hours: waiter.shiftSummary.period_hours }) }}
      </p>

      <!-- Skeleton while loading shift summary -->
      <div v-else-if="waiter.shiftSummaryLoading" class="grid grid-cols-2 gap-3" aria-busy="true" :aria-label="t('common.loading')">
        <div v-for="i in 2" :key="i" class="ui-skeleton h-20 rounded-2xl" />
      </div>

      <!-- Empty state: no data yet (before first date filter is applied) -->
      <div v-else class="ui-empty-state py-8 text-center">
        <p class="text-sm text-slate-400">{{ t('waiterPage.shiftHint') }}</p>
      </div>
    </div>

    <!-- Order cards (with optional table grouping) -->
    <div
      v-else-if="activeTab !== 'shift'"
      :id="`waiter-panel-${activeTab}`"
      role="tabpanel"
      :aria-labelledby="`waiter-tab-${activeTab}`"
      class="space-y-4"
    >
      <!-- Table groups -->
      <template v-if="showGrouped">
        <section
          v-for="group in tableGrouping.tableGroups"
          :key="group.tableKey"
          class="space-y-2"
        >
          <!-- Table section header -->
          <div class="flex items-center justify-between gap-2 px-1">
            <div class="flex items-center gap-2 min-w-0">
              <span class="text-sm font-bold text-slate-200 truncate">{{ group.tableLabel }}</span>
              <span class="text-[11px] text-slate-500">{{ t('waiterPage.tableOrders', { n: group.orders.length }) }}</span>
            </div>
            <span class="shrink-0 tabular-nums text-xs font-semibold text-[var(--color-secondary)]">
              {{ t('waiterPage.tableTotal') }}: {{ fmtOrderPrice(group.totalOutstanding, group.orders[0]?.currency) }}
            </span>
          </div>
          <!-- Orders within this table -->
          <div class="space-y-3 ps-2 border-s-2 border-slate-700/50">
            <article
              v-for="(order, index) in group.orders"
              :key="order.id"
              class="ui-surface-lift ui-reveal overflow-hidden rounded-2xl border transition-colors"
              :class="statusCardClass(order.status)"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
            >
              <!-- Card header -->
              <div class="flex items-start justify-between gap-3 px-4 pt-4 pb-3">
                <div class="min-w-0">
                  <p class="truncate text-xl font-bold leading-tight text-white" :title="orderHeadline(order)">
                    {{ orderHeadline(order) }}
                  </p>
                  <p class="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs">
                    <span class="tabular-nums font-medium text-slate-300">#{{ order.order_number }}</span>
                    <span aria-hidden="true" class="text-slate-600">·</span>
                    <span :class="timeUrgencyClass(order.created_at, order.status)">{{ timeAgo(order.created_at) }}</span>
                    <template v-if="order.customer_name">
                      <span aria-hidden="true" class="text-slate-600">·</span>
                      <span>{{ order.customer_name }}</span>
                    </template>
                    <template v-if="order.section_name">
                      <span aria-hidden="true" class="text-slate-600">·</span>
                      <span class="text-slate-500">{{ order.section_name }}</span>
                    </template>
                  </p>
                  <span
                    v-if="order.scheduled_for"
                    class="mt-1 inline-flex items-center gap-1 rounded-full border border-violet-500/30 bg-violet-500/15 px-2 py-0.5 text-[10px] font-semibold text-violet-300"
                  >
                    <span aria-hidden="true">🗓️</span> {{ formatScheduledFor(order.scheduled_for) }}
                  </span>
                  <span
                    v-if="order.fulfillment_type === 'delivery' && order.delivery_job"
                    class="mt-1 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold"
                    :class="waiterDjChipClass(order.delivery_job.status)"
                  >
                    <span
                      v-if="order.delivery_job.status === 'searching'"
                      class="block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400 motion-safe:animate-pulse"
                      aria-hidden="true"
                    />
                    <span v-else aria-hidden="true">🛵</span>
                    {{ waiterDjChipLabel(order.delivery_job) }}
                  </span>
                </div>
                <span
                  class="mt-0.5 shrink-0 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                  :class="statusChipClass(order.status)"
                >{{ t(`waiterPage.status_${order.status}`) }}</span>
              </div>
              <!-- Items -->
              <ul class="space-y-0.5 border-t px-4 py-2.5" :class="statusBorderClass(order.status)">
                <li
                  v-for="(item, idx) in order.items"
                  :key="idx"
                  class="flex items-start gap-2.5 py-0.5 text-sm"
                  :class="item.is_voided ? 'text-slate-500' : (isItemHeld(item, order) ? 'opacity-60 text-amber-300/70' : 'text-slate-300')"
                >
                  <span
class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-700/80 bg-slate-800/70 text-[10px] font-bold tabular-nums"
                    :class="item.is_voided ? 'text-slate-500' : 'text-slate-100'">
                    {{ item.qty }}
                  </span>
                  <span
class="min-w-0 flex-1 leading-snug"
                    :class="[item.is_voided ? 'line-through text-slate-500' : (item.is_ready ? 'line-through text-slate-500' : '')]">
                    {{ item.dish_name }}
                  </span>
                  <span v-if="item.note" class="shrink-0 text-[10px] italic text-slate-500 leading-snug">({{ item.note }})</span>
                  <!-- Course chip -->
                  <span
                    v-if="(item.course ?? 0) > 0 && !item.is_voided"
                    class="shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold leading-none"
                    :class="isItemHeld(item, order)
                      ? 'border-amber-500/40 bg-amber-500/10 text-amber-400'
                      : 'border-slate-600/50 bg-slate-700/30 text-slate-400'"
                  >{{ isItemHeld(item, order) ? t('waiterPage.heldChip') : t('waiterPage.courseChip', { n: item.course }) }}</span>
                  <span
                    v-if="item.is_voided"
                    class="shrink-0 rounded-full border border-red-500/30 bg-red-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-red-400 leading-none"
                  >{{ t('waiterPage.voidedBadge') }}</span>
                  <span v-else-if="item.is_ready" class="shrink-0 text-[10px] font-semibold text-emerald-500/80 leading-snug">✓</span>
                  <button
                    v-if="canManageOrders && !item.is_voided && !TERMINAL_STATUSES.has(order.status) && order.payment_status !== 'paid'"
                    class="ui-press shrink-0 rounded p-0.5 text-slate-700 transition-colors hover:text-red-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500/60"
                    :aria-label="t('waiterPage.voidItem')"
                    :disabled="voidingItemId === item.id"
                    @click.stop="voidItem(order, item)"
                  >
                    <svg viewBox="0 0 16 16" fill="currentColor" class="h-3 w-3" aria-hidden="true"><path d="M3.75 7.25a.75.75 0 0 0 0 1.5h8.5a.75.75 0 0 0 0-1.5h-8.5Z"/></svg>
                  </button>
                </li>
                <!-- Combo sub-lines -->
                <template v-if="item.combo_components?.length">
                  <li
                    v-for="comp in item.combo_components"
                    :key="comp.dish_id"
                    class="flex items-center gap-2 ps-6 py-0.5 text-[11px] text-slate-500"
                  >
                    <span aria-hidden="true">↳</span>
                    <span>{{ comp.name }} ×{{ comp.qty * item.qty }}</span>
                  </li>
                </template>
              </ul>
              <!-- Notes row -->
              <div v-if="order.customer_note || order.owner_note" class="space-y-1 border-t px-4 py-2.5" :class="statusBorderClass(order.status)">
                <p v-if="order.customer_note" class="flex gap-2 text-xs text-slate-400">
                  <span class="shrink-0 font-semibold text-slate-300">{{ t('waiterPage.customerNote') }}:</span>
                  <span>{{ order.customer_note }}</span>
                </p>
                <p v-if="order.owner_note" class="flex gap-2 text-xs text-amber-300/90">
                  <span class="shrink-0 font-semibold">{{ t('waiterPage.staffNote') }}:</span>
                  <span>{{ order.owner_note }}</span>
                </p>
              </div>
              <!-- ETA + total + payment status -->
              <div class="border-t px-4 py-2" :class="statusBorderClass(order.status)">
                <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span v-if="order.estimated_ready_minutes" class="tabular-nums text-xs text-slate-500">
                    {{ t('waiterPage.eta', { minutes: order.estimated_ready_minutes }) }}
                  </span>
                  <span class="tabular-nums text-sm font-bold text-white">{{ fmtOrderPrice(order.total, order.currency) }}</span>
                  <span
                    class="rounded-full border px-2 py-0.5 text-[10px] font-semibold"
                    :class="order.payment_status === 'paid'
                      ? 'border-emerald-500/30 bg-emerald-500/12 text-emerald-300'
                      : 'border-amber-500/30 bg-amber-500/12 text-amber-300'"
                  >{{ order.payment_status === 'paid' ? t('ownerOrders.paid') : t('ownerOrders.unpaid') }}</span>
                </div>
                <p v-if="Number(order.amount_paid) > 0 && order.payment_status !== 'paid'" class="mt-0.5 text-[11px] tabular-nums text-amber-400">
                  {{ t('waiterPage.paidSoFar', { paid: fmtOrderPrice(order.amount_paid, order.currency), left: fmtOrderPrice(order.outstanding, order.currency) }) }}
                </p>
              </div>
              <!-- Action footer -->
              <div class="flex flex-wrap items-center gap-2 border-t px-4 py-3" :class="statusBorderClass(order.status)">
                <button
                  v-if="canManageOrders && waiter.nextStatus(order)"
                  class="ui-press ui-touch-target flex-1 rounded-xl py-2.5 text-sm font-bold tracking-wide shadow-sm transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
                  :class="[actionBtnClass(order.status), waiter.updatingOrderIds.has(order.id) ? 'opacity-50 pointer-events-none' : '']"
                  :disabled="waiter.updatingOrderIds.has(order.id)"
                  :aria-busy="waiter.updatingOrderIds.has(order.id)"
                  @click="advance(order.id)"
                >
                  <span v-if="waiter.updatingOrderIds.has(order.id)" class="inline-flex items-center gap-1.5" aria-hidden="true">
                    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                  </span>
                  <span v-else>{{ actionLabel(order) }}</span>
                </button>
                <span v-else-if="canManageOrders" class="text-xs italic text-slate-500">{{ t('waiterPage.handedOff') }}</span>
                <!-- Fire course button -->
                <button
                  v-if="canManageOrders && lowestHeldCourse(order) !== null && !TERMINAL_STATUSES.has(order.status)"
                  class="ui-press ui-touch-target shrink-0 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-300 transition-colors hover:border-amber-400 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
                  :disabled="firingCourseOrderId === order.id"
                  @click="fireCourse(order)"
                >{{ firingCourseOrderId === order.id ? t('waiterPage.firingCourse') : t('waiterPage.fireCourse', { n: lowestHeldCourse(order) }) }}</button>
                <button
                  v-if="canManageOrders && order.payment_status !== 'paid'"
                  class="ui-press ui-touch-target shrink-0 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-300 transition-colors hover:border-emerald-400 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
                  :disabled="waiter.updatingOrderIds.has(order.id)"
                  @click="settleChooser = order"
                ><span aria-hidden="true">💵</span> {{ order.status === 'ready' ? t('ownerOrders.settleAndClose') : t('ownerOrders.markPaid') }}</button>
                <button
                  v-if="order.customer_id && order.handled_by_me"
                  class="ui-press ui-touch-target shrink-0 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-300 transition-colors hover:border-amber-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
                  @click="openCustomerRating(order)"
                ><span aria-hidden="true">★</span> {{ t('ownerOrders.rateCustomer') }}</button>
                <button
                  v-if="canManageOrders && order.fulfillment_type === 'table' && ACTIVE_TABLE_STATUSES.has(order.status) && order.payment_status !== 'paid'"
                  class="ui-press ui-touch-target shrink-0 rounded-xl border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-300 transition-colors hover:border-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40"
                  @click="openAppend(order)"
                ><span aria-hidden="true">+</span> {{ t('waiterPage.addItems') }}</button>
                <button
                  class="ui-press ui-touch-target shrink-0 rounded-xl border border-slate-600/70 bg-slate-800/50 px-3 py-2 text-xs font-semibold text-slate-300 transition-colors hover:border-slate-500 hover:text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500/40"
                  @click="openBill(order)"
                ><span aria-hidden="true">🧾</span> {{ t('waiterPage.billBtn') }}</button>
              </div>
            </article>
          </div>
        </section>

        <!-- Non-table orders below groups (if any) -->
        <div v-if="tableGrouping.nonTableOrders.length" class="space-y-3">
          <article
            v-for="(order, index) in tableGrouping.nonTableOrders"
            :key="order.id"
            class="ui-surface-lift ui-reveal overflow-hidden rounded-2xl border transition-colors"
            :class="statusCardClass(order.status)"
            :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
          >
            <!-- Card header -->
            <div class="flex items-start justify-between gap-3 px-4 pt-4 pb-3">
              <div class="min-w-0">
                <p class="truncate text-xl font-bold leading-tight text-white" :title="orderHeadline(order)">
                  {{ orderHeadline(order) }}
                </p>
                <p class="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs">
                  <span class="tabular-nums font-medium text-slate-300">#{{ order.order_number }}</span>
                  <span aria-hidden="true" class="text-slate-600">·</span>
                  <span :class="timeUrgencyClass(order.created_at, order.status)">{{ timeAgo(order.created_at) }}</span>
                  <template v-if="order.customer_name">
                    <span aria-hidden="true" class="text-slate-600">·</span>
                    <span>{{ order.customer_name }}</span>
                  </template>
                  <template v-if="order.section_name">
                    <span aria-hidden="true" class="text-slate-600">·</span>
                    <span class="text-slate-500">{{ order.section_name }}</span>
                  </template>
                </p>
                <span
                  v-if="order.scheduled_for"
                  class="mt-1 inline-flex items-center gap-1 rounded-full border border-violet-500/30 bg-violet-500/15 px-2 py-0.5 text-[10px] font-semibold text-violet-300"
                >
                  <span aria-hidden="true">🗓️</span> {{ formatScheduledFor(order.scheduled_for) }}
                </span>
                <span
                  v-if="order.fulfillment_type === 'delivery' && order.delivery_job"
                  class="mt-1 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold"
                  :class="waiterDjChipClass(order.delivery_job.status)"
                >
                  <span
                    v-if="order.delivery_job.status === 'searching'"
                    class="block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400 motion-safe:animate-pulse"
                    aria-hidden="true"
                  />
                  <span v-else aria-hidden="true">🛵</span>
                  {{ waiterDjChipLabel(order.delivery_job) }}
                </span>
              </div>
              <div class="mt-0.5 flex shrink-0 flex-col items-end gap-1">
                <span
                  class="rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                  :class="statusChipClass(order.status)"
                >{{ t(`waiterPage.status_${order.status}`) }}</span>
                <span
                  v-if="orderElapsedLabel(order)"
                  class="rounded-full border px-2 py-0.5 text-[9px] font-semibold tabular-nums"
                  :class="orderElapsedClass(order)"
                >{{ orderElapsedLabel(order) }}</span>
              </div>
            </div>
            <!-- Items -->
            <ul class="space-y-0.5 border-t px-4 py-2.5" :class="statusBorderClass(order.status)">
              <li
                v-for="(item, idx) in order.items"
                :key="idx"
                class="flex items-start gap-2.5 py-0.5 text-sm"
                :class="item.is_voided ? 'text-slate-500' : (isItemHeld(item, order) ? 'opacity-60 text-amber-300/70' : 'text-slate-300')"
              >
                <span
class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-700/80 bg-slate-800/70 text-[10px] font-bold tabular-nums"
                  :class="item.is_voided ? 'text-slate-500' : 'text-slate-100'">
                  {{ item.qty }}
                </span>
                <span
class="min-w-0 flex-1 leading-snug"
                  :class="[item.is_voided ? 'line-through text-slate-500' : (item.is_ready ? 'line-through text-slate-500' : '')]">
                  {{ item.dish_name }}
                </span>
                <span v-if="item.note" class="shrink-0 text-[10px] italic text-slate-500 leading-snug">({{ item.note }})</span>
                <!-- Course chip -->
                <span
                  v-if="(item.course ?? 0) > 0 && !item.is_voided"
                  class="shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold leading-none"
                  :class="isItemHeld(item, order)
                    ? 'border-amber-500/40 bg-amber-500/10 text-amber-400'
                    : 'border-slate-600/50 bg-slate-700/30 text-slate-400'"
                >{{ isItemHeld(item, order) ? t('waiterPage.heldChip') : t('waiterPage.courseChip', { n: item.course }) }}</span>
                <span
                  v-if="item.is_voided"
                  class="shrink-0 rounded-full border border-red-500/30 bg-red-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-red-400 leading-none"
                >{{ t('waiterPage.voidedBadge') }}</span>
                <span v-else-if="item.is_ready" class="shrink-0 text-[10px] font-semibold text-emerald-500/80 leading-snug">✓</span>
                <button
                  v-if="canManageOrders && !item.is_voided && !TERMINAL_STATUSES.has(order.status) && order.payment_status !== 'paid'"
                  class="ui-press shrink-0 rounded p-0.5 text-slate-700 transition-colors hover:text-red-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500/60"
                  :aria-label="t('waiterPage.voidItem')"
                  :disabled="voidingItemId === item.id"
                  @click.stop="voidItem(order, item)"
                >
                  <svg viewBox="0 0 16 16" fill="currentColor" class="h-3 w-3" aria-hidden="true"><path d="M3.75 7.25a.75.75 0 0 0 0 1.5h8.5a.75.75 0 0 0 0-1.5h-8.5Z"/></svg>
                </button>
              </li>
              <!-- Combo sub-lines -->
              <template v-if="item.combo_components?.length">
                <li
                  v-for="comp in item.combo_components"
                  :key="comp.dish_id"
                  class="flex items-center gap-2 ps-6 py-0.5 text-[11px] text-slate-500"
                >
                  <span aria-hidden="true">↳</span>
                  <span>{{ comp.name }} ×{{ comp.qty * item.qty }}</span>
                </li>
              </template>
            </ul>
            <!-- Notes row -->
            <div v-if="order.customer_note || order.owner_note" class="space-y-1 border-t px-4 py-2.5" :class="statusBorderClass(order.status)">
              <p v-if="order.customer_note" class="flex gap-2 text-xs text-slate-400">
                <span class="shrink-0 font-semibold text-slate-300">{{ t('waiterPage.customerNote') }}:</span>
                <span>{{ order.customer_note }}</span>
              </p>
              <p v-if="order.owner_note" class="flex gap-2 text-xs text-amber-300/90">
                <span class="shrink-0 font-semibold">{{ t('waiterPage.staffNote') }}:</span>
                <span>{{ order.owner_note }}</span>
              </p>
            </div>
            <!-- ETA + total + payment status -->
            <div class="border-t px-4 py-2" :class="statusBorderClass(order.status)">
              <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span v-if="order.estimated_ready_minutes" class="tabular-nums text-xs text-slate-500">
                  {{ t('waiterPage.eta', { minutes: order.estimated_ready_minutes }) }}
                </span>
                <span class="tabular-nums text-sm font-bold text-white">{{ fmtOrderPrice(order.total, order.currency) }}</span>
                <span
                  class="rounded-full border px-2 py-0.5 text-[10px] font-semibold"
                  :class="order.payment_status === 'paid'
                    ? 'border-emerald-500/30 bg-emerald-500/12 text-emerald-300'
                    : 'border-amber-500/30 bg-amber-500/12 text-amber-300'"
                >{{ order.payment_status === 'paid' ? t('ownerOrders.paid') : t('ownerOrders.unpaid') }}</span>
              </div>
              <p v-if="Number(order.amount_paid) > 0 && order.payment_status !== 'paid'" class="mt-0.5 text-[11px] tabular-nums text-amber-400">
                {{ t('waiterPage.paidSoFar', { paid: fmtOrderPrice(order.amount_paid, order.currency), left: fmtOrderPrice(order.outstanding, order.currency) }) }}
              </p>
            </div>
            <!-- Action footer -->
            <div class="flex flex-wrap items-center gap-2 border-t px-4 py-3" :class="statusBorderClass(order.status)">
              <button
                v-if="canManageOrders && waiter.nextStatus(order)"
                class="ui-press ui-touch-target flex-1 rounded-xl py-2.5 text-sm font-bold tracking-wide shadow-sm transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
                :class="[actionBtnClass(order.status), waiter.updatingOrderIds.has(order.id) ? 'opacity-50 pointer-events-none' : '']"
                :disabled="waiter.updatingOrderIds.has(order.id)"
                :aria-busy="waiter.updatingOrderIds.has(order.id)"
                @click="advance(order.id)"
              >
                <span v-if="waiter.updatingOrderIds.has(order.id)" class="inline-flex items-center gap-1.5" aria-hidden="true">
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                </span>
                <span v-else>{{ actionLabel(order) }}</span>
              </button>
              <span v-else-if="canManageOrders" class="text-xs italic text-slate-500">{{ t('waiterPage.handedOff') }}</span>
              <!-- Fire course button -->
              <button
                v-if="canManageOrders && lowestHeldCourse(order) !== null && !TERMINAL_STATUSES.has(order.status)"
                class="ui-press ui-touch-target shrink-0 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-300 transition-colors hover:border-amber-400 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
                :disabled="firingCourseOrderId === order.id"
                @click="fireCourse(order)"
              >{{ firingCourseOrderId === order.id ? t('waiterPage.firingCourse') : t('waiterPage.fireCourse', { n: lowestHeldCourse(order) }) }}</button>
              <button
                v-if="canManageOrders && order.payment_status !== 'paid'"
                class="ui-press ui-touch-target shrink-0 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-300 transition-colors hover:border-emerald-400 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
                :disabled="waiter.updatingOrderIds.has(order.id)"
                @click="settleChooser = order"
              ><span aria-hidden="true">💵</span> {{ order.status === 'ready' ? t('ownerOrders.settleAndClose') : t('ownerOrders.markPaid') }}</button>
              <button
                v-if="order.customer_id && order.handled_by_me"
                class="ui-press ui-touch-target shrink-0 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-300 transition-colors hover:border-amber-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
                @click="openCustomerRating(order)"
              ><span aria-hidden="true">★</span> {{ t('ownerOrders.rateCustomer') }}</button>
              <button
                class="ui-press ui-touch-target shrink-0 rounded-xl border border-slate-600/70 bg-slate-800/50 px-3 py-2 text-xs font-semibold text-slate-300 transition-colors hover:border-slate-500 hover:text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500/40"
                @click="openBill(order)"
              ><span aria-hidden="true">🧾</span> {{ t('waiterPage.billBtn') }}</button>
            </div>
          </article>
        </div>
      </template>

      <!-- Flat list when no grouping applies -->
      <template v-else>
      <article
        v-for="(order, index) in visibleOrders"
        :key="order.id"
        class="ui-surface-lift ui-reveal overflow-hidden rounded-2xl border transition-colors"
        :class="statusCardClass(order.status)"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
      >
        <!-- Card header -->
        <div class="flex items-start justify-between gap-3 px-4 pt-4 pb-3">
          <div class="min-w-0">
            <!-- Table / fulfillment label (largest text — for quick scanning) -->
            <p class="truncate text-xl font-bold leading-tight text-white" :title="orderHeadline(order)">
              {{ orderHeadline(order) }}
            </p>
            <p class="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs">
              <span class="tabular-nums font-medium text-slate-300">#{{ order.order_number }}</span>
              <span aria-hidden="true" class="text-slate-600">·</span>
              <span :class="timeUrgencyClass(order.created_at, order.status)">{{ timeAgo(order.created_at) }}</span>
              <template v-if="order.customer_name">
                <span aria-hidden="true" class="text-slate-600">·</span>
                <span>{{ order.customer_name }}</span>
              </template>
              <template v-if="order.section_name">
                <span aria-hidden="true" class="text-slate-600">·</span>
                <span class="text-slate-500">{{ order.section_name }}</span>
              </template>
            </p>
            <!-- Scheduled-for badge — advance orders only -->
            <span
              v-if="order.scheduled_for"
              class="mt-1 inline-flex items-center gap-1 rounded-full border border-violet-500/30 bg-violet-500/15 px-2 py-0.5 text-[10px] font-semibold text-violet-300"
            >
              <span aria-hidden="true">🗓️</span> {{ formatScheduledFor(order.scheduled_for) }}
            </span>
            <!-- Delivery job status chip — lets waiters see driver dispatch state -->
            <span
              v-if="order.fulfillment_type === 'delivery' && order.delivery_job"
              class="mt-1 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold"
              :class="waiterDjChipClass(order.delivery_job.status)"
            >
              <span
                v-if="order.delivery_job.status === 'searching'"
                class="block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400 motion-safe:animate-pulse"
                aria-hidden="true"
              />
              <span v-else aria-hidden="true">🛵</span>
              {{ waiterDjChipLabel(order.delivery_job) }}
            </span>
          </div>
          <!-- Status chip -->
          <span
            class="mt-0.5 shrink-0 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            :class="statusChipClass(order.status)"
          >{{ t(`waiterPage.status_${order.status}`) }}</span>
        </div>

        <!-- Items -->
        <ul class="space-y-0.5 border-t px-4 py-2.5" :class="statusBorderClass(order.status)">
          <li
            v-for="(item, idx) in order.items"
            :key="idx"
            class="flex items-start gap-2.5 py-0.5 text-sm"
            :class="item.is_voided ? 'text-slate-500' : (isItemHeld(item, order) ? 'opacity-60 text-amber-300/70' : 'text-slate-300')"
          >
            <span
class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-700/80 bg-slate-800/70 text-[10px] font-bold tabular-nums"
              :class="item.is_voided ? 'text-slate-500' : 'text-slate-100'">
              {{ item.qty }}
            </span>
            <span
class="min-w-0 flex-1 leading-snug"
              :class="[item.is_voided ? 'line-through text-slate-500' : (item.is_ready ? 'line-through text-slate-500' : '')]">
              {{ item.dish_name }}
            </span>
            <span v-if="item.note" class="shrink-0 text-[10px] italic text-slate-500 leading-snug">({{ item.note }})</span>
            <!-- Course chip -->
            <span
              v-if="(item.course ?? 0) > 0 && !item.is_voided"
              class="shrink-0 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold leading-none"
              :class="isItemHeld(item, order)
                ? 'border-amber-500/40 bg-amber-500/10 text-amber-400'
                : 'border-slate-600/50 bg-slate-700/30 text-slate-400'"
            >{{ isItemHeld(item, order) ? t('waiterPage.heldChip') : t('waiterPage.courseChip', { n: item.course }) }}</span>
            <!-- Voided badge -->
            <span
              v-if="item.is_voided"
              class="shrink-0 rounded-full border border-red-500/30 bg-red-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-red-400 leading-none"
            >{{ t('waiterPage.voidedBadge') }}</span>
            <span v-else-if="item.is_ready" class="shrink-0 text-[10px] font-semibold text-emerald-500/80 leading-snug">✓</span>
            <!-- Void affordance — only for non-voided items when waiter can manage orders -->
            <button
              v-if="canManageOrders && !item.is_voided && !TERMINAL_STATUSES.has(order.status) && order.payment_status !== 'paid'"
              class="ui-press shrink-0 rounded p-0.5 text-slate-700 transition-colors hover:text-red-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500/60"
              :aria-label="t('waiterPage.voidItem')"
              :disabled="voidingItemId === item.id"
              @click.stop="voidItem(order, item)"
            >
              <svg viewBox="0 0 16 16" fill="currentColor" class="h-3 w-3" aria-hidden="true"><path d="M3.75 7.25a.75.75 0 0 0 0 1.5h8.5a.75.75 0 0 0 0-1.5h-8.5Z"/></svg>
            </button>
          </li>
        </ul>

        <!-- Notes row -->
        <div v-if="order.customer_note || order.owner_note" class="space-y-1 border-t px-4 py-2.5" :class="statusBorderClass(order.status)">
          <p v-if="order.customer_note" class="flex gap-2 text-xs text-slate-400">
            <span class="shrink-0 font-semibold text-slate-300">{{ t('waiterPage.customerNote') }}:</span>
            <span>{{ order.customer_note }}</span>
          </p>
          <p v-if="order.owner_note" class="flex gap-2 text-xs text-amber-300/90">
            <span class="shrink-0 font-semibold">{{ t('waiterPage.staffNote') }}:</span>
            <span>{{ order.owner_note }}</span>
          </p>
        </div>

        <!-- ETA + total + payment status -->
        <div class="border-t px-4 py-2" :class="statusBorderClass(order.status)">
          <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span v-if="order.estimated_ready_minutes" class="tabular-nums text-xs text-slate-500">
              {{ t('waiterPage.eta', { minutes: order.estimated_ready_minutes }) }}
            </span>
            <span class="tabular-nums text-sm font-bold text-white">{{ fmtOrderPrice(order.total, order.currency) }}</span>
            <span
              class="rounded-full border px-2 py-0.5 text-[10px] font-semibold"
              :class="order.payment_status === 'paid'
                ? 'border-emerald-500/30 bg-emerald-500/12 text-emerald-300'
                : 'border-amber-500/30 bg-amber-500/12 text-amber-300'"
            >{{ order.payment_status === 'paid' ? t('ownerOrders.paid') : t('ownerOrders.unpaid') }}</span>
          </div>
          <p v-if="Number(order.amount_paid) > 0 && order.payment_status !== 'paid'" class="mt-0.5 text-[11px] tabular-nums text-amber-400">
            {{ t('waiterPage.paidSoFar', { paid: fmtOrderPrice(order.amount_paid, order.currency), left: fmtOrderPrice(order.outstanding, order.currency) }) }}
          </p>
        </div>

        <!-- Action footer -->
        <div class="flex flex-wrap items-center gap-2 border-t px-4 py-3" :class="statusBorderClass(order.status)">
          <button
            v-if="canManageOrders && waiter.nextStatus(order)"
            class="ui-press ui-touch-target flex-1 rounded-xl py-2.5 text-sm font-bold tracking-wide shadow-sm transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
            :class="[actionBtnClass(order.status), waiter.updatingOrderIds.has(order.id) ? 'opacity-50 pointer-events-none' : '']"
            :disabled="waiter.updatingOrderIds.has(order.id)"
            :aria-busy="waiter.updatingOrderIds.has(order.id)"
            @click="advance(order.id)"
          >
            <span v-if="waiter.updatingOrderIds.has(order.id)" class="inline-flex items-center gap-1.5" aria-hidden="true">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            </span>
            <span v-else>{{ actionLabel(order) }}</span>
          </button>
          <span v-else-if="canManageOrders" class="text-xs italic text-slate-500">{{ t('waiterPage.handedOff') }}</span>

          <!-- Fire course button -->
          <button
            v-if="canManageOrders && lowestHeldCourse(order) !== null && !TERMINAL_STATUSES.has(order.status)"
            class="ui-press ui-touch-target shrink-0 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-300 transition-colors hover:border-amber-400 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
            :disabled="firingCourseOrderId === order.id"
            @click="fireCourse(order)"
          >{{ firingCourseOrderId === order.id ? t('waiterPage.firingCourse') : t('waiterPage.fireCourse', { n: lowestHeldCourse(order) }) }}</button>

          <!-- Settle — opens a Cash / Wallet chooser, then marks paid (and closes
               a ready dine-in order). -->
          <button
            v-if="canManageOrders && order.payment_status !== 'paid'"
            class="ui-press ui-touch-target shrink-0 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-300 transition-colors hover:border-emerald-400 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
            :disabled="waiter.updatingOrderIds.has(order.id)"
            @click="settleChooser = order"
          ><span aria-hidden="true">💵</span> {{ order.status === 'ready' ? t('ownerOrders.settleAndClose') : t('ownerOrders.markPaid') }}</button>

          <!-- Rate the customer — only the server who handled this order -->
          <button
            v-if="order.customer_id && order.handled_by_me"
            class="ui-press ui-touch-target shrink-0 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-300 transition-colors hover:border-amber-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
            @click="openCustomerRating(order)"
          ><span aria-hidden="true">★</span> {{ t('ownerOrders.rateCustomer') }}</button>

          <!-- Add items button — table orders only, active statuses, not paid -->
          <button
            v-if="canManageOrders && order.fulfillment_type === 'table' && ACTIVE_TABLE_STATUSES.has(order.status) && order.payment_status !== 'paid'"
            class="ui-press ui-touch-target shrink-0 rounded-xl border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-300 transition-colors hover:border-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40"
            @click="openAppend(order)"
          ><span aria-hidden="true">+</span> {{ t('waiterPage.addItems') }}</button>

          <!-- Bill button -->
          <button
            class="ui-press ui-touch-target shrink-0 rounded-xl border border-slate-600/70 bg-slate-800/50 px-3 py-2 text-xs font-semibold text-slate-300 transition-colors hover:border-slate-500 hover:text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500/40"
            @click="openBill(order)"
          ><span aria-hidden="true">🧾</span> {{ t('waiterPage.billBtn') }}</button>
        </div>

      </article>
      </template>
    </div>
  </div>

  <!-- Customer trust rating modal (server-only) — also prompted right after a
       dine-in order is settled & closed, the moment service ends. -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0"
      leave-active-class="transition-all duration-150"
      leave-to-class="opacity-0"
    >
      <div
        v-if="ratingOrder"
        class="fixed inset-0 z-[2000] flex items-end justify-center bg-black/60 p-3 backdrop-blur-sm sm:items-center"
        @click.self="ratingOrder = null"
        @keydown.esc="ratingOrder = null"
      >
        <div
          ref="ratingDialogRef"
          class="ui-panel w-full max-w-sm space-y-3 p-4"
          role="dialog"
          aria-modal="true"
          :aria-label="t('ownerOrders.customerRatingTitle')"
        >
          <div>
            <p class="ui-kicker">{{ t('ownerOrders.customerRatingTitle') }}</p>
            <p class="mt-0.5 text-xs text-slate-400">
              {{ ratingOrder.customer_name || ratingOrder.table_label || ('#' + ratingOrder.order_number) }}
            </p>
            <p class="mt-1 text-[11px] text-slate-500">{{ t('ownerOrders.customerRatingHint') }}</p>
          </div>
          <div class="flex items-center gap-1.5" role="group" :aria-label="t('ownerOrders.customerRatingTitle')">
            <button
              v-for="n in 5" :key="n" type="button"
              class="ui-press text-3xl leading-none transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/60"
              :class="n <= custRatingScore ? 'text-amber-400' : 'text-slate-600'"
              :aria-label="t('common.rateNStars', { n })"
              :aria-pressed="n <= custRatingScore"
              @click="custRatingScore = n"
            >★</button>
          </div>
          <input
            v-model="custRatingNote" type="text" maxlength="200"
            class="ui-input"
            :aria-label="t('ownerOrders.customerRatingNote')"
            :placeholder="t('ownerOrders.customerRatingNote')"
          />
          <div class="flex items-center justify-end gap-2 pt-1">
            <button class="ui-press ui-touch-target px-3 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500/60" @click="ratingOrder = null">
              {{ t('common.cancel') }}
            </button>
            <button
              class="ui-btn-primary ui-press inline-flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-50"
              :disabled="!custRatingScore || submittingCustRating"
              :aria-busy="submittingCustRating"
              @click="submitCustomerRating"
            >
              <svg v-if="submittingCustRating" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ submittingCustRating ? t('common.loading') : t('ownerOrders.customerRatingSubmit') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- Settle: choose how the order was paid (cash or wallet) -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0"
      leave-active-class="transition-all duration-150"
      leave-to-class="opacity-0"
    >
      <div
        v-if="settleChooser"
        class="fixed inset-0 z-[2500] flex items-end justify-center bg-black/60 p-3 backdrop-blur-sm sm:items-center"
        @click.self="settleChooser = null"
        @keydown.esc="settleChooser = null"
      >
        <div
          ref="settleDialogRef"
          class="ui-panel w-full max-w-sm space-y-3 p-4"
          role="dialog"
          aria-modal="true"
          :aria-label="t('waiterPage.settleTitle')"
        >
          <div>
            <p class="ui-kicker">{{ t('waiterPage.settleTitle') }}</p>
            <p class="mt-0.5 tabular-nums text-xs text-slate-400">
              {{ settleChooser.table_label || ('#' + settleChooser.order_number) }} ·
              {{ fmtOrderPrice(settleOutstanding(settleChooser), settleChooser.currency) }}
            </p>
          </div>
          <!-- Item breakdown -->
          <ul v-if="settleChooser.items?.length" class="max-h-28 overflow-y-auto divide-y divide-slate-700/40 rounded-lg border border-slate-700/50 bg-slate-800/50" aria-label="Order items">
            <li
              v-for="item in settleChooser.items"
              :key="item.id"
              class="flex items-center justify-between gap-2 px-2.5 py-1.5 text-xs"
            >
              <span class="min-w-0 truncate text-slate-300"><span class="text-slate-500">{{ item.qty }}×</span> {{ item.dish_name }}</span>
              <span class="shrink-0 tabular-nums text-slate-400">{{ fmtOrderPrice((item.subtotal ?? item.unit_price * item.qty), settleChooser.currency) }}</span>
            </li>
          </ul>
          <!-- Split-payment amount input -->
          <div class="space-y-1">
            <label class="block text-xs font-medium text-slate-300" :for="'settle-amount-' + settleChooser.id">
              {{ t('waiterPage.splitAmount') }}
            </label>
            <input
              :id="'settle-amount-' + settleChooser.id"
              v-model="splitAmount"
              type="number"
              inputmode="decimal"
              step="0.01"
              min="0.01"
              :max="settleOutstanding(settleChooser)"
              class="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm tabular-nums text-slate-100 focus:border-[var(--color-secondary)] focus:outline-none"
            />
            <p class="text-[11px] text-slate-500">{{ t('waiterPage.splitHint') }}</p>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <button
              class="ui-press ui-touch-target flex flex-col items-center gap-1 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-4 text-emerald-300 transition-colors hover:border-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
              @click="payCash(settleChooser)"
            >
              <span class="text-2xl" aria-hidden="true">💵</span>
              <span class="text-sm font-semibold">{{ t('waiterPage.payCash') }}</span>
            </button>
            <button
              class="ui-press ui-touch-target flex flex-col items-center gap-1 rounded-xl border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/10 px-3 py-4 text-[var(--color-secondary)] transition-colors hover:border-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
              @click="payWallet(settleChooser)"
            >
              <span class="text-2xl" aria-hidden="true">💳</span>
              <span class="text-sm font-semibold">{{ t('waiterPage.payWalletMethod') }}</span>
            </button>
          </div>
          <button
            class="ui-press ui-touch-target w-full px-3 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 focus-visible:outline-none"
            @click="settleChooser = null"
          >
            {{ t('common.cancel') }}
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- Bill / receipt modal -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 scale-95"
      leave-active-class="transition-all duration-150"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="billOrder"
        class="fixed inset-0 z-[4000] flex items-center justify-center p-4 bg-black/70 no-print"
        @click.self="billOrder = null"
        @keydown.esc="billOrder = null"
      >
        <div ref="billDialogRef" role="dialog" aria-modal="true" aria-labelledby="waiter-bill-dialog-title" class="bill-sheet w-full max-w-sm rounded-2xl bg-white text-slate-900 shadow-2xl overflow-hidden">
          <!-- Header -->
          <div class="bill-header bg-slate-900 px-5 py-4 text-center">
            <p class="text-xs font-semibold uppercase tracking-widest text-slate-400">{{ tenantName }}</p>
            <h2 id="waiter-bill-dialog-title" class="mt-0.5 text-base font-bold text-white">{{ t('waiterPage.billTitle') }}</h2>
          </div>

          <!-- Meta -->
          <div class="px-5 pt-4 pb-2 border-b border-slate-200 space-y-1">
            <div class="flex justify-between text-sm">
              <span class="text-slate-500">{{ t('waiterPage.billOrderNum') }}</span>
              <span class="font-semibold">#{{ billOrder.order_number }}</span>
            </div>
            <div class="flex justify-between text-sm">
              <span class="text-slate-500">{{ t('waiterPage.billTable') }}</span>
              <span class="font-semibold">{{ orderHeadline(billOrder) }}</span>
            </div>
            <div v-if="billOrder.customer_name" class="flex justify-between text-sm">
              <span class="text-slate-500">{{ t('waiterPage.billCustomer') }}</span>
              <span class="font-semibold">{{ billOrder.customer_name }}</span>
            </div>
            <div class="flex justify-between text-xs text-slate-400">
              <span>{{ billDateTime(billOrder.created_at) }}</span>
            </div>
          </div>

          <!-- Items -->
          <ul class="px-5 py-3 space-y-1.5 border-b border-slate-200">
            <li
              v-for="(item, idx) in billOrder.items"
              :key="idx"
              class="flex items-baseline justify-between gap-2 text-sm"
              :class="item.is_voided ? 'opacity-50' : ''"
            >
              <span class="min-w-0" :class="item.is_voided ? 'line-through text-slate-400' : 'text-slate-700'">
                <span class="font-semibold" :class="item.is_voided ? 'text-slate-400' : 'text-slate-900'">{{ item.qty }}×</span>
                {{ item.dish_name }}
                <span v-if="item.note" class="text-[11px] italic text-slate-400"> ({{ item.note }})</span>
                <span v-if="item.is_voided" class="ms-1 rounded-full bg-red-100 px-1.5 py-0.5 text-[9px] font-semibold text-red-500 not-italic no-underline" style="text-decoration:none">{{ t('waiterPage.voidedBadge') }}</span>
              </span>
              <span class="shrink-0 tabular-nums" :class="item.is_voided ? 'line-through text-slate-300' : 'text-slate-600'">
                {{ fmtOrderPrice(item.subtotal ?? (item.unit_price * item.qty), billOrder.currency) }}
              </span>
            </li>
          </ul>

          <!-- Total + wallet deduction -->
          <div class="px-5 py-3 space-y-1">
            <div class="flex items-center justify-between">
              <span class="text-sm font-semibold text-slate-600">{{ t('waiterPage.billTotal') }}</span>
              <span class="text-lg font-bold text-slate-900">{{ fmtOrderPrice(billOrder.total, billOrder.currency) }}</span>
            </div>
            <div v-if="Number(billOrder.wallet_amount_paid) > 0" class="flex items-center justify-between text-xs">
              <span class="text-emerald-600">💰 {{ t('waiterPage.billWallet') }}</span>
              <span class="text-emerald-600 font-semibold">−{{ fmtOrderPrice(billOrder.wallet_amount_paid, billOrder.currency) }}</span>
            </div>
          </div>

          <!-- Pay with wallet (when there's still an outstanding amount) -->
          <div v-if="billOutstanding > 0 && canManageOrders" class="px-5 pb-1 no-print">
            <button
              class="w-full rounded-xl border border-emerald-500/60 bg-emerald-500/10 py-2.5 text-sm font-semibold text-emerald-700 transition-colors hover:bg-emerald-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
              @click="chargeFromBill"
            ><span aria-hidden="true">💰</span> {{ t('waiterPage.billPayWallet', { amount: fmtOrderPrice(billOutstanding, billOrder.currency) }) }}</button>
          </div>

          <!-- Actions -->
          <div class="flex gap-2 px-5 pb-5 no-print">
            <button
              class="flex-1 rounded-xl bg-slate-900 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
              @click="printBill"
            ><span aria-hidden="true">🖨</span> {{ t('waiterPage.billPrint') }}</button>
            <button
              class="rounded-xl border border-slate-300 px-4 py-2.5 text-sm text-slate-600 transition-colors hover:border-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
              @click="billOrder = null"
            >{{ t('waiterPage.billClose') }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, nextTick, onBeforeUnmount, onMounted, onUnmounted, watch } from "vue";
import { useI18n } from "../composables/useI18n";
import { useInstallPrompt } from "../composables/useInstallPrompt";
import { useWaiterStore } from "../stores/waiter";
import { useToastStore } from "../stores/toast";
import { useTenantStore } from "../stores/tenant";
import { useSessionStore } from "../stores/session";
import { usePromptModal } from "../composables/usePromptModal";
import WaiterNewOrder from "../components/WaiterNewOrder.vue";
import WalletChargeSheet from "../components/WalletChargeSheet.vue";
import api from "../lib/api";
import { chipClass as _statusChipClass } from "../lib/orderStatusMeta";
import { useNowTicker } from "../composables/useNowTicker";

const { t, currentLocale } = useI18n();
const { canInstall, isStandalone, install } = useInstallPrompt();
const installDismissed = ref(false);
const waiter = useWaiterStore();
// 30-s ticker for elapsed-time badges on active cards (task 3)
const { now: tickerNow } = useNowTicker();
const toast = useToastStore();
const tenant = useTenantStore();
const session = useSessionStore();
// Staff need the 'manage orders' permission to mutate orders or take payment;
// owners always have it. Read-only staff still see the board.
const canManageOrders = computed(() => session.canManageOrders);
const tenantName = computed(() => tenant.resolvedMeta?.name || '');

const showNewOrder = ref(false);
// Append mode: { id, order_number } of the order to append items to, or null.
const appendOrder = ref(null);
const { prompt } = usePromptModal();

// Void item
const voidingItemId = ref(null);

// Fire course
const firingCourseOrderId = ref(null);

const lowestHeldCourse = (order) => {
  if (order.fulfillment_type !== 'table') return null;
  const firedCourse = order.fired_course ?? 1;
  let lowest = null;
  for (const item of (order.items || [])) {
    const c = item.course ?? 0;
    if (c > 0 && c > firedCourse) {
      if (lowest === null || c < lowest) lowest = c;
    }
  }
  return lowest;
};

const isItemHeld = (item, order) => {
  const c = item.course ?? 0;
  if (c === 0) return false;
  return c > (order.fired_course ?? 1);
};

const fireCourse = async (order) => {
  const course = lowestHeldCourse(order);
  if (!course || firingCourseOrderId.value === order.id) return;
  firingCourseOrderId.value = order.id;
  try {
    const { data } = await api.post(`/staff/orders/${order.id}/fire-course/`, { course });
    // Optimistically patch the order in the store list so cards update instantly.
    const o = waiter.orders.find((x) => x.id === order.id);
    if (o) o.fired_course = data.fired_course ?? course;
  } catch (err) {
    const code = err?.response?.data?.code;
    const keyMap = {
      already_fired: 'fireCourseError_already_fired',
      not_table: 'fireCourseError_not_table',
      bad_status: 'fireCourseError_bad_status',
      invalid_course: 'fireCourseError_invalid_course',
    };
    const msgKey = keyMap[code] || 'fireCourseError_default';
    toast.show(t(`waiterPage.${msgKey}`, { n: course }), 'error');
  } finally {
    firingCourseOrderId.value = null;
  }
};

const openAppend = (order) => {
  appendOrder.value = { id: order.id, order_number: order.order_number };
};

const onAppended = () => {
  appendOrder.value = null;
  waiter.fetchOrders({ silent: true });
};

const voidItem = async (order, item) => {
  if (voidingItemId.value) return;
  const reason = await prompt({
    title: t('waiterPage.voidItem'),
    placeholder: t('waiterPage.voidReasonPrompt'),
    required: false,
  });
  if (reason === null) return; // cancelled
  voidingItemId.value = item.id;
  try {
    await api.post(`/staff/orders/${order.id}/items/${item.id}/void/`, { reason: reason.trim() });
    toast.show(t('waiterPage.itemVoided'), 'success');
    await waiter.fetchOrders({ silent: true });
  } catch {
    toast.show(t('waiterPage.voidFailed'), 'error');
  } finally {
    voidingItemId.value = null;
  }
};

// ── Table grouping (waiter) ────────────────────────────────────────────────────
const TERMINAL_STATUSES = new Set(['cancelled', 'completed', 'delivered']);
const ACTIVE_TABLE_STATUSES = new Set(['pending', 'confirmed', 'preparing', 'ready']);

// Groups active table orders by table_label. Returns:
//   { tableGroups: [{ tableKey, tableLabel, orders, totalOutstanding }], nonTableOrders }
const tableGrouping = computed(() => {
  // Only group when activeTab is 'all' or one of the active status tabs and not 'recent'/'shift'.
  const src = visibleOrders.value;
  const tableMap = new Map(); // tableKey -> { tableLabel, orders }
  const nonTableOrders = [];

  for (const order of src) {
    const isActiveTable =
      order.fulfillment_type === 'table' &&
      order.table_label &&
      ACTIVE_TABLE_STATUSES.has(order.status);

    if (isActiveTable) {
      const key = order.table_label.trim().toLowerCase();
      if (!tableMap.has(key)) {
        tableMap.set(key, { tableKey: key, tableLabel: order.table_label, orders: [] });
      }
      tableMap.get(key).orders.push(order);
    } else {
      nonTableOrders.push(order);
    }
  }

  const tableGroups = [...tableMap.values()].map((g) => ({
    ...g,
    totalOutstanding: g.orders.reduce(
      (sum, o) => sum + settleOutstanding(o),
      0
    ),
  }));

  return { tableGroups, nonTableOrders };
});

const showGrouped = computed(() =>
  activeTab.value !== 'recent' && activeTab.value !== 'shift' && tableGrouping.value.tableGroups.length > 0
);

const showCharge = ref(false);
const chargeContext = ref({ amount: '', orderNumber: '' });
const settleChooser = ref(null);        // order awaiting a cash/wallet choice
const settleIntentKey = ref(null);      // idempotency key minted when the chooser opens
const pendingWalletSettle = ref(null);  // order being settled via the wallet charge sheet
// If the backend provides `outstanding` (new ledger), use it; otherwise fall back to total-wallet.
const settleOutstanding = (order) => {
  if (order.outstanding !== undefined && order.outstanding !== null)
    return Math.max(0, +Number(order.outstanding).toFixed(2));
  return Math.max(0, +((Number(order.total) || 0) - (Number(order.wallet_amount_paid) || 0)).toFixed(2));
};
// Tracks the amount the user typed in the settle-chooser input (empty string = full amount).
const splitAmount = ref('');

// Outstanding amount on the open bill (total minus any wallet already applied).
const billOutstanding = computed(() => {
  if (!billOrder.value) return 0;
  const total = Number(billOrder.value.total) || 0;
  const paid = Number(billOrder.value.wallet_amount_paid) || 0;
  return Math.max(0, +(total - paid).toFixed(2));
});

const openCharge = (ctx = { amount: '', orderNumber: '' }) => {
  chargeContext.value = ctx;
  showCharge.value = true;
};

const chargeFromBill = () => {
  if (!billOrder.value) return;
  openCharge({ amount: billOutstanding.value.toFixed(2), orderNumber: billOrder.value.order_number });
  billOrder.value = null;
};

const onWalletCharged = async () => {
  const num = chargeContext.value.orderNumber;
  showCharge.value = false;
  await reload(); // refresh orders so the bill reflects the wallet payment
  // If this charge came from the Settle chooser, close the order out (completes a
  // ready dine-in order) and prompt the rating — same as the cash path.
  const settling = pendingWalletSettle.value;
  pendingWalletSettle.value = null;
  if (settling) {
    await _finishSettle(settling);
    return;
  }
  // Otherwise (charged from the bill), reopen the bill so the waiter sees confirmation.
  if (num) {
    const updated = waiter.orders.find((o) => o.order_number === num);
    if (updated) billOrder.value = updated;
  }
};
const onOrderPlaced = () => {
  // Immediately reload the order list so the new order appears
  waiter.fetchOrders({ silent: true });
};

// ── Bill / receipt ─────────────────────────────────────────────────────────────
const billOrder = ref(null);
const billDialogRef = ref(null);
const openBill = (order) => { billOrder.value = order; };

const FOCUSABLE_BILL = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapBillFocus = (e) => {
  if (!billDialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(billDialogRef.value.querySelectorAll(FOCUSABLE_BILL));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

watch(billOrder, async (val) => {
  if (val) {
    await nextTick();
    billDialogRef.value?.querySelector(FOCUSABLE_BILL)?.focus();
    document.addEventListener('keydown', trapBillFocus);
  } else {
    document.removeEventListener('keydown', trapBillFocus);
  }
});
onBeforeUnmount(() => document.removeEventListener('keydown', trapBillFocus));

// ── Customer rating dialog focus trap ──────────────────────────────────────────
// Held as the full order object (not just an id) so it survives the order being
// removed from the active list after a "settle & close". Declared here, above its
// watcher below, to avoid a temporal-dead-zone crash during setup().
const ratingOrder = ref(null);
const ratingDialogRef = ref(null);

const trapRatingFocus = (e) => {
  if (!ratingDialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(ratingDialogRef.value.querySelectorAll(FOCUSABLE_BILL));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

watch(ratingOrder, async (val) => {
  if (val) {
    await nextTick();
    ratingDialogRef.value?.querySelector(FOCUSABLE_BILL)?.focus();
    document.addEventListener('keydown', trapRatingFocus);
  } else {
    document.removeEventListener('keydown', trapRatingFocus);
  }
});
onBeforeUnmount(() => document.removeEventListener('keydown', trapRatingFocus));

// ── Settle chooser dialog focus trap ───────────────────────────────────────────
const settleDialogRef = ref(null);

const trapSettleFocus = (e) => {
  if (!settleDialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(settleDialogRef.value.querySelectorAll(FOCUSABLE_BILL));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

// Track which order the current intent key belongs to, so switching orders gets a fresh key.
const settleIntentOrderId = ref(null);

watch(settleChooser, async (val) => {
  if (val) {
    // Pre-fill with the full outstanding amount; the user can edit it down.
    splitAmount.value = settleOutstanding(val).toFixed(2);
    // Mint a fresh idempotency key when the chooser opens for a NEW order.
    // Reuse the existing key when reopening for the SAME order after a failed/
    // timed-out attempt — so the backend can deduplicate and never double-record.
    if (!settleIntentKey.value || settleIntentOrderId.value !== val.id) {
      settleIntentKey.value = (crypto.randomUUID && crypto.randomUUID())
        || `settle-${val.id}-${Date.now()}`;
      settleIntentOrderId.value = val.id;
    }
    await nextTick();
    settleDialogRef.value?.querySelector(FOCUSABLE_BILL)?.focus();
    document.addEventListener('keydown', trapSettleFocus);
  } else {
    document.removeEventListener('keydown', trapSettleFocus);
  }
});
onBeforeUnmount(() => document.removeEventListener('keydown', trapSettleFocus));

const printBill = () => { window.print(); };
const billDateTime = (iso) => {
  try {
    return new Intl.DateTimeFormat(currentLocale.value, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
};

// ── Shift summary ──────────────────────────────────────────────────────────────
// Default shift start: 8 hours ago, formatted for datetime-local input
const _defaultSince = () => {
  const d = new Date(Date.now() - 8 * 60 * 60 * 1000);
  // Format as YYYY-MM-DDTHH:MM (local time, no seconds/tz for input compatibility)
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
const shiftSinceInput = ref(_defaultSince());

// Revenue is gated by the 'view revenue' permission (backend sends show_revenue).
const showShiftRevenue = computed(() => waiter.shiftSummary?.show_revenue !== false);

const shiftRevenue = computed(() => {
  const s = waiter.shiftSummary;
  if (!s) return "—";
  const num = parseFloat(s.total_revenue || "0");
  if (!s.currency) return num.toFixed(2);
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: "currency",
      currency: s.currency,
      maximumFractionDigits: 2,
    }).format(num);
  } catch {
    return `${num.toFixed(2)} ${s.currency}`;
  }
});

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

const fmtOrderPrice = (amount, currency) => {
  if (!currency) return Number(amount || 0).toFixed(2);
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(amount || 0);
  } catch {
    return `${Number(amount || 0).toFixed(2)} ${currency}`;
  }
};

const openShiftSummary = () => {
  activeTab.value = "shift";
  if (!waiter.shiftSummary) loadShiftSummary();
};

const loadShiftSummary = () => {
  // Convert local datetime-local value to ISO string
  const raw = shiftSinceInput.value;
  let sinceIso = null;
  if (raw) {
    try {
      sinceIso = new Date(raw).toISOString();
    } catch {
      sinceIso = null;
    }
  }
  waiter.fetchShiftSummary(sinceIso);
};

// ── Tabs ───────────────────────────────────────────────────────────────────────
const activeTab = ref("all");
const searchQuery = ref("");

const tabs = computed(() => [
  { key: "all", label: t("waiterPage.tabAll"), count: waiter.orders.length },
  { key: "pending", label: t("waiterPage.tabPending"), count: waiter.byStatus.pending.length },
  { key: "confirmed", label: t("waiterPage.tabConfirmed"), count: waiter.byStatus.confirmed.length },
  { key: "preparing", label: t("waiterPage.tabPreparing"), count: waiter.byStatus.preparing.length },
  { key: "ready", label: t("waiterPage.tabReady"), count: waiter.byStatus.ready.length },
  { key: "unpaid", label: t("waiterPage.tabUnpaid"), count: waiter.unpaidOrders.length, accent: "amber" },
]);

const visibleOrders = computed(() => {
  let orders;
  if (activeTab.value === "recent") orders = waiter.recentOrders;
  else if (activeTab.value === "all") orders = waiter.orders;
  else if (activeTab.value === "unpaid") orders = waiter.unpaidOrders;
  else orders = waiter.byStatus[activeTab.value] ?? [];

  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return orders;
  return orders.filter((o) => {
    const haystack = [o.order_number, o.customer_name, o.table_label, o.section_name, o.customer_note, o.owner_note]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
});

// Load history on demand when the waiter opens the Recent tab.
watch(activeTab, (tab) => {
  if (tab === "recent") waiter.fetchRecent();
});

// Arrow-key navigation within the tablist (ARIA APG tab pattern).
// Only moves focus — activation stays on click/Enter to match existing behavior.
const _allTabKeys = ["all", "pending", "confirmed", "preparing", "ready", "unpaid", "recent", "shift"];
const _focusTabByKey = (key) => {
  const el = document.getElementById(`waiter-tab-${key}`);
  el?.focus();
};
const focusPrevTab = () => {
  const idx = _allTabKeys.indexOf(activeTab.value);
  const prev = _allTabKeys[(idx - 1 + _allTabKeys.length) % _allTabKeys.length];
  _focusTabByKey(prev);
};
const focusNextTab = () => {
  const idx = _allTabKeys.indexOf(activeTab.value);
  const next = _allTabKeys[(idx + 1) % _allTabKeys.length];
  _focusTabByKey(next);
};

// ── Polling ────────────────────────────────────────────────────────────────────
let pollTimer = null;
let prevPendingIds = new Set();

const playAlert = () => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.18].forEach((delay) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.3, ctx.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.25);
      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + 0.25);
    });
  } catch {
    // AudioContext unavailable — silent fail
  }
};

const checkNewOrders = (orders) => {
  const currentPendingIds = new Set(orders.filter((o) => o.status === "pending").map((o) => o.id));
  const isNew = [...currentPendingIds].some((id) => !prevPendingIds.has(id));
  if (isNew && prevPendingIds.size > 0) playAlert();
  prevPendingIds = currentPendingIds;
};

const doPoll = async () => {
  const results = await waiter.fetchOrders({ silent: true });
  if (Array.isArray(results)) checkNewOrders(results);
};

const onVisible = () => {
  if (document.visibilityState === "visible") doPoll();
};

onMounted(async () => {
  const initial = await waiter.fetchOrders();
  if (Array.isArray(initial)) prevPendingIds = new Set(initial.filter((o) => o.status === "pending").map((o) => o.id));
  document.addEventListener("visibilitychange", onVisible);
  pollTimer = setInterval(() => {
    if (document.visibilityState === "hidden") return;
    doPoll();
  }, 15000);
});

onUnmounted(() => {
  clearInterval(pollTimer);
  document.removeEventListener("visibilitychange", onVisible);
});

const reload = () => waiter.fetchOrders();

// ── Actions ────────────────────────────────────────────────────────────────────
const advance = async (orderId) => {
  const ok = await waiter.advanceStatus(orderId);
  if (!ok) toast.show(t('waiterPage.updateFailed'), 'error');
};

// Customer trust rating — only the server who handled the order may submit it.
// (ratingOrder is declared above, next to its focus-trap watcher.)
const custRatingScore = ref(0);
const custRatingNote = ref("");
const submittingCustRating = ref(false);

const openCustomerRating = (order) => {
  ratingOrder.value = order;
  custRatingScore.value = order.my_customer_rating?.score ?? 0;
  custRatingNote.value = order.my_customer_rating?.note ?? "";
};

const submitCustomerRating = async () => {
  const order = ratingOrder.value;
  if (!order || !custRatingScore.value || submittingCustRating.value) return;
  submittingCustRating.value = true;
  try {
    await waiter.rateCustomer(order.id, custRatingScore.value, custRatingNote.value);
    ratingOrder.value = null;
    toast.show(t("waiterPage.ratingSubmitted"), "success");
  } catch {
    // Leave the dialog open so the waiter can retry.
    toast.show(t("waiterPage.ratingFailed"), "error");
  } finally {
    submittingCustRating.value = false;
  }
};

// Settle / mark paid — records cash/card collected; closes a ready dine-in order.
// Mark the order paid and close it out. The moment a dine-in order closes is
// exactly when service ends, so prompt the server to rate the customer right then.
const _finishSettle = async (order) => {
  const eligibleToRate = order.customer_id && order.handled_by_me && !order.my_customer_rating;
  const res = await waiter.markPaid(order.id);
  if (!res) {
    toast.show(t("waiterPage.markPaidFailed"), "error");
    return;
  }
  // The full-wallet charge-sheet path settles via markPaid (not postPayment),
  // so the settle-intent key must be cleared here too on success.
  settleIntentKey.value = null;
  settleIntentOrderId.value = null;
  if (res.completed && eligibleToRate) {
    openCustomerRating(order);
  } else if (res.completed) {
    toast.show(t("waiterPage.orderSettled"), "success");
  }
};

// Resolve the numeric amount to POST — null means "full outstanding" (omit from body).
const _resolvedSplitAmount = (order) => {
  const outstanding = settleOutstanding(order);
  const typed = parseFloat(splitAmount.value);
  if (isNaN(typed) || typed <= 0) return null;
  // If the user left the default (full amount), omit to let the backend decide.
  if (Math.abs(typed - outstanding) < 0.005) return null;
  return typed;
};

// Cash: POST to payments endpoint; partial stays open, full settles.
const payCash = async (order) => {
  const intentKey = settleIntentKey.value;
  settleChooser.value = null;
  const amount = _resolvedSplitAmount(order);
  const { data, errorCode } = await waiter.postPayment(order.id, 'cash', amount, intentKey);
  if (!data) {
    if (errorCode === 'overpay') { toast.show(t('waiterPage.overpay'), 'error'); return; }
    toast.show(t('waiterPage.markPaidFailed'), 'error');
    return;
  }
  // Clear the intent key on success so the next settle gets a fresh key.
  settleIntentKey.value = null;
  settleIntentOrderId.value = null;
  if (data.completed) {
    const eligibleToRate = order.customer_id && order.handled_by_me && !order.my_customer_rating;
    if (eligibleToRate) { openCustomerRating(order); } else { toast.show(t('waiterPage.settledFull'), 'success'); }
  } else {
    toast.show(t('waiterPage.partialPaid', { left: fmtOrderPrice(data.outstanding, order.currency) }), 'success');
  }
};

// Wallet: charge the customer's wallet via their pay-code, then close out.
const payWallet = async (order) => {
  const intentKey = settleIntentKey.value;
  settleChooser.value = null;
  const amount = _resolvedSplitAmount(order);
  // If a specific partial amount is requested, try to post directly.
  if (amount !== null) {
    const { data, errorCode } = await waiter.postPayment(order.id, 'wallet', amount, intentKey);
    if (!data) {
      if (errorCode === 'overpay') { toast.show(t('waiterPage.overpay'), 'error'); return; }
      if (errorCode === 'insufficient_wallet') { toast.show(t('waiterPage.insufficientWallet'), 'error'); return; }
      toast.show(t('waiterPage.markPaidFailed'), 'error');
      return;
    }
    // Clear on success.
    settleIntentKey.value = null;
    settleIntentOrderId.value = null;
    if (data.completed) {
      const eligibleToRate = order.customer_id && order.handled_by_me && !order.my_customer_rating;
      if (eligibleToRate) { openCustomerRating(order); } else { toast.show(t('waiterPage.settledFull'), 'success'); }
    } else {
      toast.show(t('waiterPage.partialPaid', { left: fmtOrderPrice(data.outstanding, order.currency) }), 'success');
    }
    return;
  }
  // Full amount: use the existing wallet charge-sheet flow (pay-code entry).
  // The intent key will be cleared when onWalletCharged → _finishSettle succeeds.
  pendingWalletSettle.value = order;
  openCharge({ amount: settleOutstanding(order).toFixed(2), orderNumber: order.order_number });
};

// ── Display helpers ────────────────────────────────────────────────────────────
const orderHeadline = (order) => {
  if (order.fulfillment_type === "table" && order.table_label) return order.table_label;
  if (order.fulfillment_type === "pickup") return t("waiterPage.pickup");
  if (order.fulfillment_type === "delivery") return t("waiterPage.delivery");
  return order.table_label || `#${order.order_number}`;
};

const timeAgo = (iso) => {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return t("waiterPage.justNow");
  if (diff < 3600) return t("waiterPage.minutesAgo", { n: Math.floor(diff / 60) });
  return t("waiterPage.hoursAgo", { n: Math.floor(diff / 3600) });
};

// Returns the time-ago urgency class — amber > 10 min pending, red > 20 min
const timeUrgencyClass = (iso, status) => {
  if (!['pending', 'confirmed', 'preparing'].includes(status)) return 'text-slate-400';
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins >= 20) return 'font-semibold text-red-400';
  if (mins >= 10) return 'font-semibold text-amber-400';
  return 'text-slate-400';
};

const actionLabel = (order) => {
  const isDelivery = order.fulfillment_type === "delivery";
  switch (order.status) {
    case "pending": return t("waiterPage.actionAccept");
    case "confirmed": return t("waiterPage.actionPreparing");
    case "preparing": return t("waiterPage.actionReady");
    case "ready": return isDelivery ? t("waiterPage.actionOutForDelivery") : t("waiterPage.actionDone");
    case "out_for_delivery": return t("waiterPage.actionDelivered");
    default: return "";
  }
};

// ── Styling ────────────────────────────────────────────────────────────────────
const statusCardClass = (s) => ({
  pending:   "border-amber-500/30 bg-amber-500/5",
  confirmed: "border-sky-500/30 bg-sky-500/5",
  preparing: "border-orange-500/30 bg-orange-500/5",
  ready:     "border-emerald-500/30 bg-emerald-500/5",
  out_for_delivery: "border-indigo-500/30 bg-indigo-500/5",
}[s] ?? "border-slate-700/40 bg-slate-800/30");

// statusChipClass now delegates to STATUS_META single source of truth (task 1).
const statusChipClass = (s) => _statusChipClass(s);

const statusBorderClass = (s) => ({
  pending:   "border-amber-500/20",
  confirmed: "border-sky-500/20",
  preparing: "border-orange-500/20",
  ready:     "border-emerald-500/20",
  out_for_delivery: "border-indigo-500/20",
}[s] ?? "border-slate-700/30");

const actionBtnClass = (s) => ({
  pending:   "bg-amber-500 hover:bg-amber-400 text-white",
  confirmed: "bg-sky-500 hover:bg-sky-400 text-white",
  preparing: "bg-orange-500 hover:bg-orange-400 text-white",
  ready:     "bg-emerald-500 hover:bg-emerald-400 text-white",
  out_for_delivery: "bg-indigo-500 hover:bg-indigo-400 text-white",
}[s] ?? "bg-slate-600 hover:bg-slate-500 text-white");

// ── Delivery job chip helpers ─────────────────────────────────────────────────
const waiterDjChipClass = (djStatus) => ({
  searching:     "border-amber-500/40 bg-amber-500/10 text-amber-300",
  assigned:      "border-sky-500/40 bg-sky-500/10 text-sky-300",
  at_restaurant: "border-sky-500/40 bg-sky-500/10 text-sky-300",
  picked_up:     "border-violet-500/40 bg-violet-500/10 text-violet-300",
  delivered:     "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  failed:        "border-red-500/40 bg-red-500/10 text-red-300",
  cancelled:     "border-slate-600/40 bg-slate-800/40 text-slate-400",
}[djStatus] ?? "border-slate-600/40 bg-slate-800/40 text-slate-400");

const waiterDjChipLabel = (dj) => {
  const { status, driver_name } = dj;
  if (status === "searching")     return t("kitchen.driverSearching");
  if (status === "assigned")      return driver_name ? `${t("kitchen.driverAssigned")} · ${driver_name}` : t("kitchen.driverAssigned");
  if (status === "at_restaurant") return driver_name ? `${t("kitchen.driverAtDoor")} · ${driver_name}` : t("kitchen.driverAtDoor");
  if (status === "picked_up")     return t("kitchen.driverPickedUp");
  if (status === "failed")        return t("kitchen.driverFailed");
  return status;
};

// ── Elapsed-time badge helpers (task 3) ────────────────────────────────────────
const ACTIVE_ELAPSED_STATUSES = new Set(["pending", "confirmed", "preparing", "ready"]);

const orderElapsedMinutes = (order) => {
  if (!ACTIVE_ELAPSED_STATUSES.has(order.status)) return null;
  const base = order.status_updated_at || order.created_at;
  if (!base) return null;
  return Math.floor((tickerNow.value - new Date(base).getTime()) / 60_000);
};

const orderElapsedLabel = (order) => {
  const m = orderElapsedMinutes(order);
  if (m === null) return null;
  if (order.status === "preparing" && m > 15) return t("orderFlow.overdue", { m });
  return t("orderFlow.elapsed", { m });
};

const orderElapsedClass = (order) => {
  const m = orderElapsedMinutes(order);
  if (m === null) return "";
  if (order.status === "preparing" && m > 15) return "border-amber-500/40 bg-amber-500/10 text-amber-300";
  if (m >= 20) return "border-red-500/40 bg-red-500/10 text-red-300";
  if (m >= 10) return "border-slate-600/50 bg-slate-700/30 text-slate-400";
  return "border-slate-700/40 bg-slate-800/30 text-slate-500";
};
</script>

<style>
@media print {
  /* Hide everything except the bill sheet */
  body > * { display: none !important; }
  .bill-sheet {
    display: block !important;
    position: fixed !important;
    inset: 0 !important;
    max-width: 100% !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    z-index: 99999 !important;
  }
  .no-print { display: none !important; }
}
</style>
