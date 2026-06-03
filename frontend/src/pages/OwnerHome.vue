<template>
  <section class="space-y-4 pb-24 sm:space-y-4 sm:pb-6">

    <!-- ── CRITICAL SECTION: renders on first paint from cached store data ──── -->
    <article class="ui-workspace-stage ui-fade-up space-y-4 p-3 sm:space-y-4 sm:p-4 md:p-4">

      <!-- Header row -->
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="space-y-1.5">
          <p class="ui-kicker">{{ t("ownerHome.kicker") }}</p>
          <h2 class="ui-page-title ui-display text-[1.42rem] leading-tight sm:text-[2rem]">{{ t("ownerHome.title") }}</h2>
        </div>
        <div class="ui-scroll-row">
          <span class="ui-chip-strong">{{ published ? t("ownerHome.published") : t("ownerHome.draft") }}</span>
          <span class="ui-chip">{{ planModeLabel }}</span>
        </div>
      </div>

      <!-- Open / Closed — the first thing an owner checks: are we taking orders? -->
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

      <!-- Today's snapshot — live from the order store (no heavy fetch) ─────── -->
      <!-- Skeleton while the first orders load -->
      <div v-if="order.ordersLoading && !order.orders.length" class="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
        <div v-for="i in 5" :key="i" class="ui-admin-subcard animate-pulse space-y-2">
          <div class="h-2.5 w-14 rounded bg-slate-700/60" />
          <div class="h-7 w-16 rounded bg-slate-700/40" />
          <div class="h-7 rounded bg-slate-800/40" />
        </div>
      </div>

      <div v-else class="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <!-- Today's orders -->
        <article class="ui-admin-subcard space-y-1">
          <p class="ui-stat-label">{{ t("ownerHome.todayOrders") }}</p>
          <div class="flex items-end justify-between gap-1">
            <p class="ui-stat-value text-slate-100">{{ todayStats.count }}</p>
            <span
              v-if="yesterdayStats.count > 0"
              class="mb-0.5 text-[10px] tabular-nums"
              :class="todayStats.count >= yesterdayStats.count ? 'text-emerald-500' : 'text-slate-500'"
            >{{ todayStats.count >= yesterdayStats.count ? '+' : '' }}{{ todayStats.count - yesterdayStats.count }}</span>
          </div>
        </article>

        <!-- Today's revenue -->
        <article class="ui-admin-subcard space-y-1">
          <p class="ui-stat-label">{{ t("ownerHome.todayRevenue") }}</p>
          <p class="ui-stat-value text-[var(--color-secondary)]">{{ todayStats.revenue }}</p>
        </article>

        <!-- Avg ticket today -->
        <article class="ui-admin-subcard space-y-1">
          <p class="ui-stat-label">{{ t("ownerHome.kpiAvgTicket") }}</p>
          <p class="ui-stat-value text-slate-100">{{ avgTicketLabel }}</p>
        </article>

        <!-- Pending orders -->
        <article class="ui-admin-subcard space-y-1 transition-colors" :class="todayStats.pending > 0 ? 'border-amber-500/30' : ''">
          <p class="ui-stat-label">{{ t("ownerOrders.todayPending") }}</p>
          <p class="ui-stat-value" :class="todayStats.pending > 0 ? 'text-amber-400' : 'text-slate-100'">{{ todayStats.pending }}</p>
        </article>
      </div>

      <!-- Alerts strip — shown below KPIs, above ratings -->
      <OwnerDashboardAlerts
        :sold-out-count="soldOutCount"
        :ratings-summary="ratingsSummary"
        @reset-complete="soldOutCount = 0"
      />

      <!-- Dish availability — pre-seeded with data from readiness to skip double-fetch -->
      <OwnerDashboardDishPanel
        :initial-sold-out-count="soldOutCount"
        :preloaded-dishes="preloadedDishesData"
      />

      <!-- Ratings strip — a passive metric, kept below the operational controls -->
      <template v-if="ratingsSummary">
        <RouterLink
          v-if="ratingsSummary.count > 0"
          :to="{ name: 'owner-ratings' }"
          class="flex items-center justify-between gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-2.5 transition hover:border-amber-500/35 hover:bg-amber-500/8"
        >
          <div class="flex items-center gap-2.5">
            <span class="text-amber-400 text-lg leading-none">★</span>
            <span class="text-sm font-bold text-white tabular-nums">{{ ratingsSummary.average !== null ? ratingsSummary.average.toFixed(1) : "—" }}</span>
            <span class="text-xs text-slate-500">/ 5 · {{ ratingsSummary.count }} {{ t("ownerHome.avgRating").toLowerCase() }}</span>
          </div>
          <span class="text-xs font-medium text-amber-400/80">{{ t("ownerHome.viewAllRatings") }} →</span>
        </RouterLink>
        <div v-else class="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950/30 px-4 py-2.5">
          <span class="text-sm text-slate-600">★</span>
          <span class="text-xs text-slate-600">{{ t("ownerHome.noRatingsYet") }}</span>
        </div>
      </template>
      <div v-else class="h-10 animate-pulse rounded-xl bg-slate-800/30" />

      <!-- Action buttons -->
      <div class="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:gap-3">
        <RouterLink :to="{ name: 'owner-menu-builder' }" class="ui-btn-primary col-span-2 w-full px-5 py-2.5 sm:w-auto">
          <AppIcon name="menu" class="owner-home-btn-icon" />
          {{ t("ownerHome.openMenuBuilder") }}
        </RouterLink>
        <RouterLink :to="{ name: 'owner-analytics' }" class="ui-btn-outline w-full px-4 py-2.5 sm:w-auto">
          <AppIcon name="chart" class="owner-home-btn-icon" />
          {{ t("ownerAnalytics.title") }}
        </RouterLink>
        <RouterLink to="/menu" class="ui-btn-outline w-full px-4 py-2.5 sm:w-auto">
          <AppIcon name="eye" class="owner-home-btn-icon" />
          {{ t("ownerLayout.publicPreview") }}
        </RouterLink>
        <button
          class="ui-btn-outline w-full px-4 py-2.5 sm:w-auto transition-colors"
          :class="copied ? 'border-emerald-500/50 text-emerald-300' : ''"
          @click="copyMenuUrl"
        >
          <AppIcon :name="copied ? 'check' : 'copy'" class="owner-home-btn-icon" />
          {{ copied ? t("ownerHome.menuUrlCopied") : t("ownerHome.copyPublicUrl") }}
        </button>
        <button class="ui-btn-outline col-span-2 w-full px-4 py-2.5 sm:w-auto" @click="manualRefresh">
          <AppIcon name="refresh" class="owner-home-btn-icon" />
          {{ t("common.refresh") }}
        </button>
      </div>
    </article>

    <!-- ── READINESS: independent fetch for categories + dishes ─────────────── -->
    <OwnerDashboardReadiness ref="readinessRef" @loaded="onReadinessLoaded" />

    <!-- ── LIVE ORDERS: from order store ───────────────────────────────────── -->
    <article class="ui-command-deck space-y-3 p-3 sm:space-y-4 sm:p-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="inline-flex items-center gap-2 text-lg font-semibold">
          <AppIcon name="cart" class="owner-home-section-icon" />
          <span>{{ t("ownerHome.liveOrders") }}</span>
          <span v-if="order.ordersLoading" class="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-500" />
        </h3>
        <RouterLink :to="{ name: 'owner-orders' }" class="ui-btn-outline px-3 py-1.5 text-xs">
          {{ t("ownerHome.viewAllOrders") }}
        </RouterLink>
      </div>

      <!-- Status summary chips -->
      <div class="flex flex-wrap gap-2">
        <div
          class="flex items-center gap-2 rounded-xl border px-3 py-2"
          :class="pendingOrders.length ? 'border-amber-500/60 bg-amber-500/10' : 'border-slate-700 bg-slate-900/40'"
        >
          <span class="text-xl font-bold" :class="pendingOrders.length ? 'text-amber-300' : 'text-slate-400'">{{ pendingOrders.length }}</span>
          <span class="text-xs font-medium" :class="pendingOrders.length ? 'text-amber-200' : 'text-slate-500'">{{ t("ownerOrders.statusPending") }}</span>
          <span v-if="pendingOrders.length" class="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
        </div>
        <div class="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/40 px-3 py-2">
          <span class="text-xl font-bold text-slate-300">{{ activeOrders.length }}</span>
          <span class="text-xs font-medium text-slate-500">{{ t("ownerHome.inProgress") }}</span>
        </div>
        <div
          v-if="!pendingOrders.length && !activeOrders.length && recentOrders.length"
          class="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/8 px-3 py-2"
        >
          <span class="text-emerald-400">✓</span>
          <span class="text-xs font-medium text-emerald-300/70">{{ t("ownerHome.allClear") }}</span>
        </div>
      </div>

      <!-- Recent orders list -->
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

    <!-- ── PLAN CARD ────────────────────────────────────────────────────────── -->
    <article class="ui-command-deck p-3 sm:p-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <h3 class="inline-flex items-center gap-2 text-base font-semibold">
            <AppIcon name="card" class="owner-home-section-icon" />
            <span>{{ t("ownerHome.planSection") }}</span>
          </h3>
          <div class="flex flex-wrap items-center gap-2">
            <span class="rounded-full border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/10 px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-[var(--color-secondary)]">
              {{ tenant.entitlements?.tier_name || tenant.meta?.plan?.name || "Basic" }}
            </span>
          </div>
        </div>
        <RouterLink :to="{ name: 'owner-profile', query: { tab: 'billing' } }" class="ui-btn-outline px-3 py-1.5 text-xs">
          {{ t("ownerBilling.manageBilling") }}
          <svg aria-hidden="true" viewBox="0 0 16 16" class="ml-1 inline h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 8h10M9 4l4 4-4 4" />
          </svg>
        </RouterLink>
      </div>
    </article>

  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";
import { RouterLink } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import OwnerDashboardAlerts from "../components/OwnerDashboardAlerts.vue";
import OwnerDashboardReadiness from "../components/OwnerDashboardReadiness.vue";
import OwnerDashboardDishPanel from "../components/OwnerDashboardDishPanel.vue";
import { useI18n } from "../composables/useI18n";
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
const { t, formatNumber, currentLocale } = useI18n();

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

// ── Profile-derived state ─────────────────────────────────────────────────────
const profile = computed(() => tenant.meta?.profile || {});
const published = computed(() => profile.value?.is_menu_published === true);
const isOpen = computed(() => profile.value?.is_open !== false);
const togglingOpen = ref(false);

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
const pendingOrders = computed(() => order.orders.filter((o) => o.status === "pending"));
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

// ── Order helpers ─────────────────────────────────────────────────────────────
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
  if (copyResetTimer !== null) clearTimeout(copyResetTimer);
  if (typeof document !== "undefined") {
    document.removeEventListener("visibilitychange", onVisibilityChange);
  }
});
</script>

<style scoped>
.owner-home-btn-icon { width: 0.86rem; height: 0.86rem; }
.owner-home-section-icon { width: 1rem; height: 1rem; color: var(--color-secondary); }
</style>
