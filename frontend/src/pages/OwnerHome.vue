<template>
  <section class="space-y-3 pb-24 sm:pb-6">

    <!-- ── SETUP NUDGE — shown until the menu is published ─────────────── -->
    <article v-if="!published" class="ui-command-deck ui-reveal p-4 sm:p-5" style="--ui-delay: 0ms">
      <div class="flex items-start gap-3.5">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-500/15 text-amber-400">
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5">
            <path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-sm font-semibold text-slate-100">{{ t('ownerHome.setupIncompleteTitle') }}</p>
          <p class="mt-0.5 text-xs text-slate-400">{{ t('ownerHome.setupIncompleteBody') }}</p>
        </div>
        <RouterLink
          :to="{ name: 'onboarding' }"
          class="ui-btn-primary shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
        >
          {{ t('ownerHome.setupContinue') }}
          <AppIcon name="arrowRight" class="h-3.5 w-3.5 rtl:scale-x-[-1]" aria-hidden="true" />
        </RouterLink>
      </div>
    </article>

    <!-- ── CRITICAL SECTION: renders on first paint from cached store data ──── -->
    <article class="ui-workspace-stage ui-reveal space-y-4 p-4 sm:p-5">

      <!-- Header row -->
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="space-y-1.5">
          <p class="ui-kicker">{{ t("ownerHome.kicker") }}</p>
          <h1 class="ui-page-title ui-display text-[1.5rem] leading-tight tracking-tight sm:text-[2.1rem]">{{ t("ownerHome.title") }}</h1>
        </div>
        <div class="ui-scroll-row mt-0.5">
          <span class="ui-chip-strong">{{ published ? t("ownerHome.published") : t("ownerHome.draft") }}</span>
          <span class="ui-chip">{{ planModeLabel }}</span>
          <!-- Focus mode: surface the single most-important next action for a solo owner -->
          <button
            type="button"
            class="ui-chip ui-press inline-flex items-center gap-1 transition-colors"
            :class="focusMode ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : ''"
            :aria-pressed="focusMode"
            @click="toggleFocusMode"
          >
            <span aria-hidden="true">🎯</span>
            {{ focusMode ? t('ownerHome.focusOn') : t('ownerHome.focusOff') }}
          </button>
        </div>
      </div>

      <!-- ── FOCUS MODE: one prominent next-action card for the solo owner ──── -->
      <OwnerNextAction
        v-if="focusMode"
        :orders="focusOrders"
        :sold-out-count="soldOutCount"
        :busy="focusBusy"
        @act="handleNextAction"
        @skip="skipNextAction"
      />

      <!-- Opt-out link: shown only in focus mode so the owner can reveal the full dashboard -->
      <div v-if="focusMode" class="flex justify-start">
        <button
          type="button"
          class="ui-press inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-500 rounded"
          @click="toggleFocusMode"
        >{{ t('ownerHome.focusDefaultOptOut') }}</button>
      </div>

      <!-- Open / Closed — the first thing an owner checks: are we taking orders? -->
      <div
        class="flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 transition-colors"
        :class="isOpen ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-amber-500/25 bg-amber-500/5'"
        role="status"
      >
        <div class="flex min-w-0 items-center gap-3">
          <span class="relative flex h-3 w-3 shrink-0">
            <span v-if="isOpen" class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            <span class="relative inline-flex h-3 w-3 rounded-full" :class="isOpen ? 'bg-emerald-400' : 'bg-red-400'" />
          </span>
          <div class="min-w-0 leading-snug">
            <p class="text-sm font-semibold" :class="isOpen ? 'text-emerald-200' : 'text-amber-300'" aria-live="polite">
              {{ isOpen ? t("ownerHome.restaurantOpen") : t("ownerHome.restaurantClosed") }}
            </p>
            <p class="text-[11px] text-slate-500">{{ t("ownerHome.openToggleHint") }}</p>
          </div>
        </div>
        <button
          class="ui-touch-target inline-flex shrink-0 items-center gap-1.5 rounded-full border px-4 py-1.5 text-xs font-semibold transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
          :class="isOpen
            ? 'border-red-500/50 text-red-300 hover:bg-red-500/10'
            : 'border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/10'"
          :disabled="togglingOpen"
          :aria-busy="togglingOpen"
          :aria-label="togglingOpen ? t('common.loading') : (isOpen ? t('ownerHome.closeNow') : t('ownerHome.openNow'))"
          :aria-pressed="isOpen"
          @click="toggleOpen"
        >
          <svg v-if="togglingOpen" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ togglingOpen ? t("common.loading") : (isOpen ? t("ownerHome.closeNow") : t("ownerHome.openNow")) }}
        </button>
      </div>

      <!-- Quick operational toggles — accepting delivery + menu availability ──── -->
      <div class="grid gap-2 sm:grid-cols-2">
        <!-- Accepting delivery orders -->
        <div class="flex items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-950/40 px-3.5 py-2.5">
          <div class="min-w-0 leading-snug">
            <p class="text-xs font-semibold" :class="acceptingDelivery ? 'text-emerald-200' : 'text-amber-300'" aria-live="polite">
              {{ acceptingDelivery ? t("ownerHome.acceptingDelivery") : t("ownerHome.deliveryPaused") }}
            </p>
            <p class="text-[11px] text-slate-500">{{ t("ownerHome.deliveryToggleHint") }}</p>
          </div>
          <button
            class="ui-touch-target inline-flex shrink-0 items-center gap-1 rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
            :class="acceptingDelivery ? 'border-amber-500/50 text-amber-300 hover:bg-amber-500/10' : 'border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/10'"
            :disabled="togglingDelivery"
            :aria-busy="togglingDelivery"
            :aria-pressed="acceptingDelivery"
            @click="toggleDelivery"
          >
            <svg v-if="togglingDelivery" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ togglingDelivery ? t('common.loading') : (acceptingDelivery ? t("ownerHome.pauseDelivery") : t("ownerHome.resumeDelivery")) }}
          </button>
        </div>
        <!-- Menu availability -->
        <div class="flex items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-950/40 px-3.5 py-2.5">
          <div class="min-w-0 leading-snug">
            <p class="text-xs font-semibold" :class="menuActive ? 'text-emerald-200' : 'text-amber-300'" aria-live="polite">
              {{ menuActive ? t("ownerHome.menuActive") : t("ownerHome.menuDisabled") }}
            </p>
            <p class="text-[11px] text-slate-500">{{ t("ownerHome.menuToggleHint") }}</p>
          </div>
          <button
            class="ui-touch-target inline-flex shrink-0 items-center gap-1 rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
            :class="menuActive ? 'border-amber-500/50 text-amber-300 hover:bg-amber-500/10' : 'border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/10'"
            :disabled="togglingMenu"
            :aria-busy="togglingMenu"
            :aria-pressed="menuActive"
            @click="toggleMenu"
          >
            <svg v-if="togglingMenu" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ togglingMenu ? t('common.loading') : (menuActive ? t("ownerHome.disableMenu") : t("ownerHome.enableMenu")) }}
          </button>
        </div>
      </div>

      <!-- Busy mode: snooze new orders (timed auto-resume) + slow-the-kitchen quote bump -->
      <BusyModeControl />

      <!-- Cash drawer card — only rendered once drawer data has loaded; tenants
           who never open a drawer see nothing (default-preserving). -->
      <div
        v-if="drawerLoaded"
        class="flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 transition-colors"
        :class="drawerOpen
          ? 'border-emerald-500/30 bg-emerald-500/5'
          : 'border-slate-700/50 bg-slate-950/30'"
        role="region"
        :aria-label="t('cashDrawer.cardTitle')"
      >
        <div class="min-w-0 space-y-0.5">
          <p class="text-xs font-semibold" :class="drawerOpen ? 'text-emerald-200' : 'text-slate-400'">
            {{ drawerOpen ? t('cashDrawer.statusOpen') : t('cashDrawer.statusClosed') }}
          </p>
          <p v-if="drawerOpen && drawerSession" class="text-[11px] text-slate-500 tabular-nums">
            {{ t('cashDrawer.openingFloat') }}: {{ fmtDrawerMoney(drawerSession.opening_float) }}
          </p>
          <p v-else-if="!drawerOpen" class="text-[11px] text-slate-600">
            {{ t('cashDrawer.noSession') }}
          </p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <RouterLink
            :to="{ name: 'owner-z-report' }"
            class="ui-btn-outline ui-press inline-flex items-center gap-1 px-3 py-1 text-[11px] font-semibold transition-colors"
          >
            {{ t('zReport.navLabel') }}
          </RouterLink>
          <button
            v-if="!drawerOpen"
            type="button"
            class="ui-touch-target inline-flex shrink-0 items-center gap-1 rounded-full border border-emerald-500/50 px-3 py-1 text-[11px] font-semibold text-emerald-300 transition-colors hover:bg-emerald-500/10 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
            :disabled="openingDrawer"
            @click="handleOpenDrawer"
          >
            <svg v-if="openingDrawer" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ openingDrawer ? t('common.loading') : t('cashDrawer.openDrawer') }}
          </button>
        </div>
      </div>

      <!-- Today's snapshot — live from the order store (no heavy fetch) ─────── -->
      <!-- Skeleton while the first orders load -->
      <div v-if="order.ordersLoading && !order.orders.length" class="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-slate-800 bg-slate-800/70 sm:grid-cols-4" aria-hidden="true">
        <div v-for="i in 4" :key="i" class="animate-pulse space-y-2.5 bg-slate-950/60 px-4 py-3.5">
          <div class="h-2.5 w-16 rounded bg-slate-700/60" />
          <div class="h-7 w-20 rounded-lg bg-slate-700/40" />
        </div>
      </div>

      <!-- Today's snapshot — unified stat strip with hairline dividers -->
      <div v-else class="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-slate-800 bg-slate-800/70 sm:grid-cols-4" role="region" :aria-label="t('ownerHome.todayOrders')">
        <!-- Today's orders -->
        <div class="space-y-1.5 bg-slate-950/60 px-4 py-3.5">
          <p class="ui-stat-label">{{ t("ownerHome.todayOrders") }}</p>
          <div class="flex items-end gap-1.5">
            <p class="ui-stat-value text-slate-100">{{ todayStats.count }}</p>
            <span
              v-if="yesterdayStats.count > 0"
              class="mb-1.5 text-[10px] tabular-nums"
              :class="todayStats.count >= yesterdayStats.count ? 'text-emerald-500' : 'text-slate-500'"
            >{{ todayStats.count >= yesterdayStats.count ? '+' : '' }}{{ todayStats.count - yesterdayStats.count }}</span>
          </div>
        </div>

        <!-- Today's revenue -->
        <div class="space-y-1.5 bg-slate-950/60 px-4 py-3.5">
          <p class="ui-stat-label">{{ t("ownerHome.todayRevenue") }}</p>
          <div class="flex items-end gap-1.5">
            <p class="ui-stat-value text-[var(--color-secondary)]">{{ todayStats.revenue }}</p>
            <span
              v-if="yesterdayStats.revenue > 0"
              class="mb-1.5 text-[10px] tabular-nums"
              :class="todayStats.revenueRaw >= yesterdayStats.revenue ? 'text-emerald-500' : 'text-slate-500'"
            >{{ todayStats.revenueRaw >= yesterdayStats.revenue ? '+' : '' }}{{ Math.round((todayStats.revenueRaw - yesterdayStats.revenue) / yesterdayStats.revenue * 100) }}%</span>
          </div>
        </div>

        <!-- Avg ticket today -->
        <div class="space-y-1.5 bg-slate-950/60 px-4 py-3.5">
          <p class="ui-stat-label">{{ t("ownerHome.kpiAvgTicket") }}</p>
          <p class="ui-stat-value text-slate-100">{{ avgTicketLabel }}</p>
        </div>

        <!-- Pending orders — tinted + clickable when there's a queue -->
        <RouterLink
          v-if="todayStats.pending > 0"
          :to="{ name: 'owner-orders' }"
          class="group space-y-1.5 bg-amber-500/10 px-4 py-3.5 transition-colors hover:bg-amber-500/18 focus-visible:outline-none focus-visible:ring-inset focus-visible:ring-2 focus-visible:ring-amber-400/50"
          :aria-label="`${t('ownerOrders.todayPending')}: ${todayStats.pending}`"
        >
          <p class="ui-stat-label flex items-center gap-1">
            {{ t("ownerOrders.todayPending") }}
            <AppIcon name="chevronRight" class="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-60 rtl:scale-x-[-1]" aria-hidden="true" />
          </p>
          <p class="ui-stat-value text-amber-400">{{ todayStats.pending }}</p>
          <p v-if="oldestPendingMinutes !== null" class="mt-0.5 text-[10px] tabular-nums text-amber-300/60">
            {{ t('ownerHome.oldestPending', { min: oldestPendingMinutes }) }}
          </p>
        </RouterLink>
        <div v-else class="space-y-1 bg-slate-950/60 px-4 py-3.5">
          <p class="ui-stat-label">{{ t("ownerOrders.todayPending") }}</p>
          <p class="ui-stat-value text-slate-100">0</p>
          <p class="text-[10px] text-emerald-400/70">{{ t("ownerHome.allClear") }}</p>
        </div>
      </div>

      <!-- Daily revenue goal -->
      <div v-if="goalValue > 0 || editingGoal" class="rounded-2xl border border-slate-800 bg-slate-950/40 px-4 py-3 space-y-2">
        <div class="flex items-center justify-between gap-2">
          <p class="ui-stat-label">{{ t('ownerHome.goalTitle') }}</p>
          <button
            class="text-[11px] font-medium text-slate-500 hover:text-slate-300 transition-colors"
            @click="editingGoal ? cancelGoalEdit() : startGoalEdit()"
          >{{ editingGoal ? t('common.cancel') : t('ownerHome.goalEdit') }}</button>
        </div>
        <template v-if="!editingGoal">
          <div class="relative h-2 w-full overflow-hidden rounded-full bg-slate-800">
            <div
              class="h-full rounded-full transition-all duration-700"
              :class="goalProgress >= 100 ? 'bg-emerald-500' : 'bg-[var(--color-secondary)]'"
              :style="{ width: Math.min(100, goalProgress) + '%' }"
            />
          </div>
          <div class="flex items-center justify-between text-[11px]">
            <span class="text-slate-400 tabular-nums">{{ todayStats.revenue }}</span>
            <span class="font-bold tabular-nums" :class="goalProgress >= 100 ? 'text-emerald-400' : 'text-slate-400'">
              {{ goalProgress >= 100 ? t('ownerHome.goalReached') : `${Math.round(goalProgress)}%` }}
            </span>
            <span class="text-slate-500 tabular-nums">{{ goalFormattedTarget }}</span>
          </div>
        </template>
        <div v-else class="flex items-center gap-2">
          <input
            v-model.number="goalInput"
            type="number"
            min="0"
            step="100"
            :placeholder="t('ownerHome.goalPlaceholder')"
            class="ui-input flex-1 text-sm"
            :disabled="savingGoal"
            @keyup.enter="saveGoal"
            @keyup.escape="cancelGoalEdit"
          />
          <button class="ui-btn-primary shrink-0 px-3 py-2 text-xs" :disabled="savingGoal" @click="saveGoal">
            <svg v-if="savingGoal" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            <span v-else>{{ t('common.save') }}</span>
          </button>
          <button v-if="goalValue > 0" class="shrink-0 text-[11px] text-red-400/80 hover:text-red-400 transition-colors" @click="clearGoal">{{ t('ownerHome.goalClear') }}</button>
        </div>
      </div>
      <button
        v-else
        class="flex w-full items-center justify-between gap-3 rounded-2xl border border-dashed border-slate-800 bg-transparent px-4 py-2.5 text-left transition hover:border-slate-700 ui-press"
        @click="startGoalEdit"
      >
        <span class="text-xs text-slate-600">{{ t('ownerHome.goalNone') }}</span>
        <span class="shrink-0 text-xs font-semibold text-[var(--color-secondary)]/70 hover:text-[var(--color-secondary)]">{{ t('ownerHome.goalSet') }}</span>
      </button>

      <!-- Alerts strip — shown below KPIs, above ratings -->
      <OwnerDashboardAlerts
        :sold-out-count="soldOutCount"
        :ratings-summary="ratingsSummary"
        @reset-complete="soldOutCount = 0"
      />

      <!-- Dish availability — pre-seeded with data from readiness to skip double-fetch -->
      <OwnerDashboardDishPanel
        ref="dishPanelRef"
        :initial-sold-out-count="soldOutCount"
        :preloaded-dishes="preloadedDishesData"
      />

      <!-- Ratings strip — a passive metric, kept below the operational controls -->
      <template v-if="ratingsSummary">
        <RouterLink
          v-if="ratingsSummary.count > 0"
          :to="{ name: 'owner-ratings' }"
          class="ui-surface-lift flex items-center justify-between gap-3 rounded-2xl border border-amber-500/20 bg-amber-500/5 px-4 py-3 transition hover:border-amber-500/35 hover:bg-amber-500/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
          :aria-label="t('ownerHome.viewAllRatings')"
        >
          <div class="flex items-center gap-3">
            <span class="text-amber-400 text-xl leading-none" aria-hidden="true">★</span>
            <div class="flex items-baseline gap-1.5">
              <span class="text-sm font-bold text-white tabular-nums">{{ ratingsSummary.average !== null ? ratingsSummary.average.toFixed(1) : "—" }}</span>
              <span class="text-xs text-slate-500">/ 5 · {{ ratingsSummary.count }} {{ t("ownerHome.avgRating").toLowerCase() }}</span>
            </div>
          </div>
          <span class="flex items-center gap-1 text-xs font-semibold text-amber-400/80">
            {{ t("ownerHome.viewAllRatings") }}
            <AppIcon name="chevronRight" class="h-3.5 w-3.5 rtl:scale-x-[-1]" aria-hidden="true" />
          </span>
        </RouterLink>
        <div v-else class="flex items-center gap-2.5 rounded-2xl border border-slate-800 bg-slate-950/30 px-4 py-3">
          <span class="text-sm text-slate-700" aria-hidden="true">★</span>
          <span class="text-xs text-slate-600">{{ t("ownerHome.noRatingsYet") }}</span>
        </div>
      </template>
      <div v-else class="h-11 animate-pulse rounded-2xl bg-slate-800/30" aria-hidden="true" />

      <!-- Today's reservations — lazy-fetched after ratings ───────────────── -->
      <RouterLink
        v-if="todayReservations !== null"
        :to="{ name: 'owner-reservations' }"
        class="ui-surface-lift flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
        :class="todayReservations > 0 ? 'border-sky-500/25 bg-sky-500/5 hover:border-sky-500/40 hover:bg-sky-500/8' : 'border-slate-700/60 bg-slate-950/30 hover:border-slate-600'"
        :aria-label="`${t('ownerHome.todayReservations')}: ${todayReservations}`"
      >
        <div class="flex items-center gap-3">
          <svg
            viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"
            class="h-4 w-4 shrink-0 flex-none"
            :class="todayReservations > 0 ? 'text-sky-400' : 'text-slate-600'"
            aria-hidden="true"
          >
            <rect x="3" y="4" width="14" height="14" rx="2" />
            <path d="M3 9h14M7 2v4M13 2v4" />
          </svg>
          <div class="flex items-baseline gap-1.5">
            <span class="text-sm font-bold tabular-nums" :class="todayReservations > 0 ? 'text-white' : 'text-slate-400'">{{ todayReservations }}</span>
            <span class="text-xs text-slate-500">{{ t("ownerHome.todayReservations").toLowerCase() }}</span>
          </div>
          <span v-if="todayReservationsNew > 0" class="rounded-full bg-sky-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-sky-300">{{ todayReservationsNew }} {{ t("ownerOrders.statusPending").toLowerCase() }}</span>
        </div>
        <span class="flex items-center gap-0.5 text-[11px] font-semibold" :class="todayReservations > 0 ? 'text-sky-400/80' : 'text-slate-600'">
          {{ t("ownerHome.viewReservations") }}
          <AppIcon name="chevronRight" class="h-3.5 w-3.5 rtl:scale-x-[-1]" aria-hidden="true" />
        </span>
      </RouterLink>
      <div v-else-if="todayReservations === null" class="h-11 animate-pulse rounded-2xl bg-slate-800/30" aria-hidden="true" />

      <!-- Quick actions (Analytics lives in the top nav now, so it's not duplicated here) -->
      <div class="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:gap-2.5">
        <RouterLink :to="{ name: 'owner-menu-builder' }" class="ui-btn-primary ui-press col-span-2 w-full gap-2 px-5 py-2.5 text-sm sm:w-auto">
          <AppIcon name="menu" class="owner-home-btn-icon" aria-hidden="true" />
          {{ t("ownerHome.openMenuBuilder") }}
        </RouterLink>
        <RouterLink to="/menu" class="ui-btn-outline ui-press w-full gap-2 px-4 py-2 text-xs sm:w-auto">
          <AppIcon name="eye" class="owner-home-btn-icon" aria-hidden="true" />
          {{ t("ownerLayout.publicPreview") }}
        </RouterLink>
        <button
          class="ui-btn-outline ui-press w-full gap-2 px-4 py-2 text-xs transition-colors sm:w-auto"
          :class="copied ? 'border-emerald-500/50 text-emerald-300' : ''"
          @click="copyMenuUrl"
        >
          <AppIcon :name="copied ? 'check' : 'copy'" class="owner-home-btn-icon" aria-hidden="true" />
          {{ copied ? t("ownerHome.menuUrlCopied") : t("ownerHome.copyPublicUrl") }}
        </button>
        <button class="ui-btn-outline ui-press col-span-2 w-full gap-2 px-4 py-2 text-xs sm:w-auto" @click="manualRefresh">
          <AppIcon name="refresh" class="owner-home-btn-icon" aria-hidden="true" />
          {{ t("common.refresh") }}
        </button>
        <!-- High-frequency daily destination kept here: Availability. Kitchen, Tables & QR,
             and Z-Report are reachable via OwnerLayout nav/dock/settings, so they are not
             duplicated in this quick-actions grid. -->
        <button
          class="ui-btn-outline ui-press col-span-2 w-full gap-2 px-4 py-2 text-xs sm:w-auto"
          @click="openAvailabilityPanel"
        >
          <AppIcon name="eye" class="owner-home-btn-icon" aria-hidden="true" />
          {{ t("ownerHome.dishAvailability") }}
        </button>
      </div>
    </article>

    <!-- ── READINESS: independent fetch for categories + dishes ─────────────── -->
    <div class="ui-reveal" style="--ui-delay: 40ms">
      <OwnerDashboardReadiness ref="readinessRef" @loaded="onReadinessLoaded" />
    </div>

    <!-- ── LIVE ORDERS: from order store ───────────────────────────────────── -->
    <article class="ui-command-deck ui-reveal space-y-4 p-4 sm:p-5" style="--ui-delay: 80ms">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="space-y-0.5">
          <p class="ui-kicker">{{ t("ownerHome.kicker") }}</p>
          <h2 class="inline-flex items-center gap-2 text-base font-semibold tracking-tight text-white">
            <AppIcon name="cart" class="owner-home-section-icon" aria-hidden="true" />
            <span>{{ t("ownerHome.liveOrders") }}</span>
            <span v-if="order.ordersLoading" class="ui-live-dot ms-0.5 bg-slate-500" aria-hidden="true" />
          </h2>
        </div>
        <RouterLink :to="{ name: 'owner-orders' }" class="ui-btn-outline px-3 py-1.5 text-xs">
          {{ t("ownerHome.viewAllOrders") }}
        </RouterLink>
      </div>

      <!-- New-order flash banner -->
      <Transition name="ui-fade">
        <div
          v-if="newOrderFlash"
          class="flex items-center gap-2.5 rounded-xl border border-amber-500/50 bg-amber-500/12 px-4 py-2.5"
          role="alert"
          aria-live="assertive"
        >
          <span class="relative inline-flex shrink-0" aria-hidden="true">
            <span class="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-amber-400 opacity-70" />
            <span class="relative inline-flex h-2 w-2 rounded-full bg-amber-400" />
          </span>
          <p class="flex-1 text-sm font-semibold text-amber-200">{{ t('ownerHome.newOrderArrived') }}</p>
          <RouterLink :to="{ name: 'owner-orders' }" class="text-xs font-semibold text-amber-300 underline hover:no-underline">{{ t('ownerHome.viewAllOrders') }}</RouterLink>
        </div>
      </Transition>

      <!-- Status summary chips -->
      <div class="flex flex-wrap gap-2" aria-live="polite" aria-atomic="true">
        <div
          class="flex items-center gap-2.5 rounded-2xl border px-3.5 py-2.5 transition-colors"
          :class="pendingOrders.length ? 'border-amber-500/60 bg-amber-500/10' : 'border-slate-700 bg-slate-900/40'"
        >
          <span class="text-xl font-bold tabular-nums" :class="pendingOrders.length ? 'text-amber-300' : 'text-slate-400'">{{ pendingOrders.length }}</span>
          <span class="text-xs font-medium" :class="pendingOrders.length ? 'text-amber-200' : 'text-slate-500'">{{ t("ownerOrders.statusPending") }}</span>
          <span v-if="pendingOrders.length" class="ui-live-dot bg-amber-400" aria-hidden="true" />
        </div>
        <div class="flex items-center gap-2.5 rounded-2xl border border-slate-700 bg-slate-900/40 px-3.5 py-2.5">
          <span class="text-xl font-bold tabular-nums text-slate-300">{{ activeOrders.length }}</span>
          <span class="text-xs font-medium text-slate-500">{{ t("ownerHome.inProgress") }}</span>
        </div>
        <div
          v-if="!pendingOrders.length && !activeOrders.length && recentOrders.length"
          class="flex items-center gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/8 px-3.5 py-2.5"
        >
          <AppIcon name="check" class="h-3.5 w-3.5 text-emerald-400" aria-hidden="true" />
          <span class="text-xs font-medium text-emerald-300/70">{{ t("ownerHome.allClear") }}</span>
        </div>
      </div>

      <!-- Upcoming / advance orders strip — scheduled or near-due pre-orders so a
           pre-ordered lunch isn't invisible until it's late. -->
      <div v-if="upcoming.length" class="space-y-2">
        <p class="ui-kicker inline-flex items-center gap-1.5">
          <span aria-hidden="true">🗓️</span>{{ t("ownerHome.upcomingTitle") }}
        </p>
        <div
          v-for="o in upcoming"
          :key="o.id"
          class="flex items-center justify-between gap-3 rounded-xl border px-3.5 py-2.5 text-xs transition-colors"
          :class="upcomingMinutes(o) <= 0
            ? 'border-violet-500/50 bg-violet-500/10'
            : 'border-slate-700 bg-slate-950/40'"
        >
          <div class="flex min-w-0 items-center gap-2.5">
            <span class="font-mono font-bold tabular-nums text-slate-100">{{ o.order_number }}</span>
            <span v-if="o.fulfillment_type" class="hidden text-slate-400 sm:inline">{{ fulfillmentLabel(o) }}</span>
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
                ? t('ownerHome.upcomingDueNow')
                : t('ownerHome.upcomingFiresIn', { min: upcomingMinutes(o) }) }}
            </span>
          </div>
          <button
            v-if="o.status === 'scheduled'"
            type="button"
            class="ui-press shrink-0 rounded-full border border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/10 px-3 py-1 text-[11px] font-semibold text-[var(--color-secondary)] transition-colors hover:bg-[var(--color-secondary)]/20 disabled:opacity-50"
            :disabled="releasingId === o.id"
            @click="releaseUpcoming(o)"
          >
            {{ releasingId === o.id ? t('common.loading') : t('ownerHome.upcomingStartNow') }}
          </button>
        </div>
      </div>

      <!-- Recent orders list -->
      <div v-if="recentOrders.length" class="space-y-2">
        <p class="ui-kicker">{{ t("ownerHome.recentOrdersList") }}</p>
        <RouterLink
          v-for="(o, index) in recentOrders"
          :key="o.id"
          :to="{ name: 'owner-orders', query: { q: o.order_number } }"
          class="ui-reveal flex items-center justify-between gap-3 rounded-xl border bg-slate-950/40 px-3.5 py-2.5 text-xs transition-colors hover:bg-slate-900/60"
          :class="isUrgentOrder(o)
            ? 'border-red-500/50 bg-red-500/5 hover:border-red-500/70'
            : ['pending','confirmed','preparing','ready'].includes(o.status)
              ? 'border-slate-700 hover:border-slate-600'
              : 'border-slate-800 hover:border-slate-700'"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
          :title="isUrgentOrder(o) ? t('ownerHome.orderUrgentTitle', { min: Math.round((Date.now() - new Date(o.created_at).getTime()) / 60000) }) : undefined"
        >
          <div class="flex min-w-0 items-center gap-2.5">
            <span class="font-mono font-bold tabular-nums" :class="isUrgentOrder(o) ? 'text-red-300' : 'text-slate-100'">{{ o.order_number }}</span>
            <span class="rounded-full px-2 py-0.5 font-semibold" :class="orderStatusClass(o.status)">{{ orderStatusLabel(o.status) }}</span>
            <span v-if="o.fulfillment_type" class="hidden text-slate-400 sm:inline">{{ fulfillmentLabel(o) }}</span>
            <!-- Urgency dot — shown when order is overdue -->
            <span v-if="isUrgentOrder(o)" class="ui-live-dot bg-red-400" aria-hidden="true" />
          </div>
          <div class="flex shrink-0 items-center gap-3 tabular-nums">
            <span class="font-semibold text-[var(--color-secondary)]">{{ formatOrderTotal(o) }}</span>
            <span :class="isUrgentOrder(o) ? 'font-semibold text-red-400' : 'text-slate-500'">{{ formatTimeAgo(o.created_at) }}</span>
          </div>
        </RouterLink>
      </div>
      <div v-else-if="!order.ordersLoading" class="ui-empty-state text-center space-y-2.5">
        <p class="text-sm font-semibold text-slate-100">{{ t("ownerHome.noOrdersYet") }}</p>
        <p class="text-xs text-slate-500">{{ t("ownerHome.openToggleHint") }}</p>
        <button
          class="inline-flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-800/50 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-slate-600 hover:text-slate-100"
          @click="copyMenuUrl"
        >
          <AppIcon name="link" class="h-3 w-3 shrink-0" aria-hidden="true" />
          {{ copied ? t("ownerHome.menuUrlCopied") : t("ownerHome.noOrdersShareHint") }}
        </button>
      </div>
    </article>

    <!-- ── PLAN CARD ────────────────────────────────────────────────────────── -->
    <article class="ui-command-deck ui-reveal p-4 sm:p-5" style="--ui-delay: 160ms">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t("ownerHome.planSection") }}</p>
          <h2 class="inline-flex items-center gap-2 text-base font-semibold tracking-tight">
            <AppIcon name="card" class="owner-home-section-icon" aria-hidden="true" />
            <span class="text-white">{{ tenant.entitlements?.tier_name || tenant.meta?.plan?.name || "Basic" }}</span>
          </h2>
        </div>
        <RouterLink :to="{ name: 'owner-profile', query: { tab: 'billing' } }" class="ui-btn-outline px-3 py-1.5 text-xs">
          {{ t("ownerBilling.manageBilling") }}
          <AppIcon name="arrowRight" class="ms-1 inline h-3.5 w-3.5 rtl:scale-x-[-1]" aria-hidden="true" />
        </RouterLink>
      </div>
    </article>

  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import OwnerDashboardAlerts from "../components/OwnerDashboardAlerts.vue";
import OwnerDashboardReadiness from "../components/OwnerDashboardReadiness.vue";
import OwnerDashboardDishPanel from "../components/OwnerDashboardDishPanel.vue";
import OwnerNextAction from "../components/OwnerNextAction.vue";
import BusyModeControl from "../components/BusyModeControl.vue";
import { useI18n } from "../composables/useI18n";
import { useNowTicker } from "../composables/useNowTicker";
import { upcomingOrders, minutesUntilScheduled } from "../lib/ownerLiveFocus";
import api from "../lib/api";
import { bustCache } from "../lib/staleCache";
import { useOrderStore } from "../stores/order";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

// Explicit name so <KeepAlive :exclude> in OwnerLayout reliably skips this page
// (it polls / has lifecycle cleanup and must mount & unmount normally).
defineOptions({ name: "OwnerHome" });

const tenant = useTenantStore();
const order = useOrderStore();
const toast = useToastStore();
const router = useRouter();
const { t, formatNumber, currentLocale } = useI18n();

// ── Quick-action: open and scroll to the dish availability panel ──────────────
const dishPanelRef = ref(null);
const openAvailabilityPanel = () => {
  dishPanelRef.value?.openAndScroll();
  nextTick(() => {
    dishPanelRef.value?.$el?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
};

// ── Ref to the deferred readiness component (for manual refresh) ──────────────
const readinessRef = ref(null);

// ── Data from OwnerDashboardReadiness (emitted after its dishes/categories fetch) ─
const soldOutCount = ref(0);
const preloadedDishesData = ref([]); // passed to dish panel to skip a second fetch

const onReadinessLoaded = ({ soldOutCount: n, dishesData }) => {
  soldOutCount.value = n ?? 0;
  if (dishesData) preloadedDishesData.value = dishesData;
};

// ── Ratings — fetched independently after first paint ────────────────────────
const ratingsSummary = ref(null); // null = loading, {} = loaded

const fetchRatings = async () => {
  try {
    const { data } = await api.get("/owner/ratings/", { timeout: 5000 });
    ratingsSummary.value = { count: data?.count ?? 0, average: data?.average ?? null };
  } catch {
    ratingsSummary.value = { count: 0, average: null };
  }
};

// ── Today's reservations — fetched lazily after ratings ──────────────────────
const todayReservations = ref(null);   // null = loading skeleton
const todayReservationsNew = ref(0);

const fetchTodayReservations = async () => {
  const today = new Date().toISOString().slice(0, 10);
  try {
    const { data } = await api.get("/owner/reservations/", {
      params: { booked_for_date: today, page_size: 1 },
      timeout: 5000,
    });
    todayReservations.value = data?.pagination?.total ?? 0;
    todayReservationsNew.value = data?.counts?.new ?? 0;
  } catch {
    todayReservations.value = 0;
  }
};

// ── Profile-derived state ─────────────────────────────────────────────────────
const profile = computed(() => tenant.meta?.profile || {});
const published = computed(() => profile.value?.is_menu_published === true);
const isOpen = computed(() => profile.value?.is_open !== false);
const togglingOpen = ref(false);
// Quick operational toggles (owner controls; delivery PRICING is admin-only).
const acceptingDelivery = computed(() => profile.value?.delivery_enabled !== false);
const menuActive = computed(() => profile.value?.is_menu_temporarily_disabled !== true);
const togglingDelivery = ref(false);
const togglingMenu = ref(false);

// ── Daily revenue goal ─────────────────────────────────────────────────────────
const goalInput = ref(0);
const editingGoal = ref(false);
const savingGoal = ref(false);

const goalValue = computed(() => parseFloat(profile.value.daily_revenue_goal || 0) || 0);
const goalCurrency = computed(() => order.orders.find((o) => o.currency)?.currency || "MAD");
const goalProgress = computed(() => {
  if (!goalValue.value) return 0;
  return (todayStats.value.revenueRaw / goalValue.value) * 100;
});
const goalFormattedTarget = computed(() => {
  if (!goalValue.value) return "—";
  try {
    return formatNumber(goalValue.value, { style: "currency", currency: goalCurrency.value, maximumFractionDigits: 0 });
  } catch {
    return goalValue.value.toFixed(0);
  }
});

const startGoalEdit = () => { goalInput.value = goalValue.value || 0; editingGoal.value = true; };
const cancelGoalEdit = () => { editingGoal.value = false; };
const saveGoal = async () => {
  const val = Number(goalInput.value) || null;
  if (val !== null && val < 0) return;
  savingGoal.value = true;
  try {
    await api.patch("/profile/", { daily_revenue_goal: val });
    tenant.mergeProfile({ daily_revenue_goal: val });
    editingGoal.value = false;
    toast.show(t("ownerHome.goalSaved"), "success");
  } catch {
    toast.show(t("ownerHome.goalSaveFailed"), "error");
  } finally {
    savingGoal.value = false;
  }
};
const clearGoal = async () => { goalInput.value = 0; await saveGoal(); };

const canCheckout = computed(() => tenant.entitlements?.can_checkout === true);
const canWhatsapp = computed(() => tenant.entitlements?.can_whatsapp_order === true);
const planModeLabel = computed(() => {
  if (canCheckout.value) return t("ownerHome.checkoutEnabled");
  if (canWhatsapp.value) return t("ownerHome.whatsappEnabled");
  return t("ownerHome.browseOnly");
});

// ── Open/Closed toggle ────────────────────────────────────────────────────────
const toggleOpen = async () => {
  if (togglingOpen.value) return;
  togglingOpen.value = true;
  const newValue = !isOpen.value;
  try {
    await api.patch("/profile/", { is_open: newValue });
    tenant.mergeProfile({ is_open: newValue });
    bustCache("meta");
    toast.show(newValue ? t("ownerHome.openedToast") : t("ownerHome.closedToast"), newValue ? "success" : "info");
  } catch {
    toast.show(t("ownerHome.toggleFailed"), "error");
  } finally {
    togglingOpen.value = false;
  }
};

// ── Quick toggle: accepting delivery orders (operational; pricing is admin-only) ─
const toggleDelivery = async () => {
  if (togglingDelivery.value) return;
  togglingDelivery.value = true;
  const newValue = !acceptingDelivery.value;
  try {
    await api.patch("/profile/", { delivery_enabled: newValue });
    tenant.mergeProfile({ delivery_enabled: newValue });
    bustCache("meta");
    toast.show(newValue ? t("ownerHome.deliveryResumedToast") : t("ownerHome.deliveryPausedToast"), newValue ? "success" : "info");
  } catch {
    toast.show(t("ownerHome.toggleFailed"), "error");
  } finally {
    togglingDelivery.value = false;
  }
};

// ── Quick toggle: menu active / temporarily disabled ────────────────────────────
const toggleMenu = async () => {
  if (togglingMenu.value) return;
  togglingMenu.value = true;
  const nextActive = !menuActive.value; // store the inverse on is_menu_temporarily_disabled
  try {
    await api.patch("/profile/", { is_menu_temporarily_disabled: !nextActive });
    tenant.mergeProfile({ is_menu_temporarily_disabled: !nextActive });
    bustCache("meta");
    toast.show(nextActive ? t("ownerHome.menuEnabledToast") : t("ownerHome.menuDisabledToast"), nextActive ? "success" : "info");
  } catch {
    toast.show(t("ownerHome.toggleFailed"), "error");
  } finally {
    togglingMenu.value = false;
  }
};

// ── Today's order stats — derived from the order store ────────────────────────
const todayStats = computed(() => {
  const today = new Date().toDateString();
  const todayOrders = order.orders.filter((o) => new Date(o.created_at).toDateString() === today);
  const revenue = todayOrders.reduce((s, o) => s + (Number(o.total) || 0), 0);
  const currency = todayOrders.find((o) => o.currency)?.currency || "MAD";
  let revenueLabel = "";
  try {
    revenueLabel = formatNumber(revenue, { style: "currency", currency, notation: "compact", maximumFractionDigits: 0 });
  } catch {
    revenueLabel = `${currency} ${Math.floor(revenue)}`;
  }
  return {
    count: todayOrders.length,
    revenue: revenueLabel,
    revenueRaw: revenue,
    pending: todayOrders.filter((o) => o.status === "pending").length,
  };
});

// Average ticket for today
const avgTicketLabel = computed(() => {
  const { count, revenueRaw } = todayStats.value;
  if (!count) return "—";
  const avg = revenueRaw / count;
  const currency = order.orders.find((o) => o.currency)?.currency || "MAD";
  try { return formatNumber(avg, { style: "currency", currency, maximumFractionDigits: 0 }); }
  catch { return `${currency} ${Math.round(avg)}`; }
});

const yesterdayStats = computed(() => {
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const yStr = yesterday.toDateString();
  const yOrders = order.orders.filter((o) => new Date(o.created_at).toDateString() === yStr);
  return {
    count: yOrders.length,
    revenue: yOrders.reduce((s, o) => s + (Number(o.total) || 0), 0),
  };
});

// ── Live orders ───────────────────────────────────────────────────────────────
// New-order flash: track known IDs and show a brief banner when a new pending order arrives.
const homeKnownIds = new Set();
const newOrderFlash = ref(false);
let newOrderFlashTimer = null;
const watchHomeOrders = (orders) => {
  if (!Array.isArray(orders) || !homeKnownIds.size) {
    orders?.forEach((o) => homeKnownIds.add(o.id));
    return;
  }
  const hasNew = orders.some((o) => o.status === "pending" && !homeKnownIds.has(o.id));
  orders.forEach((o) => homeKnownIds.add(o.id));
  if (hasNew) {
    newOrderFlash.value = true;
    if (newOrderFlashTimer) clearTimeout(newOrderFlashTimer);
    newOrderFlashTimer = setTimeout(() => { newOrderFlash.value = false; }, 6000);
  }
};
watch(() => order.orders, watchHomeOrders, { deep: false });

const pendingOrders = computed(() => order.orders.filter((o) => o.status === "pending"));
const oldestPendingMinutes = computed(() => {
  if (!pendingOrders.value.length) return null;
  const oldest = pendingOrders.value.reduce((min, o) => {
    const ts = new Date(o.created_at).getTime();
    return ts < min ? ts : min;
  }, Infinity);
  return Math.max(0, Math.round((Date.now() - oldest) / 60000));
});
const activeOrders = computed(() => order.orders.filter((o) => ["confirmed", "preparing", "ready"].includes(o.status)));
const ORDER_STATUS_PRIORITY = { pending: 0, confirmed: 1, preparing: 2, ready: 3, completed: 4, cancelled: 5 };
const recentOrders = computed(() =>
  [...order.orders]
    .sort((a, b) => {
      const sp = (ORDER_STATUS_PRIORITY[a.status] ?? 9) - (ORDER_STATUS_PRIORITY[b.status] ?? 9);
      if (sp !== 0) return sp;
      return new Date(b.created_at) - new Date(a.created_at);
    })
    .slice(0, 6)
);

// ── Upcoming / advance (scheduled) orders ─────────────────────────────────────
// Surface scheduled or near-due pre-orders in the live flow with a fires-in
// countdown + a Start-now release. Recomputes off the shared ticker.
const { now: focusNow } = useNowTicker();
const upcoming = computed(() => upcomingOrders(order.orders, focusNow.value));
const upcomingMinutes = (o) => minutesUntilScheduled(o, focusNow.value);

const releasingId = ref(null);
const releaseUpcoming = async (o) => {
  if (releasingId.value) return;
  releasingId.value = o.id;
  try {
    // Release a scheduled advance order to the kitchen now (scheduled → pending).
    await order.updateOrderStatus(o.id, { status: "pending" });
    toast.show(t("ownerHome.upcomingReleased", { order: o.order_number }), "success");
  } catch {
    toast.show(t("ownerOrders.updateFailed"), "error");
  } finally {
    releasingId.value = null;
  }
};

// ── Focus mode: single next-action surface for a solo owner ───────────────────
// Defaults ON for new accounts (no explicit preference stored yet) so the
// simplified action-first UI is the first thing a new owner sees. Once the
// owner toggles it off via the chip or the opt-out link, that choice is persisted.
const FOCUS_KEY = typeof window === "undefined" ? "owner:focus" : `owner:focus:${window.location.hostname}`;
const focusMode = ref((() => {
  try {
    const stored = localStorage.getItem(FOCUS_KEY);
    // null → never explicitly set → default ON (new owner experience)
    if (stored === null) return true;
    return stored === "on";
  } catch { return true; }
})());
const toggleFocusMode = () => {
  focusMode.value = !focusMode.value;
  try { localStorage.setItem(FOCUS_KEY, focusMode.value ? "on" : "off"); } catch { /* ignore */ }
};

// Orders the owner has skipped this session — removed from the focus candidate
// pool so "Next" can cycle past one to the following action.
const skippedFocusIds = ref(new Set());
const focusOrders = computed(() =>
  order.orders.filter((o) => !skippedFocusIds.value.has(o.id)),
);
const skipNextAction = (action) => {
  if (action?.order?.id != null) {
    skippedFocusIds.value = new Set(skippedFocusIds.value).add(action.order.id);
  }
};

const focusBusy = ref(false);
const handleNextAction = async (action) => {
  if (focusBusy.value) return;
  const o = action?.order;
  focusBusy.value = true;
  try {
    if (action.kind === "confirm") {
      await order.updateOrderStatus(o.id, { status: "confirmed" });
      toast.show(t("ownerOrders.updated"), "success");
    } else if (action.kind === "dueSoon") {
      await order.updateOrderStatus(o.id, { status: o.status === "scheduled" ? "pending" : "preparing" });
      toast.show(t("ownerOrders.updated"), "success");
    } else if (action.kind === "handoff") {
      const next = o.fulfillment_type === "delivery" ? "out_for_delivery" : "completed";
      await order.updateOrderStatus(o.id, { status: next });
      toast.show(t("ownerOrders.updated"), "success");
    } else if (action.kind === "overdue") {
      await order.updateOrderStatus(o.id, { status: "ready" });
      toast.show(t("ownerOrders.updated"), "success");
    } else if (action.kind === "fire") {
      // Coursing fires from the kitchen view; route the owner there to fire it.
      await router.push({ name: "owner-kitchen" });
    } else if (action.kind === "soldOut") {
      await api.post("/owner/dishes/reset-availability/");
      soldOutCount.value = 0;
      toast.show(t("ownerHome.allClear"), "success");
    }
  } catch {
    toast.show(t("ownerOrders.updateFailed"), "error");
  } finally {
    focusBusy.value = false;
  }
};

// ── Order helpers ─────────────────────────────────────────────────────────────
// An order is "urgent" when it has been in a live status longer than expected:
//   pending   > 15 min — owner hasn't confirmed yet (customer is waiting)
//   confirmed > 30 min — kitchen may be stuck
const URGENT_THRESHOLDS_MIN = { pending: 15, confirmed: 30 };
const isUrgentOrder = (o) => {
  const threshold = URGENT_THRESHOLDS_MIN[o.status];
  if (!threshold || !o.created_at) return false;
  return (Date.now() - new Date(o.created_at).getTime()) / 60000 >= threshold;
};

const orderStatusClass = (s) => ({
  pending: "bg-amber-500/20 text-amber-200 border border-amber-500/30",
  confirmed: "bg-sky-500/20 text-sky-200 border border-sky-500/30",
  preparing: "bg-orange-500/20 text-orange-200 border border-orange-500/30",
  ready: "bg-emerald-500/20 text-emerald-200 border border-emerald-500/30",
  completed: "bg-slate-700 text-slate-300",
  cancelled: "bg-red-500/20 text-red-300 border border-red-500/30",
}[s] || "bg-slate-700 text-slate-300");

const orderStatusLabel = (s) => ({
  pending: t("ownerOrders.statusPending"),
  confirmed: t("ownerOrders.statusConfirmed"),
  preparing: t("ownerOrders.statusPreparing"),
  ready: t("ownerOrders.statusReady"),
  completed: t("ownerOrders.statusCompleted"),
  cancelled: t("ownerOrders.statusCancelled"),
}[s] || s);

const fulfillmentLabel = (o) => {
  if (o.fulfillment_type === "table") return t("ownerOrders.fulfillmentTable", { table: o.table_label || "?" });
  if (o.fulfillment_type === "delivery") return t("ownerOrders.fulfillmentDelivery");
  if (o.fulfillment_type === "pickup") return t("ownerOrders.fulfillmentPickup");
  return "";
};

const formatOrderTotal = (o) => {
  try { return formatNumber(Number(o.total) || 0, { style: "currency", currency: o.currency || "MAD" }); }
  catch { return `${o.currency} ${Number(o.total).toFixed(2)}`; }
};

const formatTimeAgo = (iso) => {
  if (!iso) return "";
  const diffMin = Math.floor((Date.now() - new Date(iso)) / 60000);
  if (diffMin < 1) return t("ownerOrders.justNow");
  if (diffMin < 60) return `${diffMin}m`;
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)}h`;
  return new Intl.DateTimeFormat(currentLocale.value, { dateStyle: "short" }).format(new Date(iso));
};

// ── Cash drawer (default-preserving) ─────────────────────────────────────────
// drawerLoaded starts false; once the /current/ call returns we show the card.
// Tenants who never open a drawer get {open: false} → the card stays hidden
// until the first open, so existing UX is unchanged.
const drawerLoaded = ref(false);
const drawerOpen = ref(false);
const drawerSession = ref(null);
const openingDrawer = ref(false);

const fmtDrawerMoney = (val) => {
  const n = Number(val) || 0;
  const curr = order.orders.find((o) => o.currency)?.currency || "MAD";
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: curr, minimumFractionDigits: 2 }).format(n);
  } catch {
    return `${curr} ${n.toFixed(2)}`;
  }
};

const fetchDrawerState = async () => {
  try {
    const { data } = await api.get("/owner/drawer/current/", { timeout: 5000 });
    drawerOpen.value = data.open === true;
    drawerSession.value = data.session || null;
    // Only show the card if the drawer has ever been used OR is currently open.
    // A fresh tenant (no session) gets open:false + session:null → card stays hidden.
    if (drawerOpen.value || drawerSession.value) {
      drawerLoaded.value = true;
    }
  } catch {
    // Silently ignore — the drawer card simply won't appear (no regression).
  }
};

const handleOpenDrawer = async () => {
  if (openingDrawer.value) return;
  openingDrawer.value = true;
  try {
    const { data } = await api.post("/owner/drawer/open/", { opening_float: "0.00" });
    drawerOpen.value = true;
    drawerSession.value = data;
    drawerLoaded.value = true;
    toast.show(t("cashDrawer.openSuccess"), "success");
  } catch (err) {
    const code = err?.response?.data?.code;
    if (code === "already_open") {
      // Race condition: another tab opened it — just refresh the state.
      await fetchDrawerState();
    } else {
      toast.show(err?.response?.data?.detail || t("cashDrawer.openError"), "error");
    }
  } finally {
    openingDrawer.value = false;
  }
};

// ── Copy URL ──────────────────────────────────────────────────────────────────
const copied = ref(false);
const menuUrl = computed(() => (typeof window === "undefined" ? "/menu" : `${window.location.origin}/menu`));
let copyResetTimer = null;

const copyMenuUrl = async () => {
  try {
    await navigator.clipboard.writeText(menuUrl.value);
    copied.value = true;
    if (copyResetTimer !== null) clearTimeout(copyResetTimer);
    copyResetTimer = setTimeout(() => { copied.value = false; copyResetTimer = null; }, 1800);
  } catch {
    toast.show(t("ownerHome.copyFailed"), "error");
  }
};

// ── Manual refresh ────────────────────────────────────────────────────────────
const manualRefresh = () => {
  void order.fetchOrders("", { silent: false });
  void tenant.fetchMeta();
  void fetchRatings();
  void fetchTodayReservations();
  void fetchDrawerState();
  // Re-fetch readiness data (counts, sold-out count) so the readiness card and
  // the alerts that depend on it stay in sync.
  readinessRef.value?.load();
};

// ── Background order poll ─────────────────────────────────────────────────────
const POLL_INTERVAL_S = 30;
let pollTimer = null;

const onVisibilityChange = () => {
  if (typeof document !== "undefined" && document.visibilityState === "visible") {
    void order.fetchOrders("", { silent: true });
  }
};

// ── Mount: critical path first, deferred work via nextTick ────────────────────
onMounted(async () => {
  // 1. Critical path — both calls hit the store cache if data is fresh.
  //    No global loading flag: each section has its own skeleton.
  await Promise.all([
    tenant.fetchMeta(),
    order.fetchOrders(),
  ]);

  // 2. Deferred — run after the first paint so the critical sections are visible
  //    before these additional calls hit the network.
  nextTick(() => {
    void fetchRatings();
    void fetchTodayReservations();
    void fetchDrawerState();
  });

  // 3. Background poll setup
  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", onVisibilityChange);
  }
  pollTimer = setInterval(() => {
    if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
    void order.fetchOrders("", { silent: true });
  }, POLL_INTERVAL_S * 1000);
});

onUnmounted(() => {
  clearInterval(pollTimer);
  if (newOrderFlashTimer) clearTimeout(newOrderFlashTimer);
  if (copyResetTimer !== null) clearTimeout(copyResetTimer);
  if (typeof document !== "undefined") {
    document.removeEventListener("visibilitychange", onVisibilityChange);
  }
});
</script>

<style scoped>
.owner-home-btn-icon { width: 0.9rem; height: 0.9rem; }
.owner-home-section-icon { width: 1rem; height: 1rem; color: var(--color-secondary); }
</style>
