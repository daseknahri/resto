<template>
  <section class="space-y-6 pb-24 sm:pb-6">
    <header class="ui-workspace-stage ui-fade-up">
      <div class="grid gap-5 xl:grid-cols-[minmax(0,1.14fr),360px]">
        <div class="space-y-5">
          <div class="space-y-2">
            <p class="ui-kicker">{{ t("ownerHome.kicker") }}</p>
            <h2 class="ui-page-title ui-display">{{ t("ownerHome.title") }}</h2>
            <p class="max-w-3xl text-sm leading-7 text-slate-300">{{ t("ownerHome.description") }}</p>
          </div>

          <div class="flex flex-wrap gap-2">
            <span class="ui-chip-strong">{{ published ? t("ownerHome.published") : t("ownerHome.draft") }}</span>
            <span class="ui-chip">{{ planModeLabel }}</span>
            <span class="ui-data-strip">{{ t("ownerHome.readiness") }}: {{ readinessScore }}%</span>
            <span class="ui-data-strip">{{ categoriesCount }} {{ t("common.categories") }}</span>
            <span class="ui-data-strip">{{ dishesCount }} {{ t("common.dishes") }}</span>
          </div>

          <div class="flex flex-wrap gap-3">
            <RouterLink to="/owner/onboarding" class="ui-btn-primary px-5 py-2.5">
              {{ t("ownerHome.openMenuBuilder") }}
            </RouterLink>
            <RouterLink to="/menu" class="ui-btn-outline px-5 py-2.5">
              {{ t("ownerLayout.publicPreview") }}
            </RouterLink>
            <button class="ui-btn-outline px-5 py-2.5" @click="copyMenuUrl">
              {{ t("ownerHome.copyPublicUrl") }}
            </button>
          </div>

          <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <div class="ui-action-tile">
              <p class="ui-stat-label">{{ t("ownerHome.launchProgress") }}</p>
              <div class="mt-3 flex items-center justify-between gap-3">
                <p class="text-3xl font-semibold text-[var(--color-secondary)]">{{ readinessScore }}%</p>
                <span class="rounded-full px-2 py-1 text-[10px] font-semibold" :class="published ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'">
                  {{ published ? t("ownerHome.published") : t("ownerHome.draft") }}
                </span>
              </div>
              <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-800">
                <div class="h-full rounded-full bg-[var(--color-secondary)] transition-all duration-300" :style="{ width: `${readinessScore}%` }"></div>
              </div>
            </div>

            <div class="ui-action-tile">
              <p class="ui-stat-label">{{ t("ownerHome.state") }}</p>
              <p class="mt-3 text-xl font-semibold" :class="published ? 'text-emerald-300' : 'text-amber-300'">
                {{ published ? t("ownerHome.published") : t("ownerHome.draft") }}
              </p>
              <p class="mt-2 text-sm text-slate-300">{{ isOpen ? t("ownerHome.restaurantOpen") : t("ownerHome.restaurantClosed") }}</p>
              <p class="mt-1 text-xs" :class="isBrowseOnlyPlan ? 'text-sky-300' : 'text-slate-400'">
                {{ planModeLabel }}
              </p>
            </div>

            <div class="ui-action-tile">
              <p class="ui-stat-label">{{ t("ownerHome.quickActions") }}</p>
              <div class="mt-3 flex flex-col gap-2">
                <button class="ui-btn-outline w-full justify-between px-4 py-2 text-xs" :disabled="loading" @click="refresh">
                  <span>{{ loading ? t("ownerHome.refreshing") : t("common.refresh") }}</span>
                  <span class="text-slate-400">{{ t("ownerHome.readiness") }}</span>
                </button>
                <button class="ui-btn-outline w-full justify-between px-4 py-2 text-xs" :disabled="upgradeLoading" @click="fetchUpgradeRequests">
                  <span>{{ upgradeLoading ? t("ownerHome.loadingRequests") : t("ownerHome.refreshRequests") }}</span>
                  <span class="text-slate-400">{{ upgradeRequests.length }}</span>
                </button>
              </div>
            </div>
          </div>

          <p v-if="error" class="text-sm text-red-300">{{ error }}</p>
          <p v-if="copied" class="text-xs text-emerald-300">{{ t("ownerHome.menuUrlCopied") }}</p>
        </div>

        <aside class="ui-command-deck ui-fade-up space-y-4">
          <div class="space-y-1.5">
            <p class="ui-kicker">{{ t("ownerHome.quickActions") }}</p>
            <h3 class="text-xl font-semibold text-white">{{ t("ownerHome.launchChecklist") }}</h3>
            <p class="text-sm text-slate-300">{{ t("ownerHome.readinessHint") }}</p>
          </div>

          <article class="ui-action-tile space-y-3">
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="ui-stat-label">{{ t("ownerLayout.publicPreview") }}</p>
                <p class="mt-2 break-all text-sm font-medium text-white">{{ menuUrl }}</p>
              </div>
              <span class="rounded-full px-2 py-1 text-[10px] font-semibold" :class="published ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'">
                {{ published ? t("ownerHome.published") : t("ownerHome.draft") }}
              </span>
            </div>
            <div class="grid gap-2 sm:grid-cols-2">
              <RouterLink to="/menu" class="ui-btn-outline justify-center text-xs">
                {{ t("ownerLayout.publicPreview") }}
              </RouterLink>
              <button class="ui-btn-outline justify-center text-xs" @click="copyMenuUrl">
                {{ t("ownerHome.copyPublicUrl") }}
              </button>
            </div>
          </article>

          <div class="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
            <RouterLink to="/owner/onboarding" class="ui-orbit-card ui-surface-lift block p-4">
              <p class="ui-kicker">{{ t("ownerLayout.menuBuilder") }}</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ categoriesCount }} / {{ dishesCount }}</p>
              <p class="mt-1 text-sm text-slate-400">{{ t("ownerHome.launchProgress") }}</p>
            </RouterLink>
            <RouterLink to="/owner/tables" class="ui-orbit-card ui-surface-lift block p-4">
              <p class="ui-kicker">{{ t("ownerLayout.tablesQr") }}</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ published ? t("ownerHome.ready") : t("ownerHome.pending") }}</p>
              <p class="mt-1 text-sm text-slate-400">{{ t("ownerHome.menuPublished") }}</p>
            </RouterLink>
            <RouterLink to="/owner/reservations" class="ui-orbit-card ui-surface-lift block p-4">
              <p class="ui-kicker">{{ t("ownerLayout.reservations") }}</p>
              <p class="mt-2 text-lg font-semibold text-white">{{ upgradeRequests.length }}</p>
              <p class="mt-1 text-sm text-slate-400">{{ t("ownerHome.recentRequests") }}</p>
            </RouterLink>
          </div>
        </aside>
      </div>
    </header>

    <article class="ui-section-band space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p class="text-sm text-slate-300">{{ t("ownerHome.launchProgress") }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ t("ownerHome.pushTo100") }}</p>
        </div>
        <span class="text-sm font-semibold text-[var(--color-secondary)]">{{ readinessScore }}%</span>
      </div>
      <div class="h-2 overflow-hidden rounded-full bg-slate-800">
        <div class="h-full rounded-full bg-[var(--color-secondary)] transition-all duration-300" :style="{ width: `${readinessScore}%` }"></div>
      </div>
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <article
          v-for="item in readinessItems"
          :key="item.label"
          class="ui-admin-subcard flex items-center justify-between gap-3"
        >
          <div class="min-w-0">
            <p class="text-sm font-medium text-slate-100">{{ item.label }}</p>
            <p class="mt-1 text-xs text-slate-500">{{ item.note }}</p>
          </div>
          <span class="shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold" :class="item.ready ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'">
            {{ item.ready ? t("ownerHome.ready") : t("ownerHome.missing") }}
          </span>
        </article>
      </div>
    </article>

    <article class="ui-command-deck space-y-4">
      <div class="flex items-center justify-between gap-2">
        <h3 class="text-lg font-semibold">{{ t("ownerHome.analyticsTitle") }}</h3>
        <p class="text-xs text-slate-400">{{ t("ownerHome.analyticsSubtitle") }}</p>
      </div>
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
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
      <div class="grid gap-3 sm:grid-cols-2">
        <div class="ui-admin-subcard">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerHome.topCategories") }}</p>
          <ul class="mt-3 space-y-2 text-sm text-slate-200">
            <li v-for="item in topCategories" :key="item.category_slug" class="space-y-1.5">
              <div class="flex items-center justify-between gap-3">
                <span>{{ humanizeSlug(item.category_slug) }}</span>
                <span class="text-slate-400">{{ item.count }}</span>
              </div>
              <div class="h-1.5 overflow-hidden rounded-full bg-slate-800">
                <div
                  class="h-full rounded-full bg-[var(--color-secondary)]"
                  :style="{ width: `${scaledCount(item.count, topCategoryPeak)}%` }"
                ></div>
              </div>
            </li>
            <li v-if="!topCategories.length" class="text-slate-500">{{ t("ownerHome.noDataYet") }}</li>
          </ul>
        </div>
        <div class="ui-admin-subcard">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerHome.topDishes") }}</p>
          <ul class="mt-3 space-y-2 text-sm text-slate-200">
            <li v-for="item in topDishes" :key="item.dish_slug" class="space-y-1.5">
              <div class="flex items-center justify-between gap-3">
                <span>{{ humanizeSlug(item.dish_slug) }}</span>
                <span class="text-slate-400">{{ item.count }}</span>
              </div>
              <div class="h-1.5 overflow-hidden rounded-full bg-slate-800">
                <div
                  class="h-full rounded-full bg-cyan-400/80"
                  :style="{ width: `${scaledCount(item.count, topDishPeak)}%` }"
                ></div>
              </div>
            </li>
            <li v-if="!topDishes.length" class="text-slate-500">{{ t("ownerHome.noDataYet") }}</li>
          </ul>
        </div>
      </div>
    </article>

    <article class="ui-command-deck space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 class="text-lg font-semibold">{{ t("ownerHome.purchaseUpgrade") }}</h3>
          <p class="text-xs text-slate-400">{{ t("ownerHome.currentPlan", { plan: tenant.entitlements?.tier_name || tenant.meta?.plan?.name || "Basic" }) }}</p>
        </div>
        <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="upgradeLoading" @click="fetchUpgradeRequests">
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

      <div v-if="upgradeTargets.length" class="grid gap-3 lg:grid-cols-[1fr,2fr,auto]">
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
                <th class="px-3 py-2 text-left">{{ t("ownerHome.when") }}</th>
                <th class="px-3 py-2 text-left">{{ t("ownerHome.from") }}</th>
                <th class="px-3 py-2 text-left">{{ t("ownerHome.to") }}</th>
                <th class="px-3 py-2 text-left">{{ t("common.status") }}</th>
                <th class="px-3 py-2 text-left">{{ t("ownerHome.adminNote") }}</th>
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
                <td colspan="5" class="px-3 py-3 text-slate-500">{{ t("ownerHome.noRequests") }}</td>
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
          <p v-if="!upgradeRequests.length && !upgradeLoading" class="text-xs text-slate-500">{{ t("ownerHome.noRequests") }}</p>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const tenant = useTenantStore();
const toast = useToastStore();
const { t, formatDateTime, formatNumber } = useI18n();

const categoriesCount = ref(0);
const dishesCount = ref(0);
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

const profile = computed(() => tenant.meta?.profile || {});
const published = computed(() => profile.value?.is_menu_published === true);
const isOpen = computed(() => profile.value?.is_open !== false);
const canCheckout = computed(() => tenant.entitlements?.can_checkout === true);
const canWhatsapp = computed(() => tenant.entitlements?.can_whatsapp_order === true);
const isBrowseOnlyPlan = computed(() => !canCheckout.value && !canWhatsapp.value);
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
const topCategories = computed(() => analyticsSummary.value?.top_categories || []);
const topDishes = computed(() => analyticsSummary.value?.top_dishes || []);
const pendingUpgrade = computed(() => upgradeRequests.value.find((request) => request.status === "pending") || null);
const hasPendingRequest = computed(() => Boolean(pendingUpgrade.value) || upgradeMeta.value.has_pending_request === true);
const topCategoryPeak = computed(() => Math.max(1, ...topCategories.value.map((item) => Number(item?.count || 0))));
const topDishPeak = computed(() => Math.max(1, ...topDishes.value.map((item) => Number(item?.count || 0))));
const readinessItems = computed(() => [
  {
    label: t("ownerHome.brandContactPresent"),
    note: t("ownerHome.quickActions"),
    ready: hasContact.value,
  },
  {
    label: t("ownerHome.themeConfigured"),
    note: t("ownerLayout.publicPreview"),
    ready: hasTheme.value,
  },
  {
    label: t("ownerHome.categoriesAdded"),
    note: `${categoriesCount.value} ${t("common.categories")}`,
    ready: categoriesCount.value > 0,
  },
  {
    label: t("ownerHome.dishesAdded"),
    note: `${dishesCount.value} ${t("common.dishes")}`,
    ready: dishesCount.value > 0,
  },
  {
    label: t("ownerHome.menuPublished"),
    note: planModeLabel.value,
    ready: published.value,
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
    categoriesCount.value = Array.isArray(cats.data) ? cats.data.length : 0;
    dishesCount.value = Array.isArray(dishes.data) ? dishes.data.length : 0;
    ensureUpgradeTargetSelection();
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

const humanizeSlug = (value) =>
  String(value || "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

const scaledCount = (value, max) => {
  const numeric = Number(value || 0);
  const denominator = Number(max || 1);
  if (!numeric || denominator <= 0) return 6;
  return Math.max(10, Math.min(100, Math.round((numeric / denominator) * 100)));
};

onMounted(async () => {
  await refresh();
});
</script>
