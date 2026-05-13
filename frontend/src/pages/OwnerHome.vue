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
        <article class="ui-admin-subcard space-y-1.5">
          <p class="ui-stat-label">{{ t("common.status") }}</p>
          <p class="ui-stat-value text-slate-100">{{ published ? t("ownerHome.published") : t("ownerHome.draft") }}</p>
        </article>
      </div>

      <!-- Today's order quick-stats -->
      <div class="grid grid-cols-3 gap-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-950/50">
        <div class="py-3 text-center">
          <p class="text-xl font-bold tabular-nums text-white">{{ todayOrderStats.count }}</p>
          <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerHome.todayOrders") }}</p>
        </div>
        <div class="border-x border-slate-800 py-3 text-center">
          <p class="text-xl font-bold tabular-nums text-[var(--color-secondary)]">{{ todayOrderStats.revenue }}</p>
          <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerHome.todayRevenue") }}</p>
        </div>
        <div class="py-3 text-center">
          <p class="text-xl font-bold tabular-nums transition-colors" :class="todayOrderStats.pending > 0 ? 'text-amber-400' : 'text-white'">{{ todayOrderStats.pending }}</p>
          <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerOrders.todayPending") }}</p>
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
      <details class="group rounded-xl border border-slate-800 bg-slate-950/30" :open="soldOutCount > 0 || dishAvailOpen">
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
          <input
            v-model.trim="dishAvailSearch"
            class="ui-input mb-2 text-xs"
            :placeholder="t('common.search')"
          />
          <div v-if="!dishesData.length" class="py-2 text-center text-xs text-slate-500">
            {{ t("ownerHome.noDishesLoaded") }}
          </div>
          <div
            v-for="dish in filteredDishesAvail"
            :key="dish.id"
            class="flex items-center justify-between gap-2 rounded-xl px-2 py-1.5 transition-colors hover:bg-slate-900/60"
            :class="!dish.is_published ? 'opacity-60' : ''"
          >
            <div class="min-w-0">
              <p class="truncate text-xs font-medium text-slate-100">{{ dish.name }}</p>
              <p class="text-[10px] text-slate-500">{{ dish.category_name || dish.category_slug }}</p>
            </div>
            <button
              class="shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-semibold transition-colors disabled:opacity-50"
              :class="dish.is_published
                ? 'border-emerald-500/40 text-emerald-300 hover:border-red-400/50 hover:bg-red-500/10 hover:text-red-300'
                : 'border-red-500/40 bg-red-500/10 text-red-300 hover:border-emerald-400/50 hover:bg-emerald-500/10 hover:text-emerald-300'"
              :disabled="togglingDishId === dish.id"
              @click="toggleDishPublished(dish)"
            >
              {{ togglingDishId === dish.id ? "…" : (dish.is_published ? t("ownerHome.dishAvailable") : t("ownerHome.dish86d")) }}
            </button>
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
        <button class="ui-btn-outline w-full px-4 py-2.5 sm:w-auto" @click="copyMenuUrl">
          <AppIcon name="copy" class="owner-home-btn-icon" />
          {{ t("ownerHome.copyPublicUrl") }}
        </button>
        <button class="ui-btn-outline col-span-2 w-full px-4 py-2.5 sm:w-auto" :disabled="loading" @click="refresh">
          <AppIcon name="refresh" class="owner-home-btn-icon" />
          {{ loading ? t("ownerHome.refreshing") : t("common.refresh") }}
        </button>
      </div>

      <p v-if="error" class="text-sm text-red-300">{{ error }}</p>
      <p v-if="copied" class="text-xs text-emerald-300">{{ t("ownerHome.menuUrlCopied") }}</p>
    </article>

    <article class="ui-section-band space-y-3 p-3 sm:space-y-4 sm:p-4">
      <div class="flex items-center justify-between gap-3">
        <p class="text-sm font-medium text-slate-200">{{ t("ownerHome.launchProgress") }}</p>
        <span class="text-sm font-semibold text-[var(--color-secondary)]">{{ readinessScore }}%</span>
      </div>
      <div class="h-2 overflow-hidden rounded-full bg-slate-800">
        <div class="h-full rounded-full bg-[var(--color-secondary)] transition-all duration-300" :style="{ width: `${readinessScore}%` }"></div>
      </div>
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
          <span>{{ t("ownerHome.analyticsTitle") }}</span>
        </h3>
        <p class="text-xs text-slate-400">{{ t("ownerHome.analyticsSubtitle") }}</p>
      </div>
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-2 sm:gap-3 xl:grid-cols-4">
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
      </div>
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

    <!-- Live Orders Widget -->
    <article class="ui-command-deck space-y-3 p-3 sm:space-y-4 sm:p-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="inline-flex items-center gap-2 text-lg font-semibold">
          <AppIcon name="menu" class="owner-home-section-icon" />
          <span>{{ t("ownerHome.liveOrders") }}</span>
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
      </div>

      <!-- Recent orders list -->
      <div v-if="recentOrders.length" class="space-y-1.5">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerHome.recentOrdersList") }}</p>
        <RouterLink
          v-for="o in recentOrders"
          :key="o.id"
          :to="{ name: 'owner-orders' }"
          class="flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/40 px-3 py-2 text-xs transition-colors hover:border-slate-600 hover:bg-slate-900/60"
        >
          <div class="flex items-center gap-2 min-w-0">
            <span class="font-mono font-bold text-slate-100">{{ o.order_number }}</span>
            <span class="rounded-full px-2 py-0.5 font-semibold" :class="orderStatusClass(o.status)">{{ orderStatusLabel(o.status) }}</span>
            <span v-if="o.fulfillment_type" class="hidden sm:inline text-slate-400">{{ o.fulfillment_type }}</span>
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

    <article class="ui-command-deck space-y-3 p-3 sm:space-y-4 sm:p-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 class="inline-flex items-center gap-2 text-lg font-semibold">
            <AppIcon name="plus" class="owner-home-section-icon" />
            <span>{{ t("ownerHome.purchaseUpgrade") }}</span>
          </h3>
          <p class="text-xs text-slate-400">{{ t("ownerHome.currentPlan", { plan: tenant.entitlements?.tier_name || tenant.meta?.plan?.name || "Basic" }) }}</p>
        </div>
        <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="upgradeLoading" @click="fetchUpgradeRequests">
          <AppIcon name="refresh" class="owner-home-btn-icon" />
          {{ upgradeLoading ? t("ownerHome.loadingRequests") : t("ownerHome.refreshRequests") }}
        </button>
      </div>

      <p v-if="hasPendingRequest" class="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
        {{
          pendingUpgrade
            ? t("ownerHome.pendingUpgrade", { plan: pendingUpgrade.target_plan_name })
            : t("ownerHome.pendingUpgradeFallback")
        }}
      </p>

      <div v-if="upgradeTargets.length" class="grid gap-2 sm:gap-3 lg:grid-cols-[1fr,2fr,auto]">
        <label class="text-sm text-slate-300">
          {{ t("ownerHome.targetTier") }}
          <select v-model="upgradeTargetCode" class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
            <option v-for="target in upgradeTargets" :key="target.code" :value="target.code">
              {{ target.name }}{{ target.is_active ? "" : ` (${t("common.soon")})` }}
            </option>
          </select>
        </label>
        <label class="text-sm text-slate-300">
          {{ t("ownerHome.messageToAdmin") }}
          <input
            v-model.trim="upgradeCustomerNote"
            type="text"
            maxlength="1500"
            :placeholder="t('ownerHome.upgradePlaceholder')"
            class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
        </label>
        <div class="flex items-end">
          <button
            class="ui-btn-primary w-full px-4 py-2 text-sm disabled:opacity-60"
            :disabled="upgradeSubmitting || hasPendingRequest || !upgradeTargetCode"
            @click="submitUpgradeRequest"
          >
            {{ upgradeSubmitting ? t("ownerHome.sendingUpgrade") : t("ownerHome.purchaseTier") }}
          </button>
        </div>
      </div>
      <p v-else class="text-sm text-slate-400">{{ t("ownerHome.highestTier") }}</p>
      <p v-if="upgradeError" class="text-sm text-red-300">{{ upgradeError }}</p>

      <div class="space-y-2">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerHome.recentRequests") }}</p>
        <div class="overflow-hidden rounded-xl border border-slate-800 hidden md:block">
          <table class="min-w-full text-sm">
            <thead class="bg-slate-900/80 text-slate-400">
              <tr>
                <th class="px-3 py-2 text-start">{{ t("ownerHome.when") }}</th>
                <th class="px-3 py-2 text-start">{{ t("ownerHome.from") }}</th>
                <th class="px-3 py-2 text-start">{{ t("ownerHome.to") }}</th>
                <th class="px-3 py-2 text-start">{{ t("common.status") }}</th>
                <th class="px-3 py-2 text-start">{{ t("ownerHome.adminNote") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="request in upgradeRequests" :key="request.id" class="border-t border-slate-800">
                <td class="px-3 py-2 text-slate-300">{{ formatDateTime(request.requested_at) }}</td>
                <td class="px-3 py-2 text-slate-200">{{ request.current_plan_name }}</td>
                <td class="px-3 py-2 text-slate-200">{{ request.target_plan_name }}</td>
                <td class="px-3 py-2">
                  <span
                    class="rounded-full px-2 py-1 text-xs font-semibold"
                    :class="upgradeStatusClass(request.status)"
                  >
                    {{ upgradeStatusLabel(request.status) }}
                  </span>
                </td>
                <td class="px-3 py-2 text-slate-400">{{ request.admin_note || t("ownerHome.noAdminNote") }}</td>
              </tr>
              <tr v-if="!upgradeRequests.length && !upgradeLoading">
                <td colspan="5" class="px-3 py-4">
                  <div class="ui-empty-state px-4 py-4 text-center">
                    <AppIcon name="plus" class="mx-auto h-5 w-5 text-slate-500" />
                    <p class="mt-2 text-sm text-slate-400">{{ t("ownerHome.noRequests") }}</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="space-y-2 md:hidden">
          <article
            v-for="request in upgradeRequests"
            :key="`mobile-${request.id}`"
            class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-2"
          >
            <div class="flex items-center justify-between gap-2">
              <p class="text-xs text-slate-400">{{ formatDateTime(request.requested_at) }}</p>
              <span class="rounded-full px-2 py-1 text-xs font-semibold" :class="upgradeStatusClass(request.status)">
                {{ upgradeStatusLabel(request.status) }}
              </span>
            </div>
            <p class="text-sm text-slate-100">{{ request.current_plan_name }} -> {{ request.target_plan_name }}</p>
            <p class="text-xs text-slate-400">{{ request.admin_note || t("ownerHome.noAdminNote") }}</p>
          </article>
          <div v-if="!upgradeRequests.length && !upgradeLoading" class="ui-empty-state px-4 py-4 text-center">
            <AppIcon name="plus" class="mx-auto h-5 w-5 text-slate-500" />
            <p class="mt-2 text-sm text-slate-400">{{ t("ownerHome.noRequests") }}</p>
          </div>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { RouterLink } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { useOrderStore } from "../stores/order";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const tenant = useTenantStore();
const order = useOrderStore();
const toast = useToastStore();
const { t, formatDateTime, formatNumber } = useI18n();

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

// ── Dish availability panel ───────────────────────────────────────────────────
const dishAvailOpen = ref(false);
const dishAvailSearch = ref("");
const togglingDishId = ref(null);

const soldOutCount = computed(() => dishesData.value.filter((d) => !d.is_published).length);
const filteredDishesAvail = computed(() => {
  const q = dishAvailSearch.value.toLowerCase();
  const list = [...dishesData.value].sort((a, b) => {
    // 86'd dishes first
    if (!a.is_published && b.is_published) return -1;
    if (a.is_published && !b.is_published) return 1;
    return 0;
  });
  if (!q) return list;
  return list.filter((d) =>
    (d.name || "").toLowerCase().includes(q) ||
    (d.category_name || "").toLowerCase().includes(q) ||
    (d.category_slug || "").toLowerCase().includes(q)
  );
});

const toggleDishPublished = async (dish) => {
  if (togglingDishId.value === dish.id) return;
  togglingDishId.value = dish.id;
  const newValue = !dish.is_published;
  try {
    await api.patch(`/dishes/${dish.id}/`, { is_published: newValue });
    dish.is_published = newValue;
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

const pendingOrders = computed(() => order.orders.filter((o) => o.status === "pending"));
const activeOrders = computed(() => order.orders.filter((o) => ["confirmed", "preparing", "ready"].includes(o.status)));
const recentOrders = computed(() => [...order.orders].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 5));

const profile = computed(() => tenant.meta?.profile || {});
const published = computed(() => profile.value?.is_menu_published === true);
const isOpen = computed(() => profile.value?.is_open !== false);
const togglingOpen = ref(false);

// ── Today's order stats ───────────────────────────────────────────────────────
const todayOrderStats = computed(() => {
  const today = new Date().toDateString();
  const todayOrders = order.orders.filter((o) => new Date(o.created_at).toDateString() === today);
  const revenue = todayOrders.reduce((s, o) => s + (Number(o.total) || 0), 0);
  const currency = todayOrders.find((o) => o.currency)?.currency || "USD";
  let revenueLabel = "";
  try {
    revenueLabel = new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      notation: "compact",
      maximumFractionDigits: 0,
    }).format(revenue);
  } catch {
    revenueLabel = `${currency} ${Math.floor(revenue)}`;
  }
  return {
    count: todayOrders.length,
    revenue: revenueLabel,
    pending: todayOrders.filter((o) => o.status === "pending").length,
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
const pendingUpgrade = computed(() => upgradeRequests.value.find((request) => request.status === "pending") || null);
const hasPendingRequest = computed(() => Boolean(pendingUpgrade.value) || upgradeMeta.value.has_pending_request === true);
const readinessItems = computed(() => [
  {
    label: t("ownerHome.brandContactPresent"),
    note: t("ownerHome.quickActions"),
    ready: hasContact.value,
    to: hasContact.value ? "" : "/owner/profile",
    actionLabel: t("ownerHome.openMenuBuilder"),
  },
  {
    label: t("ownerHome.themeConfigured"),
    note: t("ownerLayout.publicPreview"),
    ready: hasTheme.value,
    to: hasTheme.value ? "" : "/owner/profile?tab=theme",
    actionLabel: t("ownerHome.openMenuBuilder"),
  },
  {
    label: t("ownerHome.categoriesAdded"),
    note: `${categoriesCount.value} ${t("common.categories")}`,
    ready: categoriesCount.value > 0,
    to: categoriesCount.value > 0 ? "" : "/owner/menu-builder?tab=categories",
    actionLabel: t("ownerLayout.menuBuilder"),
  },
  {
    label: t("ownerHome.dishesAdded"),
    note: `${dishesCount.value} ${t("common.dishes")}`,
    ready: dishesCount.value > 0,
    to: dishesCount.value > 0 ? "" : "/owner/menu-builder?tab=dishes",
    actionLabel: t("ownerLayout.menuBuilder"),
  },
  {
    label: t("ownerHome.menuPublished"),
    note: planModeLabel.value,
    ready: published.value,
    to: published.value ? "/menu" : "/owner/profile?tab=publish",
    actionLabel: published.value ? t("ownerLayout.publicPreview") : t("common.profile"),
  },
]);

const refresh = async () => {
  loading.value = true;
  error.value = "";
  try {
    await tenant.fetchMeta();
    const [cats, dishes] = await Promise.all([
      api.get("/categories/", { timeout: 5000 }),
      api.get("/dishes/", { timeout: 5000 }),
    ]);
    categoriesData.value = Array.isArray(cats.data) ? cats.data : [];
    dishesData.value = Array.isArray(dishes.data) ? dishes.data : [];
    categoriesCount.value = categoriesData.value.length;
    dishesCount.value = dishesData.value.length;
    ensureUpgradeTargetSelection();
    void order.fetchOrders();
    void hydrateOwnerInsights();
  } catch {
    error.value = t("ownerHome.dashboardRefreshFailed");
    toast.show(error.value, "error");
  } finally {
    loading.value = false;
  }
};

const hydrateOwnerInsights = async () => {
  try {
    const analytics = await api.get("/analytics/summary/", {
      params: { days: 30 },
      timeout: 5000,
    });
    analyticsSummary.value = analytics?.data || analyticsSummary.value;
  } catch {
    // Analytics are supplementary. Keep the dashboard responsive if they lag.
  }

  await Promise.allSettled([fetchUpgradeTargets(), fetchUpgradeRequests()]);
};

const menuUrl = computed(() => (typeof window === "undefined" ? "/menu" : `${window.location.origin}/menu`));

const copyMenuUrl = async () => {
  try {
    await navigator.clipboard.writeText(menuUrl.value);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
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
  try { return new Intl.NumberFormat(undefined, { style: "currency", currency: o.currency || "USD" }).format(Number(o.total) || 0); }
  catch { return `${o.currency} ${Number(o.total).toFixed(2)}`; }
};

const formatTimeAgo = (iso) => {
  if (!iso) return "";
  const diffMin = Math.floor((Date.now() - new Date(iso)) / 60000);
  if (diffMin < 1) return t("ownerOrders.justNow");
  if (diffMin < 60) return `${diffMin}m`;
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)}h`;
  return new Date(iso).toLocaleDateString();
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
  clearInterval(homePollTimer);
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
</style>
