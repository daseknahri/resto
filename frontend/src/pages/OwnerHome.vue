<template>
  <section class="space-y-4 pb-24 sm:space-y-5 sm:pb-6">
    <article class="ui-workspace-stage ui-fade-up space-y-4 p-3 sm:space-y-4 sm:p-4 md:p-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="space-y-1.5">
          <p class="ui-kicker">{{ t("ownerHome.kicker") }}</p>
          <h2 class="ui-page-title ui-display text-[1.42rem] leading-tight sm:text-[2rem]">{{ t("ownerHome.title") }}</h2>
        </div>
        <div class="ui-scroll-row max-w-full sm:max-w-none">
          <span class="ui-chip-strong">{{ published ? t("ownerHome.published") : t("ownerHome.draft") }}</span>
          <span class="ui-chip">{{ planModeLabel }}</span>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-2 xl:grid-cols-4">
        <template v-if="loading">
          <div v-for="i in 4" :key="i" class="ui-admin-subcard animate-pulse space-y-1.5">
            <div class="h-2.5 w-14 rounded bg-slate-700/60" />
            <div class="mt-1 h-7 w-10 rounded bg-slate-700/40" />
          </div>
        </template>
        <template v-else>
          <article class="ui-admin-subcard space-y-1.5">
            <p class="ui-stat-label">{{ t("ownerHome.readiness") }}</p>
            <p class="ui-stat-value text-[var(--color-secondary)]">{{ readinessScore }}%</p>
          </article>
          <article class="ui-admin-subcard space-y-1.5">
            <p class="ui-stat-label">{{ t("common.categories") }}</p>
            <p class="ui-stat-value text-slate-100">{{ categoriesCount }}</p>
          </article>
          <article class="ui-admin-subcard space-y-1.5">
            <p class="ui-stat-label">{{ t("common.dishes") }}</p>
            <p class="ui-stat-value text-slate-100">{{ dishesCount }}</p>
          </article>
          <article
            class="ui-admin-subcard space-y-1.5 transition-colors"
            :class="soldOutCount > 0 ? 'cursor-pointer hover:border-amber-500/40' : ''"
            :title="soldOutCount > 0 ? t('ownerHome.dishAvailability') : ''"
            @click="soldOutCount > 0 && (dishAvailOpen = true)"
          >
            <p class="ui-stat-label">{{ t("ownerHome.soldOutLabel") }}</p>
            <p class="ui-stat-value transition-colors" :class="soldOutCount > 0 ? 'text-amber-400' : 'text-emerald-500'">{{ soldOutCount }}</p>
          </article>
        </template>
      </div>

      <!-- Today's order quick-stats -->
      <div class="grid grid-cols-3 gap-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-950/50">
        <template v-if="loading">
          <div v-for="i in 3" :key="i" class="animate-pulse py-3 text-center" :class="i === 2 ? 'border-x border-slate-800' : ''">
            <div class="mx-auto h-6 w-8 rounded bg-slate-700/50" />
            <div class="mx-auto mt-1.5 h-2 w-16 rounded bg-slate-800/50" />
          </div>
        </template>
        <template v-else>
          <div class="py-3 text-center">
            <p class="text-xl font-bold tabular-nums text-white">{{ todayOrderStats.count }}</p>
            <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerHome.todayOrders") }}</p>
            <p v-if="yesterdayOrderStats.count > 0" class="mt-0.5 text-[9px] tabular-nums" :class="todayOrderStats.count >= yesterdayOrderStats.count ? 'text-emerald-500' : 'text-slate-600'">
              {{ todayOrderStats.count >= yesterdayOrderStats.count ? '+' : '' }}{{ todayOrderStats.count - yesterdayOrderStats.count }} {{ t("ownerHome.vsYesterday") }}
            </p>
          </div>
          <div class="border-x border-slate-800 py-3 text-center">
            <p class="text-xl font-bold tabular-nums text-[var(--color-secondary)]">{{ todayOrderStats.revenue }}</p>
            <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerHome.todayRevenue") }}</p>
            <p v-if="yesterdayOrderStats.revenue > 0" class="mt-0.5 text-[9px]" :class="todayOrderStats.revenueRaw >= yesterdayOrderStats.revenue ? 'text-emerald-500' : 'text-slate-600'">
              {{ todayOrderStats.revenueRaw >= yesterdayOrderStats.revenue ? '↑' : '↓' }} {{ t("ownerHome.vsYesterday") }}
            </p>
          </div>
          <div class="py-3 text-center">
            <p class="text-xl font-bold tabular-nums transition-colors" :class="todayOrderStats.pending > 0 ? 'text-amber-400' : 'text-white'">{{ todayOrderStats.pending }}</p>
            <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerOrders.todayPending") }}</p>
          </div>
        </template>
      </div>

      <!-- Ratings summary strip -->
      <RouterLink
        v-if="ratingsSummary && ratingsSummary.count > 0"
        :to="{ name: 'owner-ratings' }"
        class="flex items-center justify-between gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-2.5 transition hover:border-amber-500/35 hover:bg-amber-500/8"
      >
        <div class="flex items-center gap-2.5">
          <span class="text-amber-400 text-lg leading-none">★</span>
          <span class="text-sm font-bold text-white tabular-nums">{{ ratingsSummary.average !== null ? ratingsSummary.average.toFixed(1) : "—" }}</span>
          <span class="text-xs text-slate-500">/ 5 &middot; {{ ratingsSummary.count }} {{ t("ownerHome.avgRating").toLowerCase() }}</span>
        </div>
        <span class="text-xs font-medium text-amber-400/80 transition hover:text-amber-300">{{ t("ownerHome.viewAllRatings") }} →</span>
      </RouterLink>
      <div v-else-if="ratingsSummary && ratingsSummary.count === 0" class="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950/30 px-4 py-2.5">
        <span class="text-sm text-slate-600">★</span>
        <span class="text-xs text-slate-600">{{ t("ownerHome.noRatingsYet") }}</span>
      </div>
      <!-- Skeleton while ratings haven't loaded yet -->
      <div v-else-if="!ratingsSummary" class="h-10 animate-pulse rounded-xl bg-slate-800/30" />

      <!-- Revenue chart + best sellers side-by-side on wider screens -->
      <div class="grid gap-3 xl:grid-cols-2">
        <div class="rounded-xl border border-slate-800 bg-slate-950/50 p-3 sm:p-4">
          <RevenueBarChart
            :external-days="chartComponentDays"
            :external-currency="chartComponentCurrency"
            :parent-loading="insightsLoading"
          />
        </div>
        <div class="rounded-xl border border-slate-800 bg-slate-950/50 p-3 sm:p-4">
          <BestSellersWidget :period="dashboardPeriod" />
        </div>
      </div>

      <!-- Restaurant open/closed quick toggle -->
      <div
        class="flex items-center justify-between gap-3 rounded-xl border px-4 py-3 transition-colors"
        :class="isOpen ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-amber-500/20 bg-amber-500/5'"
      >
        <div class="space-y-0.5">
          <p class="text-sm font-semibold" :class="isOpen ? 'text-emerald-200' : 'text-amber-300'">
            {{ isOpen ? t("ownerHome.restaurantOpen") : t("ownerHome.restaurantClosed") }}
          </p>
          <p class="text-xs text-slate-500">{{ t("ownerHome.openToggleHint") }}</p>
        </div>
        <button
          class="rounded-full border px-4 py-1.5 text-xs font-semibold transition-colors disabled:opacity-50"
          :class="isOpen
            ? 'border-red-500/50 text-red-300 hover:bg-red-500/10'
            : 'border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/10'"
          :disabled="togglingOpen"
          @click="toggleOpen"
        >
          {{ togglingOpen ? "…" : (isOpen ? t("ownerHome.closeNow") : t("ownerHome.openNow")) }}
        </button>
      </div>

      <!-- Dish availability quick toggle -->
      <details class="group rounded-xl border border-slate-800 bg-slate-950/30" :open="dishAvailOpen">
        <summary
          class="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2.5 text-sm font-semibold text-slate-200 [&::-webkit-details-marker]:hidden"
          @click.prevent="dishAvailOpen = !dishAvailOpen"
        >
          <span class="flex items-center gap-2">
            <AppIcon name="menu" class="h-3.5 w-3.5 text-slate-400" />
            {{ t("ownerHome.dishAvailability") }}
          </span>
          <span class="flex items-center gap-2 text-xs font-normal text-slate-400">
            <span v-if="soldOutCount > 0" class="rounded-full border border-red-500/40 bg-red-500/15 px-2 py-0.5 font-semibold text-red-300">
              {{ soldOutCount }} {{ t("ownerHome.soldOut") }}
            </span>
            <span>{{ dishAvailOpen ? "▲" : "▼" }}</span>
          </span>
        </summary>
        <div v-if="dishAvailOpen" class="space-y-1 border-t border-slate-800 px-3 pb-3 pt-2">
          <!-- Search + morning reset row -->
          <div class="mb-2 flex items-center gap-2">
            <input
              v-model.trim="dishAvailSearch"
              type="search"
              class="ui-input flex-1 text-xs"
              :aria-label="t('common.search')"
              :placeholder="t('common.search')"
            />
            <button
              v-if="soldOutCount > 0"
              class="shrink-0 rounded-full border border-emerald-500/40 px-2.5 py-1 text-[10px] font-semibold text-emerald-300 transition-colors hover:bg-emerald-500/10 disabled:opacity-50"
              :disabled="resettingAvailability"
              :title="t('ownerHome.resetAvailabilityHint')"
              @click="resetAllAvailability"
            >
              {{ resettingAvailability ? "…" : t("ownerHome.resetAllAvailable") }}
            </button>
          </div>
          <div v-if="!dishesData.length" class="py-2 text-center text-xs text-slate-500">
            {{ t("ownerHome.noDishesLoaded") }}
          </div>
          <div
            v-for="dish in filteredDishesAvail"
            :key="dish.id"
            class="flex items-center justify-between gap-2 rounded-xl px-2 py-1.5 transition-colors hover:bg-slate-900/60"
            :class="!dish.is_available ? 'opacity-70' : ''"
          >
            <div class="min-w-0">
              <p class="truncate text-xs font-medium text-slate-100">{{ dish.name }}</p>
              <p class="text-[10px] text-slate-500">{{ dish.category_name || dish.category_slug }}</p>
            </div>
            <!-- Stock qty input: blank = unlimited (∞), number = tracked inventory -->
            <div class="flex shrink-0 items-center gap-1.5">
              <div class="flex flex-col items-center gap-0.5">
                <label class="text-[8px] uppercase tracking-wider text-slate-600">{{ t("ownerHome.stockLabel") }}</label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  :value="dish.stock_qty ?? ''"
                  :placeholder="t('ownerHome.stockUnlimited')"
                  :disabled="settingStockId === dish.id"
                  class="w-14 rounded-lg border border-slate-700 bg-slate-900/80 px-1.5 py-0.5 text-center text-[10px] text-slate-200 placeholder-slate-600 focus:border-slate-500 focus:outline-none disabled:opacity-40"
                  :class="dish.stock_qty === 0 ? 'border-red-500/50 text-red-300' : dish.stock_qty !== null ? 'border-amber-500/30 text-amber-200' : ''"
                  @change="setDishStock(dish, $event.target.value)"
                  @keydown.enter="$event.target.blur()"
                />
              </div>
              <button
                class="shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-semibold transition-colors disabled:opacity-50"
                :class="dish.is_available
                  ? 'border-emerald-500/40 text-emerald-300 hover:border-red-400/50 hover:bg-red-500/10 hover:text-red-300'
                  : 'border-red-500/40 bg-red-500/10 text-red-300 hover:border-emerald-400/50 hover:bg-emerald-500/10 hover:text-emerald-300'"
                :disabled="togglingDishId === dish.id"
                @click="toggleDishAvailability(dish)"
              >
                {{ togglingDishId === dish.id ? "…" : (dish.is_available ? t("ownerHome.dishAvailable") : t("ownerHome.dish86d")) }}
              </button>
            </div>
          </div>
        </div>
      </details>

      <div class="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:gap-3">
        <RouterLink :to="{ name: 'owner-menu-builder' }" class="ui-btn-primary col-span-2 w-full px-5 py-2.5 sm:w-auto">
          <AppIcon name="menu" class="owner-home-btn-icon" />
          {{ t("ownerHome.openMenuBuilder") }}
        </RouterLink>
        <RouterLink to="/menu" class="ui-btn-outline w-full px-4 py-2.5 sm:w-auto">
          <AppIcon name="eye" class="owner-home-btn-icon" />
          {{ t("ownerLayout.publicPreview") }}
        </RouterLink>
        <button class="ui-btn-outline w-full px-4 py-2.5 sm:w-auto transition-colors" :class="copied ? 'border-emerald-500/50 text-emerald-300' : ''" @click="copyMenuUrl">
          <AppIcon :name="copied ? 'check' : 'copy'" class="owner-home-btn-icon" />
          {{ copied ? t("ownerHome.menuUrlCopied") : t("ownerHome.copyPublicUrl") }}
        </button>
        <button class="ui-btn-outline col-span-2 w-full px-4 py-2.5 sm:w-auto" :disabled="loading" @click="refresh">
          <AppIcon name="refresh" class="owner-home-btn-icon" />
          {{ loading ? t("ownerHome.refreshing") : t("common.refresh") }}
        </button>
      </div>

      <!-- Error banner with retry -->
      <div v-if="error" role="alert" class="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/8 px-4 py-3">
        <svg viewBox="0 0 20 20" class="h-4 w-4 shrink-0 text-red-400" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-10.5a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 7a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/>
        </svg>
        <p class="flex-1 text-sm text-red-300">{{ error }}</p>
        <button
          class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
          :disabled="loading"
          @click="refresh"
        >{{ t("common.retry") }}</button>
      </div>
    </article>

    <!-- Readiness skeleton -->
    <article v-if="loading" class="ui-section-band animate-pulse space-y-3 p-3 sm:space-y-4 sm:p-4">
      <div class="flex items-center justify-between gap-3">
        <div class="h-3.5 w-28 rounded bg-slate-700/60" />
        <div class="h-3.5 w-10 rounded bg-slate-700/60" />
      </div>
      <div class="h-2 rounded-full bg-slate-800" />
      <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
        <div v-for="i in 5" :key="i" class="ui-checklist-card flex items-center justify-between gap-3">
          <div class="h-3 flex-1 rounded bg-slate-700/50" />
          <div class="h-5 w-14 shrink-0 rounded-full bg-slate-700/40" />
        </div>
      </div>
    </article>

    <!-- Readiness — only show once real data has loaded -->
    <article v-else class="ui-section-band space-y-3 p-3 sm:space-y-4 sm:p-4">
      <div class="flex items-center justify-between gap-3">
        <p class="text-sm font-medium text-slate-200">{{ t("ownerHome.launchProgress") }}</p>
        <span class="text-sm font-semibold" :class="readinessScore === 100 ? 'text-emerald-400' : 'text-[var(--color-secondary)]'">
          {{ readinessScore === 100 ? "✓ " : "" }}{{ readinessScore }}%
        </span>
      </div>
      <div class="h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          class="h-full rounded-full transition-all duration-300"
          :class="readinessScore === 100 ? 'bg-emerald-500' : 'bg-[var(--color-secondary)]'"
          :style="{ width: `${readinessScore}%` }"
        ></div>
      </div>
      <!-- Congratulatory message when 100% ready -->
      <p v-if="readinessScore === 100" class="text-xs text-emerald-400/80">
        {{ t("ownerHome.readinessDone") }}
      </p>
      <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
        <article
          v-for="item in readinessItems"
          :key="item.label"
          class="ui-checklist-card flex items-start justify-between gap-3"
          :data-complete="item.ready"
          :data-warning="!item.ready"
        >
          <div class="flex min-w-0 items-start gap-3">
            <span class="ui-readiness-dot mt-1 shrink-0"></span>
            <div class="min-w-0">
              <p class="text-[13px] font-medium text-slate-100 sm:text-sm">{{ item.label }}</p>
              <RouterLink v-if="item.to" :to="item.to" class="mt-1.5 inline-flex text-[11px] text-brand-secondary hover:underline sm:text-xs">
                {{ item.actionLabel }}
              </RouterLink>
            </div>
          </div>
          <span class="shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold" :class="item.ready ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'">
            {{ item.ready ? t("ownerHome.ready") : t("ownerHome.missing") }}
          </span>
        </article>
      </div>
    </article>

    <article class="ui-command-deck space-y-3 p-3 sm:space-y-4 sm:p-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="inline-flex items-center gap-2 text-lg font-semibold">
          <AppIcon name="chart" class="owner-home-section-icon" />
          <span>{{ t("ownerHome.analyticsTitle", { days: dashboardPeriod }) }}</span>
          <!-- Subtle spinner shown while stale cache is being silently refreshed -->
          <svg v-if="insightsUpdating" class="h-3.5 w-3.5 animate-spin text-slate-500" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M13.5 8a5.5 5.5 0 1 1-1.1-3.3M13.5 2v3.5H10"/>
          </svg>
        </h3>
        <div class="flex flex-wrap items-center gap-2">
          <!-- Period selector pills -->
          <div class="flex items-center gap-1">
            <button
              v-for="d in PERIOD_OPTIONS"
              :key="d"
              class="rounded-full border px-2.5 py-0.5 text-[11px] font-semibold transition-colors"
              :class="dashboardPeriod === d
                ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                : 'border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
              :disabled="insightsLoading"
              @click="setDashboardPeriod(d)"
            >{{ d }}d</button>
          </div>
          <button
            class="inline-flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-800/60 px-2.5 py-1 text-xs text-slate-300 transition hover:border-slate-600 hover:text-white"
            :disabled="analyticsExporting"
            @click="exportAnalytics"
          >
            <svg v-if="!analyticsExporting" class="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M2 11v2a1 1 0 001 1h10a1 1 0 001-1v-2M8 2v8M5 7l3 3 3-3"/>
            </svg>
            <svg v-else class="h-3.5 w-3.5 animate-spin" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8">
              <circle cx="8" cy="8" r="6" stroke-dasharray="28" stroke-dashoffset="10"/>
            </svg>
            {{ t("ownerHome.exportCsv") }}
          </button>
        </div>
      </div>

      <!-- KPI tiles — skeleton while loading -->
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-2 sm:gap-3 xl:grid-cols-4">
        <template v-if="insightsLoading">
          <div v-for="i in 4" :key="i" class="ui-stat-tile animate-pulse">
            <div class="h-3 w-16 rounded bg-slate-700/60" />
            <div class="mt-2 h-7 w-12 rounded bg-slate-700/40" />
          </div>
        </template>
        <template v-else>
          <div class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("ownerHome.menuViews") }}</p>
            <p class="ui-stat-value text-slate-100">{{ analyticsCounts.menu_view || 0 }}</p>
          </div>
          <div class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("ownerHome.dishViews") }}</p>
            <p class="ui-stat-value text-slate-100">{{ analyticsCounts.dish_view || 0 }}</p>
          </div>
          <div class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("ownerHome.orderActions") }}</p>
            <p class="ui-stat-value text-slate-100">{{ orderActionsCount }}</p>
          </div>
          <div class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("ownerHome.interactionRate") }}</p>
            <p class="ui-stat-value text-[var(--color-secondary)]">{{ interactionRateLabel }}</p>
          </div>
        </template>
      </div>

      <!-- Analytics network error — show retry instead of empty state -->
      <div
        v-if="insightsError && !insightsLoading"
        class="flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3"
      >
        <svg viewBox="0 0 20 20" class="h-4 w-4 shrink-0 text-red-400/70" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-10.5a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 7a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/>
        </svg>
        <p class="flex-1 text-xs text-slate-400">{{ t("ownerHome.analyticsLoadError") }}</p>
        <button
          class="shrink-0 rounded-lg border border-slate-700 px-2.5 py-1 text-[11px] font-semibold text-slate-300 transition hover:border-slate-600"
          @click="hydrateOwnerInsights(true)"
        >{{ t("common.retry") }}</button>
      </div>

      <!-- Empty state: no analytics data at all (new restaurant) -->
      <div
        v-else-if="!insightsError && !insightsLoading && !funnelSteps.some(s => s.value > 0) && !topCategories.length"
        class="rounded-xl border border-slate-800/60 bg-slate-900/30 px-4 py-5 text-center space-y-1"
      >
        <AppIcon name="chart" class="mx-auto h-6 w-6 text-slate-600" />
        <p class="text-sm font-medium text-slate-400">{{ t("ownerHome.noAnalyticsData") }}</p>
        <p class="text-xs text-slate-600">{{ t("ownerHome.noAnalyticsDataHint") }}</p>
      </div>

      <!-- Order conversion funnel -->
      <div v-if="funnelSteps.some(s => s.value > 0)" class="ui-admin-subcard space-y-3">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerHome.funnelTitle") }}</p>
        <div class="space-y-2">
          <div v-for="(step, i) in funnelSteps" :key="step.key" class="funnel-step">
            <div class="flex items-center justify-between gap-2 text-sm">
              <span class="text-slate-300">{{ step.label }}</span>
              <div class="flex items-center gap-2 shrink-0">
                <span v-if="step.dropPct !== null" class="funnel-drop-badge">
                  −{{ step.dropPct }}%
                </span>
                <span class="w-14 text-right tabular-nums font-semibold text-slate-100">{{ formatNumber(step.value) }}</span>
              </div>
            </div>
            <div class="mt-1.5 h-2 w-full rounded-full bg-slate-800">
              <div
                class="h-2 rounded-full transition-all duration-500"
                :class="step.barClass"
                :style="{ width: step.widthPct + '%' }"
              />
            </div>
            <!-- Conversion rate below the bar (except last step) -->
            <p v-if="i < funnelSteps.length - 1 && step.convRate !== null" class="mt-0.5 text-right text-[10px] text-slate-500">
              {{ step.convRate }}% {{ t("ownerHome.funnelConvert") }}
            </p>
          </div>
        </div>
        <p v-if="funnelOverall !== null" class="border-t border-slate-800/60 pt-2 text-xs text-slate-500">
          {{ t("ownerHome.funnelOverall", { pct: funnelOverall }) }}
        </p>
      </div>

      <!-- Top categories / dishes -->
      <div class="grid gap-2 sm:grid-cols-2 sm:gap-3">
        <div class="ui-admin-subcard">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerHome.topCategories") }}</p>
          <ul v-if="topCategories.length" class="mt-3 space-y-2 text-sm text-slate-200">
            <li v-for="item in topCategories" :key="item.category_slug" class="flex items-center justify-between gap-3">
              <span>{{ resolveLabel(categoryNameBySlug, item.category_slug) }}</span>
              <span class="text-slate-400">{{ item.count }}</span>
            </li>
          </ul>
          <div v-else class="ui-empty-state mt-3 px-4 py-4 text-center">
            <AppIcon name="chart" class="mx-auto h-5 w-5 text-slate-500" />
            <p class="mt-2 text-sm text-slate-400">{{ t("ownerHome.noDataYet") }}</p>
          </div>
        </div>
        <div class="ui-admin-subcard">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerHome.topDishes") }}</p>
          <ul v-if="topDishes.length" class="mt-3 space-y-2 text-sm text-slate-200">
            <li v-for="item in topDishes" :key="item.dish_slug" class="flex items-center justify-between gap-3">
              <span>{{ resolveLabel(dishNameBySlug, item.dish_slug) }}</span>
              <span class="text-slate-400">{{ item.count }}</span>
            </li>
          </ul>
          <div v-else class="ui-empty-state mt-3 px-4 py-4 text-center">
            <AppIcon name="menu" class="mx-auto h-5 w-5 text-slate-500" />
            <p class="mt-2 text-sm text-slate-400">{{ t("ownerHome.noDataYet") }}</p>
          </div>
        </div>
      </div>
    </article>

    <!-- Revenue analytics (hidden for staff without view_revenue permission) -->
    <article v-if="(revenueSummary || insightsLoading) && session.canViewRevenue" class="ui-command-deck space-y-3 p-3 sm:space-y-4 sm:p-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="inline-flex items-center gap-2 text-lg font-semibold">
          <AppIcon name="download" class="owner-home-section-icon" />
          <span>{{ t("ownerHome.revenueTitle") }}</span>
          <svg v-if="insightsUpdating" class="h-3.5 w-3.5 animate-spin text-slate-500" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M13.5 8a5.5 5.5 0 1 1-1.1-3.3M13.5 2v3.5H10"/>
          </svg>
        </h3>
        <p class="text-xs text-slate-400">{{ revenueSummary ? t("ownerHome.revenuePeriod", { days: revenueSummary.days }) : `${dashboardPeriod}d` }}</p>
      </div>

      <!-- KPI row — skeleton while loading -->
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <template v-if="insightsLoading">
          <div v-for="i in 4" :key="i" class="ui-stat-tile animate-pulse">
            <div class="h-3 w-16 rounded bg-slate-700/60" />
            <div class="mt-2 h-7 w-14 rounded bg-slate-700/40" />
          </div>
        </template>
        <template v-else-if="revenueSummary">
          <div class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("ownerHome.revenueTotal") }}</p>
            <p class="ui-stat-value text-[var(--color-secondary)]">{{ formatRevenue(revenueSummary.total_revenue) }}</p>
          </div>
          <div class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("ownerHome.revenueOrders") }}</p>
            <p class="ui-stat-value text-slate-100">{{ revenueSummary.order_count }}</p>
          </div>
          <div class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("ownerHome.revenueAvg") }}</p>
            <p class="ui-stat-value text-slate-100">{{ formatRevenue(revenueSummary.avg_order_value) }}</p>
          </div>
          <div class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("ownerHome.customerReturnRate") }}</p>
            <p
              class="ui-stat-value"
              :class="returnRate !== null ? 'text-slate-100' : 'text-slate-600'"
            >
              {{ returnRateLabel }}
            </p>
            <p v-if="returnRate !== null && returnData" class="mt-0.5 text-[10px] text-slate-500">
              {{ t("ownerHome.customerReturnRateHint", { count: returnData.total_customers }) }}
            </p>
          </div>
        </template>
      </div>

      <!-- Daily revenue bar chart (CSS-only) -->
      <div v-if="revenueSummary && revenueSummary.daily.length > 1" class="space-y-1">
        <p class="text-xs uppercase tracking-[0.18em] text-slate-500">{{ t("ownerHome.revenueDailyChart") }}</p>
        <div class="flex items-end gap-0.5 h-20 overflow-x-auto pb-1">
          <div
            v-for="day in revenueChartDays"
            :key="day.date"
            class="flex flex-1 min-w-[0.5rem] flex-col items-center gap-0.5"
            :title="`${day.date}: ${formatRevenue(day.revenue)} (${day.orders} orders)`"
          >
            <div
              class="w-full rounded-sm bg-[var(--color-secondary)]/70 hover:bg-[var(--color-secondary)] transition-colors"
              :style="{ height: `${day.heightPct}%`, minHeight: day.revenue > 0 ? '2px' : '0' }"
            />
          </div>
        </div>
        <div class="flex justify-between text-[10px] text-slate-600">
          <span>{{ revenueChartDays[0]?.shortDate }}</span>
          <span>{{ revenueChartDays[revenueChartDays.length - 1]?.shortDate }}</span>
        </div>
      </div>

      <!-- Peak hours charts (only when there are orders to show) -->
      <div v-if="revenueSummary && revenueSummary.order_count > 0 && peakHoursBars.length" class="space-y-3 pt-2 border-t border-slate-800/60">
        <p class="text-xs uppercase tracking-[0.18em] text-slate-500">{{ t("ownerHome.peakHoursTitle") }}</p>
        <div class="grid sm:grid-cols-2 gap-4">
          <!-- Orders by hour of day -->
          <div class="space-y-1.5">
            <p class="text-[10px] font-medium text-slate-400">{{ t("ownerHome.peakHoursByHour") }}</p>
            <div class="flex items-end gap-px h-16 overflow-hidden">
              <div
                v-for="bar in peakHoursBars"
                :key="bar.hour"
                class="flex-1 rounded-sm transition-colors"
                :class="hourBarColor(bar.hour)"
                :style="{ height: `${bar.heightPct}%`, minHeight: bar.count > 0 ? '2px' : '0' }"
                :title="`${bar.hour}:00 — ${bar.count}`"
              />
            </div>
            <div class="flex justify-between text-[9px] text-slate-600">
              <span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>23h</span>
            </div>
          </div>
          <!-- Orders by day of week -->
          <div class="space-y-1.5">
            <p class="text-[10px] font-medium text-slate-400">{{ t("ownerHome.peakHoursByDay") }}</p>
            <div class="flex items-end gap-1 h-16">
              <div
                v-for="bar in peakWeekdayBars"
                :key="bar.label"
                class="flex flex-1 flex-col items-center gap-0.5"
                :title="`${bar.label} — ${bar.count}`"
              >
                <div
                  class="w-full rounded-sm bg-[var(--color-secondary)]/70 hover:bg-[var(--color-secondary)] transition-colors"
                  :style="{ height: `${bar.heightPct}%`, minHeight: bar.count > 0 ? '2px' : '0' }"
                />
              </div>
            </div>
            <div class="flex justify-between text-[9px] text-slate-600">
              <span v-for="bar in peakWeekdayBars" :key="bar.label">{{ bar.label }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Popular dishes (only when there are orders) -->
      <div v-if="revenueSummary && popularDishes.length" class="space-y-2 pt-2 border-t border-slate-800/60">
        <p class="text-xs uppercase tracking-[0.18em] text-slate-500">{{ t("ownerHome.popularDishesTitle") }}</p>
        <ol class="space-y-1.5">
          <li
            v-for="(dish, idx) in popularDishes"
            :key="dish.dish_slug"
            class="flex items-center gap-2 text-sm"
          >
            <span class="w-4 shrink-0 text-right text-xs font-bold text-slate-600">{{ idx + 1 }}</span>
            <div class="relative flex-1 overflow-hidden rounded-sm bg-slate-800/50 h-6">
              <div
                class="absolute inset-y-0 left-0 rounded-sm bg-[var(--color-secondary)]/20 transition-all"
                :style="{ width: dish.barPct + '%' }"
              />
              <span class="relative truncate px-2 leading-6 text-slate-200">{{ dish.dish_name }}</span>
            </div>
            <span class="shrink-0 text-xs text-slate-400 tabular-nums">×{{ dish.order_count }}</span>
          </li>
        </ol>
      </div>
    </article>

    <!-- Live Orders Widget -->
    <article class="ui-command-deck space-y-3 p-3 sm:space-y-4 sm:p-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="inline-flex items-center gap-2 text-lg font-semibold">
          <AppIcon name="cart" class="owner-home-section-icon" />
          <span>{{ t("ownerHome.liveOrders") }}</span>
          <span v-if="order.ordersLoading" class="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-500"></span>
        </h3>
        <RouterLink :to="{ name: 'owner-orders' }" class="ui-btn-outline px-3 py-1.5 text-xs">
          {{ t("ownerHome.viewAllOrders") }}
        </RouterLink>
      </div>

      <!-- Status counts -->
      <div class="flex flex-wrap gap-2">
        <div
          class="flex items-center gap-2 rounded-xl border px-3 py-2"
          :class="pendingOrders.length ? 'border-amber-500/60 bg-amber-500/10' : 'border-slate-700 bg-slate-900/40'"
        >
          <span class="text-xl font-bold" :class="pendingOrders.length ? 'text-amber-300' : 'text-slate-400'">{{ pendingOrders.length }}</span>
          <span class="text-xs font-medium" :class="pendingOrders.length ? 'text-amber-200' : 'text-slate-500'">{{ t("ownerOrders.statusPending") }}</span>
          <span v-if="pendingOrders.length" class="h-2 w-2 animate-pulse rounded-full bg-amber-400"></span>
        </div>
        <div class="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/40 px-3 py-2">
          <span class="text-xl font-bold text-slate-300">{{ activeOrders.length }}</span>
          <span class="text-xs font-medium text-slate-500">{{ t("ownerHome.inProgress") }}</span>
        </div>
        <!-- All-clear badge when no active orders but there are recent ones -->
        <div
          v-if="!pendingOrders.length && !activeOrders.length && recentOrders.length"
          class="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/8 px-3 py-2"
        >
          <span class="text-emerald-400">✓</span>
          <span class="text-xs font-medium text-emerald-300/70">{{ t("ownerHome.allClear") }}</span>
        </div>
      </div>

      <!-- Recent orders list — sorted with active first -->
      <div v-if="recentOrders.length" class="space-y-1.5">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerHome.recentOrdersList") }}</p>
        <RouterLink
          v-for="o in recentOrders"
          :key="o.id"
          :to="{ name: 'owner-orders', query: { q: o.order_number } }"
          class="flex items-center justify-between gap-3 rounded-xl border bg-slate-950/40 px-3 py-2 text-xs transition-colors hover:bg-slate-900/60"
          :class="['pending','confirmed','preparing','ready'].includes(o.status)
            ? 'border-slate-700 hover:border-slate-600'
            : 'border-slate-800 hover:border-slate-700'"
        >
          <div class="flex items-center gap-2 min-w-0">
            <span class="font-mono font-bold text-slate-100">{{ o.order_number }}</span>
            <span class="rounded-full px-2 py-0.5 font-semibold" :class="orderStatusClass(o.status)">{{ orderStatusLabel(o.status) }}</span>
            <span v-if="o.fulfillment_type" class="hidden sm:inline text-slate-400">{{ fulfillmentLabel(o) }}</span>
          </div>
          <div class="flex shrink-0 items-center gap-3">
            <span class="font-semibold text-[var(--color-secondary)]">{{ formatOrderTotal(o) }}</span>
            <span class="text-slate-500">{{ formatTimeAgo(o.created_at) }}</span>
          </div>
        </RouterLink>
      </div>
      <div v-else-if="!order.ordersLoading" class="rounded-xl border border-slate-800 bg-slate-950/30 px-4 py-6 text-center">
        <p class="text-sm text-slate-400">{{ t("ownerHome.noOrdersYet") }}</p>
      </div>
    </article>

    <!-- Plan summary card → links to billing tab -->
    <article class="ui-command-deck p-3 sm:p-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <h3 class="inline-flex items-center gap-2 text-base font-semibold">
            <AppIcon name="plus" class="owner-home-section-icon" />
            <span>{{ t("ownerHome.planSection") }}</span>
          </h3>
          <div class="flex flex-wrap items-center gap-2">
            <span class="rounded-full border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/10 px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-[var(--color-secondary)]">
              {{ tenant.entitlements?.tier_name || tenant.meta?.plan?.name || "Basic" }}
            </span>
            <span
              v-if="hasPendingRequest"
              class="rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-amber-300"
            >
              {{ t("ownerHome.pendingUpgradeShort") }}
            </span>
          </div>
        </div>
        <RouterLink
          :to="{ name: 'owner-profile', query: { tab: 'billing' } }"
          class="ui-btn-outline px-3 py-1.5 text-xs"
        >
          {{ t("ownerBilling.manageBilling") }}
          <svg viewBox="0 0 16 16" class="ml-1 inline h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 8h10M9 4l4 4-4 4"/>
          </svg>
        </RouterLink>
      </div>
      <!-- Pending upgrade banner -->
      <p
        v-if="hasPendingRequest"
        class="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2 text-xs text-amber-200"
      >
        {{
          pendingUpgrade
            ? t("ownerHome.pendingUpgrade", { plan: pendingUpgrade.target_plan_name })
            : t("ownerHome.pendingUpgradeFallback")
        }}
      </p>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import BestSellersWidget from "../components/BestSellersWidget.vue";
import RevenueBarChart from "../components/RevenueBarChart.vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { bustCache, isFresh, readCache, writeCache } from "../lib/staleCache";
import { useOrderStore } from "../stores/order";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const session = useSessionStore();
const tenant = useTenantStore();
const order = useOrderStore();
const toast = useToastStore();
const { t, formatDateTime, formatNumber, currentLocale } = useI18n();

const categoriesCount = ref(0);
const dishesCount = ref(0);
const categoriesData = ref([]);
const dishesData = ref([]);
const loading = ref(false);
const copied = ref(false);
const error = ref("");
const upgradeLoading = ref(false);
const upgradeSubmitting = ref(false);
const upgradeError = ref("");
const upgradeRequests = ref([]);
const upgradeTargets = ref([]);
const upgradeMeta = ref({
  current_tier_code: "basic",
  current_tier_name: "Basic",
  has_pending_request: false,
});
const upgradeCustomerNote = ref("");
const upgradeTargetCode = ref("growth");
const analyticsSummary = ref({
  counts: {},
  top_categories: [],
  top_dishes: [],
  interaction_rate_pct: 0,
});
const revenueSummary = ref(null); // { total_revenue, order_count, avg_order_value, daily: [{date, revenue, orders}] }
const ratingsSummary = ref(null); // { count, average } or null while loading
const insightsLoading = ref(false);
const insightsUpdating = ref(false); // stale data showing, silently refreshing
const insightsError = ref(false);    // network error loading analytics data
const dashboardPeriod = ref(30);
const PERIOD_OPTIONS = [7, 14, 30, 90];
const INSIGHTS_TTL_MS = 3 * 60 * 1000; // 3-minute cache TTL per period

// ── Dish availability panel ───────────────────────────────────────────────────
const dishAvailOpen = ref(false);
const dishAvailSearch = ref("");
const togglingDishId = ref(null);
const settingStockId = ref(null);
const resettingAvailability = ref(false);

// is_available = daily 86 toggle (sold-out but still visible on menu)
// is_published = permanent visibility toggle (hide from menu entirely)
const soldOutCount = computed(() => dishesData.value.filter((d) => d.is_published && !d.is_available).length);

// Auto-open when new sold-out dishes appear (e.g. after data load)
watch(soldOutCount, (n, o) => {
  if (n > 0 && o === 0) dishAvailOpen.value = true;
});
const filteredDishesAvail = computed(() => {
  const q = dishAvailSearch.value.toLowerCase();
  const list = [...dishesData.value].filter((d) => d.is_published).sort((a, b) => {
    // 86'd dishes first
    if (!a.is_available && b.is_available) return -1;
    if (a.is_available && !b.is_available) return 1;
    return 0;
  });
  if (!q) return list;
  return list.filter((d) =>
    (d.name || "").toLowerCase().includes(q) ||
    (d.category_name || "").toLowerCase().includes(q) ||
    (d.category_slug || "").toLowerCase().includes(q)
  );
});

const toggleDishAvailability = async (dish) => {
  if (togglingDishId.value === dish.id) return;
  togglingDishId.value = dish.id;
  const newValue = !dish.is_available;
  try {
    await api.patch(`/dishes/${dish.id}/`, { is_available: newValue });
    dish.is_available = newValue;
    // Bust menu cache so customers see the updated availability immediately
    bustCache("menu.categories");
    toast.show(
      newValue ? t("ownerHome.dishRestored", { name: dish.name }) : t("ownerHome.dish86dToast", { name: dish.name }),
      newValue ? "success" : "info"
    );
  } catch {
    toast.show(t("ownerHome.dish86Failed"), "error");
  } finally {
    togglingDishId.value = null;
  }
};

// Set or clear tracked stock count for a dish.
// Empty input → null (unlimited). Positive int → tracked stock.
// Re-enables availability automatically when restoring positive stock.
const setDishStock = async (dish, rawValue) => {
  if (settingStockId.value === dish.id) return;
  const trimmed = String(rawValue ?? "").trim();
  const newQty = trimmed === "" ? null : parseInt(trimmed, 10);
  if (newQty !== null && (isNaN(newQty) || newQty < 0)) return;
  if (newQty === dish.stock_qty) return; // no real change
  settingStockId.value = dish.id;
  try {
    const payload = { stock_qty: newQty };
    // Restore availability when owner sets positive stock (auto-disabled when it hit 0)
    if (newQty !== null && newQty > 0 && !dish.is_available) {
      payload.is_available = true;
    }
    await api.patch(`/dishes/${dish.id}/`, payload);
    dish.stock_qty = newQty;
    if (payload.is_available !== undefined) dish.is_available = payload.is_available;
    bustCache("menu.categories");
    toast.show(
      newQty === null
        ? t("ownerHome.stockUnlimitedSet", { name: dish.name })
        : t("ownerHome.stockSet", { name: dish.name, qty: newQty }),
      "success"
    );
  } catch {
    toast.show(t("ownerHome.stockSetFailed"), "error");
  } finally {
    settingStockId.value = null;
  }
};

// Morning reset: mark all published dishes available and clear auto-zeroed stock.
// Shown only when soldOutCount > 0 — the "start of day" button.
const resetAllAvailability = async () => {
  if (resettingAvailability.value) return;
  resettingAvailability.value = true;
  try {
    const { data } = await api.post("/owner/dishes/reset-availability/");
    // Update local dish data optimistically — re-enable all sold-out dishes
    dishesData.value.forEach((d) => {
      if (d.is_published && !d.is_available) {
        d.is_available = true;
      }
      // Clear stock_qty=0 entries (auto-zeroed) so the input shows blank again
      if (d.stock_qty === 0) {
        d.stock_qty = null;
      }
    });
    bustCache("menu.categories");
    const count = data?.restored ?? 0;
    toast.show(
      count > 0
        ? t("ownerHome.resetAvailabilityDone", { count })
        : t("ownerHome.resetAvailabilityNone"),
      "success"
    );
  } catch {
    toast.show(t("ownerHome.resetAvailabilityFailed"), "error");
  } finally {
    resettingAvailability.value = false;
  }
};

const pendingOrders = computed(() => order.orders.filter((o) => o.status === "pending"));
const activeOrders = computed(() => order.orders.filter((o) => ["confirmed", "preparing", "ready"].includes(o.status)));
const ORDER_STATUS_PRIORITY = { pending: 0, confirmed: 1, preparing: 2, ready: 3, completed: 4, cancelled: 5 };
const recentOrders = computed(() =>
  [...order.orders]
    .sort((a, b) => {
      // Active orders first, then by recency
      const sp = (ORDER_STATUS_PRIORITY[a.status] ?? 9) - (ORDER_STATUS_PRIORITY[b.status] ?? 9);
      if (sp !== 0) return sp;
      return new Date(b.created_at) - new Date(a.created_at);
    })
    .slice(0, 6)
);

const profile = computed(() => tenant.meta?.profile || {});
const published = computed(() => profile.value?.is_menu_published === true);
const isOpen = computed(() => profile.value?.is_open !== false);
const togglingOpen = ref(false);

// ── Today's order stats ───────────────────────────────────────────────────────
const todayOrderStats = computed(() => {
  const today = new Date().toDateString();
  const todayOrders = order.orders.filter((o) => new Date(o.created_at).toDateString() === today);
  const revenue = todayOrders.reduce((s, o) => s + (Number(o.total) || 0), 0);
  const currency = todayOrders.find((o) => o.currency)?.currency || "MAD";
  let revenueLabel = "";
  try {
    revenueLabel = formatNumber(revenue, {
      style: "currency",
      currency,
      notation: "compact",
      maximumFractionDigits: 0,
    });
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

const yesterdayOrderStats = computed(() => {
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const yStr = yesterday.toDateString();
  const yOrders = order.orders.filter((o) => new Date(o.created_at).toDateString() === yStr);
  return {
    count: yOrders.length,
    pending: yOrders.filter((o) => o.status === "pending").length,
    revenue: yOrders.reduce((s, o) => s + (Number(o.total) || 0), 0),
  };
});

// ── Open/Closed toggle ────────────────────────────────────────────────────────
const toggleOpen = async () => {
  if (togglingOpen.value) return;
  togglingOpen.value = true;
  const newValue = !isOpen.value;
  try {
    await api.patch("/profile/", { is_open: newValue });
    tenant.mergeProfile({ is_open: newValue });
    // Bust meta cache so customers see the updated open/closed status immediately
    bustCache("meta");
    toast.show(newValue ? t("ownerHome.openedToast") : t("ownerHome.closedToast"), newValue ? "success" : "info");
  } catch {
    toast.show(t("ownerHome.toggleFailed"), "error");
  } finally {
    togglingOpen.value = false;
  }
};
const canCheckout = computed(() => tenant.entitlements?.can_checkout === true);
const canWhatsapp = computed(() => tenant.entitlements?.can_whatsapp_order === true);
const planModeLabel = computed(() => {
  if (canCheckout.value) return t("ownerHome.checkoutEnabled");
  if (canWhatsapp.value) return t("ownerHome.whatsappEnabled");
  return t("ownerHome.browseOnly");
});
const hasContact = computed(() => Boolean((profile.value?.phone || "").trim() || (profile.value?.whatsapp || "").trim()));
const hasTheme = computed(() =>
  Boolean((profile.value?.logo_url || "").trim() || (profile.value?.hero_url || "").trim() || profile.value?.primary_color || profile.value?.secondary_color)
);

const readinessScore = computed(() => {
  const checks = [
    hasContact.value,
    hasTheme.value,
    categoriesCount.value > 0,
    dishesCount.value > 0,
    published.value,
  ];
  const passed = checks.filter(Boolean).length;
  return Math.round((passed / checks.length) * 100);
});

const analyticsCounts = computed(() => analyticsSummary.value?.counts || {});

// Revenue helpers
const formatRevenue = (amount) => {
  const n = Number(amount) || 0;
  if (n === 0) return "—";
  // Use the first order's currency or fallback to a plain number
  const currency = revenueSummary.value?.currency || tenant.meta?.profile?.currency || null;
  try {
    if (currency) return formatNumber(n, { style: "currency", currency });
  } catch { /* unsupported currency */ }
  return n.toFixed(2);
};

const revenueChartDays = computed(() => {
  const days = revenueSummary.value?.daily || [];
  if (!days.length) return [];
  const maxRev = Math.max(...days.map((d) => d.revenue), 1);
  return days.map((d) => ({
    date: d.date,
    revenue: d.revenue,
    orders: d.orders,
    heightPct: Math.round((d.revenue / maxRev) * 100),
    shortDate: d.date.slice(5), // "MM-DD"
  }));
});

// Data passed to <RevenueBarChart> so it can skip its own /owner/revenue-chart/ API call.
// The field mapping normalises 'orders' (dashboard) → 'order_count' (chart component).
const chartComponentDays = computed(() => {
  const days = revenueSummary.value?.daily;
  if (!days?.length) return null;
  return days.map((d) => ({ date: d.date, revenue: d.revenue, order_count: d.orders ?? 0 }));
});
const chartComponentCurrency = computed(() => revenueSummary.value?.currency ?? null);

// Peak hours helpers
const hourBarColor = (hour) => {
  if (hour >= 6 && hour <= 11) return "bg-amber-400/70 hover:bg-amber-400";
  if (hour >= 12 && hour <= 14) return "bg-emerald-400/70 hover:bg-emerald-400";
  if (hour >= 18 && hour <= 22) return "bg-violet-400/70 hover:bg-violet-400";
  return "bg-slate-500/50 hover:bg-slate-400/60";
};

const peakHoursData = computed(() => revenueSummary.value?.peak_hours || null);

const peakHoursBars = computed(() => {
  const hours = peakHoursData.value?.by_hour || [];
  const max = Math.max(...hours, 1);
  return hours.map((count, hour) => ({
    hour,
    count,
    heightPct: Math.round((count / max) * 100),
  }));
});

const shortDayLabels = computed(() => {
  // Jan 1 2023 was a Sunday — gives us Sun=0 … Sat=6 aligned with ExtractWeekDay 1-7
  const locale = tenant.meta?.profile?.locale || "en";
  return Array.from({ length: 7 }, (_, i) => {
    try {
      return new Intl.DateTimeFormat(locale, { weekday: "short" }).format(new Date(2023, 0, 1 + i));
    } catch {
      return ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"][i];
    }
  });
});

const peakWeekdayBars = computed(() => {
  const days = peakHoursData.value?.by_weekday || [];
  const max = Math.max(...days, 1);
  return days.map((count, idx) => ({
    label: shortDayLabels.value[idx] || String(idx),
    count,
    heightPct: Math.round((count / max) * 100),
  }));
});

const popularDishes = computed(() => {
  const dishes = revenueSummary.value?.popular_dishes || [];
  const maxCount = Math.max(...dishes.map((d) => d.order_count), 1);
  return dishes.map((d) => ({
    ...d,
    barPct: Math.round((d.order_count / maxCount) * 100),
  }));
});

const returnData = computed(() => revenueSummary.value?.customer_return || null);
const returnRate = computed(() => {
  const d = returnData.value;
  if (!d || d.return_rate_pct === null || d.return_rate_pct === undefined) return null;
  return d.return_rate_pct;
});
const returnRateLabel = computed(() =>
  returnRate.value !== null
    ? `${returnRate.value.toFixed(1)}%`
    : t("ownerHome.customerReturnRateNA")
);

const orderActionsCount = computed(
  () => Number(analyticsCounts.value?.order_handoff_click || 0) + Number(analyticsCounts.value?.checkout_click || 0)
);
const interactionRateLabel = computed(() =>
  `${formatNumber(analyticsSummary.value?.interaction_rate_pct || 0, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`
);
const topCategories = computed(() => (analyticsSummary.value?.top_categories || []).slice(0, 6));
const topDishes = computed(() => (analyticsSummary.value?.top_dishes || []).slice(0, 6));
const categoryNameBySlug = computed(() => Object.fromEntries(categoriesData.value.map((c) => [c.slug, c.name])));
const dishNameBySlug = computed(() => Object.fromEntries(dishesData.value.map((d) => [d.slug, d.name])));
const resolveLabel = (map, slug) => map[slug] || humanizeSlug(slug);

// ── Conversion funnel ─────────────────────────────────────────────────────────
const funnelData = computed(() => analyticsSummary.value?.funnel || null);
const funnelOverall = computed(() => {
  const f = funnelData.value;
  return f?.overall_rate_pct ?? null;
});
const funnelSteps = computed(() => {
  const f = funnelData.value;
  const menuViews = f?.menu_views ?? Number(analyticsCounts.value?.menu_view || 0);
  const cartViews = f?.cart_views ?? Number(analyticsCounts.value?.cart_view || 0);
  const intents = f?.order_intents ?? orderActionsCount.value;
  const orders = f?.orders_placed ?? revenueSummary.value?.order_count ?? 0;

  const steps = [
    {
      key: "menu",
      label: t("ownerHome.funnelMenuViews"),
      value: menuViews,
      barClass: "bg-slate-400/70",
      convRate: f?.cart_rate_pct ?? null,
    },
    {
      key: "cart",
      label: t("ownerHome.funnelCartViews"),
      value: cartViews,
      barClass: "bg-amber-400/70",
      convRate: f?.intent_rate_pct ?? null,
    },
    {
      key: "intent",
      label: t("ownerHome.funnelOrderIntents"),
      value: intents,
      barClass: "bg-orange-400/70",
      convRate: f?.completion_rate_pct ?? null,
    },
    {
      key: "orders",
      label: t("ownerHome.funnelOrdersPlaced"),
      value: orders,
      barClass: "bg-emerald-400/80",
      convRate: null,
    },
  ];

  const maxVal = Math.max(...steps.map((s) => s.value), 1);
  return steps.map((step, i) => {
    const prev = i > 0 ? steps[i - 1].value : null;
    const dropped = prev !== null && prev > 0 ? Math.round(((prev - step.value) / prev) * 100) : null;
    return {
      ...step,
      widthPct: Math.max(Math.round((step.value / maxVal) * 100), step.value > 0 ? 2 : 0),
      dropPct: dropped,
    };
  });
});

// ── Analytics CSV export ──────────────────────────────────────────────────────
const analyticsExporting = ref(false);
const exportAnalytics = async () => {
  if (analyticsExporting.value) return;
  analyticsExporting.value = true;
  try {
    const response = await api.get("/owner/analytics/export/", {
      params: { days: dashboardPeriod.value },
      responseType: "blob",
      timeout: 15000,
    });
    const url = URL.createObjectURL(new Blob([response.data], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `analytics_${dashboardPeriod.value}d.csv`;
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    toast.show(t("ownerHome.exportFailed"), "error");
  } finally {
    analyticsExporting.value = false;
  }
};
const fetchRatingsSummary = async () => {
  try {
    const { data } = await api.get("/owner/ratings/", { timeout: 5000 });
    ratingsSummary.value = {
      count: data?.count ?? 0,
      average: data?.average ?? null,
    };
  } catch {
    ratingsSummary.value = { count: 0, average: null };
  }
};

const pendingUpgrade = computed(() => upgradeRequests.value.find((request) => request.status === "pending") || null);
const hasPendingRequest = computed(() => Boolean(pendingUpgrade.value) || upgradeMeta.value.has_pending_request === true);
const readinessItems = computed(() => [
  {
    label: t("ownerHome.brandContactPresent"),
    ready: hasContact.value,
    to: hasContact.value ? "" : "/owner/profile",
    actionLabel: t("ownerHome.readinessActionContact"),
  },
  {
    label: t("ownerHome.themeConfigured"),
    ready: hasTheme.value,
    to: hasTheme.value ? "" : "/owner/profile?tab=theme",
    actionLabel: t("ownerHome.readinessActionTheme"),
  },
  {
    label: t("ownerHome.categoriesAdded"),
    ready: categoriesCount.value > 0,
    to: categoriesCount.value > 0 ? "" : "/owner/menu-builder?tab=categories",
    actionLabel: t("ownerHome.readinessActionCategories"),
  },
  {
    label: t("ownerHome.dishesAdded"),
    ready: dishesCount.value > 0,
    to: dishesCount.value > 0 ? "" : "/owner/menu-builder?tab=dishes",
    actionLabel: t("ownerHome.readinessActionDishes"),
  },
  {
    label: t("ownerHome.menuPublished"),
    ready: published.value,
    to: published.value ? "/menu" : "/owner/profile?tab=publish",
    actionLabel: published.value ? t("ownerLayout.publicPreview") : t("ownerHome.readinessActionPublish"),
  },
]);

const refresh = async () => {
  loading.value = true;
  error.value = "";
  try {
    // Fire all three independent calls in parallel instead of sequentially.
    const [, cats, dishes] = await Promise.all([
      tenant.fetchMeta(),
      api.get("/categories/", { timeout: 5000 }),
      api.get("/dishes/", { timeout: 5000 }),
    ]);
    categoriesData.value = Array.isArray(cats.data) ? cats.data : [];
    dishesData.value = Array.isArray(dishes.data) ? dishes.data : [];
    categoriesCount.value = categoriesData.value.length;
    dishesCount.value = dishesData.value.length;
    ensureUpgradeTargetSelection();
    void order.fetchOrders();
    void hydrateOwnerInsights(true); // force = true: bust cache on manual refresh
    void fetchRatingsSummary();
  } catch {
    error.value = t("ownerHome.dashboardRefreshFailed");
    toast.show(error.value, "error");
  } finally {
    loading.value = false;
  }
};

const setDashboardPeriod = (days) => {
  if (days === dashboardPeriod.value) return;
  dashboardPeriod.value = days;
  void hydrateOwnerInsights();
};

// ── Insights data helpers ─────────────────────────────────────────────────────
let _insightsAbort = null;

/** Apply a dashboard API response to the reactive state (shared by cache + network path). */
const _applyInsightsData = (data) => {
  if (data?.analytics_summary) analyticsSummary.value = data.analytics_summary;
  if (data?.revenue_summary) revenueSummary.value = data.revenue_summary;
  if (Array.isArray(data?.upgrade_targets)) upgradeTargets.value = data.upgrade_targets;
  if (data?.upgrade_meta) {
    upgradeMeta.value = {
      current_tier_code: data.upgrade_meta.current_tier_code || tenant.entitlements?.tier_code || "basic",
      current_tier_name: data.upgrade_meta.current_tier_name || tenant.entitlements?.tier_name || "Basic",
      has_pending_request: data.upgrade_meta.has_pending_request === true,
    };
  }
  if (Array.isArray(data?.upgrade_requests)) {
    upgradeRequests.value = data.upgrade_requests;
    upgradeMeta.value = {
      ...upgradeMeta.value,
      has_pending_request: upgradeRequests.value.some((r) => r.status === "pending"),
    };
  }
  ensureUpgradeTargetSelection();
};

const hydrateOwnerInsights = async (force = false) => {
  // Cancel any superseded in-flight request (e.g. rapid period switching).
  _insightsAbort?.abort();
  const ctrl = new AbortController();
  _insightsAbort = ctrl;

  insightsError.value = false;
  const cacheKey = `owner.insights.${dashboardPeriod.value}d`;
  // Force mode (manual refresh button) — discard cache so fresh data is fetched.
  if (force) bustCache(cacheKey);
  const cached = readCache(cacheKey);

  if (cached) {
    _applyInsightsData(cached);
    if (isFresh(cacheKey, INSIGHTS_TTL_MS)) return; // Cache still fresh — skip network
    insightsUpdating.value = true; // Stale — revalidate silently in the background
  } else {
    insightsLoading.value = true; // Cold start — show skeleton
  }

  try {
    const { data } = await api.get("/owner/dashboard/", {
      params: { days: dashboardPeriod.value },
      signal: ctrl.signal,
      timeout: 8000,
    });
    if (ctrl.signal.aborted) return;
    _applyInsightsData(data);
    writeCache(cacheKey, data);
  } catch (err) {
    if (err.code === "ERR_CANCELED" || err.name === "AbortError" || ctrl.signal.aborted) return;
    // Dashboard endpoint unavailable — fall back to individual calls.
    let fallbackOk = false;
    try {
      const analytics = await api.get("/analytics/summary/", { params: { days: dashboardPeriod.value }, timeout: 5000 });
      analyticsSummary.value = analytics?.data || analyticsSummary.value;
      fallbackOk = true;
    } catch { /* analytics are supplementary */ }
    await Promise.allSettled([fetchUpgradeTargets(), fetchUpgradeRequests()]);
    if (!fallbackOk && !cached) insightsError.value = true;
  } finally {
    if (!ctrl.signal.aborted) {
      insightsLoading.value = false;
      insightsUpdating.value = false;
    }
  }
};

const menuUrl = computed(() => (typeof window === "undefined" ? "/menu" : `${window.location.origin}/menu`));

let copyResetTimer = null;

const copyMenuUrl = async () => {
  try {
    await navigator.clipboard.writeText(menuUrl.value);
    copied.value = true;
    if (copyResetTimer !== null) clearTimeout(copyResetTimer);
    copyResetTimer = setTimeout(() => {
      copied.value = false;
      copyResetTimer = null;
    }, 1800);
  } catch {
    toast.show(t("ownerHome.copyFailed"), "error");
  }
};

const ensureUpgradeTargetSelection = () => {
  if (!upgradeTargets.value.length) {
    upgradeTargetCode.value = "";
    return;
  }
  const stillAvailable = upgradeTargets.value.some((target) => target.code === upgradeTargetCode.value);
  if (!stillAvailable) {
    upgradeTargetCode.value = upgradeTargets.value[0].code;
  }
};

const fetchUpgradeTargets = async () => {
  try {
    const { data } = await api.get("/tier-upgrade-targets/", { timeout: 6000 });
    const targets = Array.isArray(data?.targets) ? data.targets : [];
    upgradeTargets.value = targets;
    upgradeMeta.value = {
      current_tier_code: data?.current_tier_code || tenant.entitlements?.tier_code || "basic",
      current_tier_name: data?.current_tier_name || tenant.entitlements?.tier_name || "Basic",
      has_pending_request: data?.has_pending_request === true,
    };
    ensureUpgradeTargetSelection();
  } catch {
    upgradeTargets.value = [];
  }
};

const fetchUpgradeRequests = async () => {
  upgradeLoading.value = true;
  upgradeError.value = "";
  try {
    const { data } = await api.get("/tier-upgrade-requests/", { timeout: 6000 });
    upgradeRequests.value = Array.isArray(data) ? data : [];
    upgradeMeta.value = {
      ...upgradeMeta.value,
      has_pending_request: upgradeRequests.value.some((request) => request.status === "pending"),
    };
    ensureUpgradeTargetSelection();
  } catch {
    upgradeError.value = t("ownerHome.loadRequestsFailed");
  } finally {
    upgradeLoading.value = false;
  }
};

const submitUpgradeRequest = async () => {
  if (!upgradeTargetCode.value || hasPendingRequest.value) return;
  upgradeSubmitting.value = true;
  upgradeError.value = "";
  try {
    await api.post("/tier-upgrade-requests/", {
      target_plan_code: upgradeTargetCode.value,
      payment_method: "cash",
      customer_note: upgradeCustomerNote.value,
    });
    upgradeCustomerNote.value = "";
    toast.show(t("ownerHome.upgradeSent"), "success");
    await Promise.all([fetchUpgradeTargets(), fetchUpgradeRequests()]);
  } catch (err) {
    const detail = err?.response?.data?.detail;
    upgradeError.value = typeof detail === "string" ? detail : t("ownerHome.upgradeFailed");
    toast.show(upgradeError.value, "error");
  } finally {
    upgradeSubmitting.value = false;
  }
};

const upgradeStatusClass = (status) => {
  if (status === "approved") return "bg-emerald-500/20 text-emerald-200";
  if (status === "rejected") return "bg-rose-500/20 text-rose-200";
  if (status === "canceled") return "bg-slate-600/30 text-slate-300";
  return "bg-amber-500/20 text-amber-200";
};

const upgradeStatusLabel = (status) => {
  if (status === "approved") return t("ownerHome.statusApproved");
  if (status === "rejected") return t("ownerHome.statusRejected");
  if (status === "canceled") return t("ownerHome.statusCanceled");
  return t("ownerHome.statusPending");
};

const fulfillmentLabel = (o) => {
  if (o.fulfillment_type === "table") return t("ownerOrders.fulfillmentTable", { table: o.table_label || "?" });
  if (o.fulfillment_type === "delivery") return t("ownerOrders.fulfillmentDelivery");
  if (o.fulfillment_type === "pickup") return t("ownerOrders.fulfillmentPickup");
  return "";
};

const orderStatusClass = (s) => ({
  pending: "bg-amber-500/20 text-amber-200 border border-amber-500/30",
  confirmed: "bg-sky-500/20 text-sky-200 border border-sky-500/30",
  preparing: "bg-violet-500/20 text-violet-200 border border-violet-500/30",
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
  return new Intl.DateTimeFormat(currentLocale.value, { dateStyle: 'short' }).format(new Date(iso));
};

const humanizeSlug = (value) =>
  String(value || "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

// ── Live-orders background poll ──────────────────────────────────────────────
const HOME_POLL_INTERVAL_S = 30;
let homePollTimer = null;

const doSilentOrdersPoll = () => {
  void order.fetchOrders("", { silent: true });
};

const onHomePageVisible = () => {
  if (typeof document !== "undefined" && document.visibilityState === "visible") {
    doSilentOrdersPoll();
  }
};

onMounted(async () => {
  await refresh();
  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", onHomePageVisible);
  }
  homePollTimer = setInterval(() => {
    if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
    doSilentOrdersPoll();
  }, HOME_POLL_INTERVAL_S * 1000);
});

onUnmounted(() => {
  _insightsAbort?.abort();
  clearInterval(homePollTimer);
  if (copyResetTimer !== null) {
    clearTimeout(copyResetTimer);
    copyResetTimer = null;
  }
  if (typeof document !== "undefined") {
    document.removeEventListener("visibilitychange", onHomePageVisible);
  }
});
</script>

<style scoped>
.owner-home-btn-icon {
  width: 0.86rem;
  height: 0.86rem;
}

.owner-home-section-icon {
  width: 1rem;
  height: 1rem;
  color: var(--color-secondary);
}

/* ── Funnel ─────────────────────────────────────────────────────────────────── */
.funnel-step {
  /* no extra styling needed – layout handled by flex in template */
}

.funnel-drop-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.05rem 0.35rem;
  border-radius: 0.3rem;
  font-size: 0.68rem;
  font-weight: 600;
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
  letter-spacing: 0.02em;
}
</style>
