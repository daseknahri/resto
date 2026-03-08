<template>
  <section class="space-y-6 pb-24 sm:pb-6">
    <header class="space-y-3 ui-fade-up">
      <p class="ui-kicker">Owner dashboard</p>
      <h2 class="ui-page-title ui-display">Launch and manage your menu</h2>
      <p class="max-w-3xl text-sm text-slate-300">Track readiness, complete setup, and publish a stable customer experience.</p>
    </header>

    <div class="grid gap-4 md:grid-cols-4">
      <article class="ui-panel p-4 ui-fade-up">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Readiness</p>
        <p class="mt-2 text-3xl font-semibold text-[var(--color-secondary)]">{{ readinessScore }}%</p>
        <p class="text-xs text-slate-400">Based on contact, theme, content, and publish status.</p>
      </article>

      <article class="ui-panel p-4 ui-fade-up">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Categories</p>
        <p class="mt-2 text-3xl font-semibold">{{ categoriesCount }}</p>
        <p class="text-xs text-slate-400">Target: at least 3 for better browsing.</p>
      </article>

      <article class="ui-panel p-4 ui-fade-up">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Dishes</p>
        <p class="mt-2 text-3xl font-semibold">{{ dishesCount }}</p>
        <p class="text-xs text-slate-400">Target: at least 8 for launch quality.</p>
      </article>

      <article class="ui-panel p-4 ui-fade-up">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">State</p>
        <p class="mt-2 text-xl font-semibold" :class="published ? 'text-emerald-300' : 'text-amber-300'">
          {{ published ? "Published" : "Draft" }}
        </p>
        <p class="text-xs text-slate-400">{{ isOpen ? "Restaurant open" : "Restaurant closed" }}</p>
        <p class="mt-1 text-xs" :class="isBrowseOnlyPlan ? 'text-sky-300' : 'text-slate-400'">
          {{ planModeLabel }}
        </p>
      </article>
    </div>

    <article class="ui-panel p-5 space-y-3">
      <div class="flex items-center justify-between gap-2">
        <p class="text-sm text-slate-300">Launch readiness progress</p>
        <span class="text-sm font-semibold text-[var(--color-secondary)]">{{ readinessScore }}%</span>
      </div>
      <div class="h-2 overflow-hidden rounded-full bg-slate-800">
        <div class="h-full rounded-full bg-[var(--color-secondary)] transition-all duration-300" :style="{ width: `${readinessScore}%` }"></div>
      </div>
      <p class="text-xs text-slate-500">Push to 100% before paid campaigns and QR rollout.</p>
    </article>

    <article class="ui-panel p-5 space-y-4">
      <div class="flex items-center justify-between gap-2">
        <h3 class="text-lg font-semibold">30-day menu analytics</h3>
        <p class="text-xs text-slate-400">Auto-collected from customer interactions</p>
      </div>
      <div class="grid gap-3 md:grid-cols-4">
        <div class="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Menu views</p>
          <p class="mt-2 text-2xl font-semibold text-slate-100">{{ analyticsCounts.menu_view || 0 }}</p>
        </div>
        <div class="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Dish views</p>
          <p class="mt-2 text-2xl font-semibold text-slate-100">{{ analyticsCounts.dish_view || 0 }}</p>
        </div>
        <div class="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Order actions</p>
          <p class="mt-2 text-2xl font-semibold text-slate-100">{{ orderActionsCount }}</p>
        </div>
        <div class="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Interaction rate</p>
          <p class="mt-2 text-2xl font-semibold text-[var(--color-secondary)]">{{ interactionRateLabel }}</p>
        </div>
      </div>
      <div class="grid gap-3 md:grid-cols-2">
        <div class="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Top categories</p>
          <ul class="mt-2 space-y-1 text-sm text-slate-200">
            <li v-for="item in topCategories" :key="item.category_slug" class="flex items-center justify-between">
              <span>{{ humanizeSlug(item.category_slug) }}</span>
              <span class="text-slate-400">{{ item.count }}</span>
            </li>
            <li v-if="!topCategories.length" class="text-slate-500">No data yet.</li>
          </ul>
        </div>
        <div class="rounded-xl border border-slate-700/60 bg-slate-900/50 p-3">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Top dishes</p>
          <ul class="mt-2 space-y-1 text-sm text-slate-200">
            <li v-for="item in topDishes" :key="item.dish_slug" class="flex items-center justify-between">
              <span>{{ humanizeSlug(item.dish_slug) }}</span>
              <span class="text-slate-400">{{ item.count }}</span>
            </li>
            <li v-if="!topDishes.length" class="text-slate-500">No data yet.</li>
          </ul>
        </div>
      </div>
    </article>

    <article class="ui-panel p-5 space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="text-lg font-semibold">Launch checklist</h3>
        <button
          class="ui-btn-outline px-3 py-1.5 text-xs"
          :disabled="loading"
          @click="refresh"
        >
          {{ loading ? "Refreshing..." : "Refresh" }}
        </button>
      </div>
      <ul class="grid gap-2 md:grid-cols-2">
        <li class="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2 text-sm">
          <span>Brand contact present</span>
          <span :class="hasContact ? 'text-emerald-300' : 'text-amber-300'">{{ hasContact ? "Ready" : "Missing" }}</span>
        </li>
        <li class="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2 text-sm">
          <span>Theme configured</span>
          <span :class="hasTheme ? 'text-emerald-300' : 'text-amber-300'">{{ hasTheme ? "Ready" : "Missing" }}</span>
        </li>
        <li class="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2 text-sm">
          <span>Categories added</span>
          <span :class="categoriesCount > 0 ? 'text-emerald-300' : 'text-amber-300'">{{ categoriesCount > 0 ? "Ready" : "Missing" }}</span>
        </li>
        <li class="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2 text-sm">
          <span>Dishes added</span>
          <span :class="dishesCount > 0 ? 'text-emerald-300' : 'text-amber-300'">{{ dishesCount > 0 ? "Ready" : "Missing" }}</span>
        </li>
        <li class="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2 text-sm">
          <span>Menu published</span>
          <span :class="published ? 'text-emerald-300' : 'text-amber-300'">{{ published ? "Ready" : "Pending" }}</span>
        </li>
      </ul>
    </article>

    <article class="ui-panel p-5 space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 class="text-lg font-semibold">Purchase tier upgrade</h3>
          <p class="text-xs text-slate-400">Current plan: {{ tenant.entitlements?.tier_name || tenant.meta?.plan?.name || "Basic" }}</p>
        </div>
        <button class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="upgradeLoading" @click="fetchUpgradeRequests">
          {{ upgradeLoading ? "Loading..." : "Refresh requests" }}
        </button>
      </div>

      <p v-if="hasPendingRequest" class="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
        You already have a pending upgrade request{{ pendingUpgrade ? ` for ${pendingUpgrade.target_plan_name}` : "" }}. Wait for admin confirmation.
      </p>

      <div v-if="upgradeTargets.length" class="grid gap-3 md:grid-cols-[1fr,2fr,auto]">
        <label class="text-sm text-slate-300">
          Target tier
          <select v-model="upgradeTargetCode" class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
            <option v-for="target in upgradeTargets" :key="target.code" :value="target.code">
              {{ target.name }}{{ target.is_active ? "" : " (coming soon)" }}
            </option>
          </select>
        </label>
        <label class="text-sm text-slate-300">
          Message to admin (optional)
          <input
            v-model.trim="upgradeCustomerNote"
            type="text"
            maxlength="1500"
            placeholder="Please enable Growth for my restaurant."
            class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
        </label>
        <div class="flex items-end">
          <button
            class="ui-btn-primary w-full px-4 py-2 text-sm disabled:opacity-60"
            :disabled="upgradeSubmitting || hasPendingRequest || !upgradeTargetCode"
            @click="submitUpgradeRequest"
          >
            {{ upgradeSubmitting ? "Sending..." : "Purchase tier" }}
          </button>
        </div>
      </div>
      <p v-else class="text-sm text-slate-400">You are already on the highest available tier.</p>
      <p v-if="upgradeError" class="text-sm text-red-300">{{ upgradeError }}</p>

      <div class="space-y-2">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Recent requests</p>
        <div class="overflow-hidden rounded-xl border border-slate-800 hidden md:block">
          <table class="min-w-full text-sm">
            <thead class="bg-slate-900/80 text-slate-400">
              <tr>
                <th class="px-3 py-2 text-left">When</th>
                <th class="px-3 py-2 text-left">From</th>
                <th class="px-3 py-2 text-left">To</th>
                <th class="px-3 py-2 text-left">Status</th>
                <th class="px-3 py-2 text-left">Admin note</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="request in upgradeRequests" :key="request.id" class="border-t border-slate-800">
                <td class="px-3 py-2 text-slate-300">{{ new Date(request.requested_at).toLocaleString() }}</td>
                <td class="px-3 py-2 text-slate-200">{{ request.current_plan_name }}</td>
                <td class="px-3 py-2 text-slate-200">{{ request.target_plan_name }}</td>
                <td class="px-3 py-2">
                  <span
                    class="rounded-full px-2 py-1 text-xs font-semibold"
                    :class="upgradeStatusClass(request.status)"
                  >
                    {{ request.status }}
                  </span>
                </td>
                <td class="px-3 py-2 text-slate-400">{{ request.admin_note || "-" }}</td>
              </tr>
              <tr v-if="!upgradeRequests.length && !upgradeLoading">
                <td colspan="5" class="px-3 py-3 text-slate-500">No upgrade requests yet.</td>
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
              <p class="text-xs text-slate-400">{{ new Date(request.requested_at).toLocaleString() }}</p>
              <span class="rounded-full px-2 py-1 text-xs font-semibold" :class="upgradeStatusClass(request.status)">
                {{ request.status }}
              </span>
            </div>
            <p class="text-sm text-slate-100">{{ request.current_plan_name }} -> {{ request.target_plan_name }}</p>
            <p class="text-xs text-slate-400">{{ request.admin_note || "No admin note yet." }}</p>
          </article>
          <p v-if="!upgradeRequests.length && !upgradeLoading" class="text-xs text-slate-500">No upgrade requests yet.</p>
        </div>
      </div>
    </article>

    <article class="ui-panel p-5 space-y-4">
      <h3 class="text-lg font-semibold">Quick actions</h3>
      <div class="flex flex-wrap gap-3">
        <RouterLink to="/owner/onboarding" class="ui-btn-primary">
          Open menu builder
        </RouterLink>
        <button class="ui-btn-outline" @click="copyMenuUrl">
          Copy public URL
        </button>
      </div>
      <p v-if="error" class="text-sm text-red-300">{{ error }}</p>
      <p v-if="copied" class="text-xs text-emerald-300">Menu URL copied.</p>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import api from "../lib/api";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const tenant = useTenantStore();
const toast = useToastStore();

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
  if (canCheckout.value) return "Checkout enabled";
  if (canWhatsapp.value) return "WhatsApp ordering enabled";
  return "Browse-only mode";
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
const interactionRateLabel = computed(() => `${Number(analyticsSummary.value?.interaction_rate_pct || 0).toFixed(1)}%`);
const topCategories = computed(() => analyticsSummary.value?.top_categories || []);
const topDishes = computed(() => analyticsSummary.value?.top_dishes || []);
const currentTierCode = computed(() => upgradeMeta.value.current_tier_code || tenant.entitlements?.tier_code || "basic");
const pendingUpgrade = computed(() => upgradeRequests.value.find((request) => request.status === "pending") || null);
const hasPendingRequest = computed(() => Boolean(pendingUpgrade.value) || upgradeMeta.value.has_pending_request === true);

const refresh = async () => {
  loading.value = true;
  error.value = "";
  try {
    await tenant.fetchMeta();
    const [cats, dishes] = await Promise.all([api.get("/categories/"), api.get("/dishes/")]);
    categoriesCount.value = Array.isArray(cats.data) ? cats.data.length : 0;
    dishesCount.value = Array.isArray(dishes.data) ? dishes.data.length : 0;
    try {
      const analytics = await api.get("/analytics/summary/", { params: { days: 30 } });
      analyticsSummary.value = analytics?.data || analyticsSummary.value;
    } catch (analyticsErr) {
      // Keep dashboard usable even if analytics endpoint is unavailable.
    }
    await Promise.all([fetchUpgradeTargets(), fetchUpgradeRequests()]);
  } catch (err) {
    error.value = "Unable to refresh dashboard metrics.";
    toast.show(error.value, "error");
  } finally {
    loading.value = false;
  }
};

const menuUrl = computed(() => (typeof window === "undefined" ? "/menu" : `${window.location.origin}/menu`));

const copyMenuUrl = async () => {
  try {
    await navigator.clipboard.writeText(menuUrl.value);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 1800);
  } catch (err) {
    toast.show("Copy failed", "error");
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
    const { data } = await api.get("/tier-upgrade-targets/");
    const targets = Array.isArray(data?.targets) ? data.targets : [];
    upgradeTargets.value = targets;
    upgradeMeta.value = {
      current_tier_code: data?.current_tier_code || tenant.entitlements?.tier_code || "basic",
      current_tier_name: data?.current_tier_name || tenant.entitlements?.tier_name || "Basic",
      has_pending_request: data?.has_pending_request === true,
    };
    ensureUpgradeTargetSelection();
  } catch (err) {
    upgradeTargets.value = [];
  }
};

const fetchUpgradeRequests = async () => {
  upgradeLoading.value = true;
  upgradeError.value = "";
  try {
    const { data } = await api.get("/tier-upgrade-requests/");
    upgradeRequests.value = Array.isArray(data) ? data : [];
    upgradeMeta.value = {
      ...upgradeMeta.value,
      has_pending_request: upgradeRequests.value.some((request) => request.status === "pending"),
    };
    ensureUpgradeTargetSelection();
  } catch (err) {
    upgradeError.value = "Unable to load upgrade requests.";
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
    toast.show("Upgrade request sent. We will confirm payment and activate your tier.", "success");
    await Promise.all([fetchUpgradeTargets(), fetchUpgradeRequests()]);
  } catch (err) {
    const detail = err?.response?.data?.detail;
    upgradeError.value = typeof detail === "string" ? detail : "Unable to submit upgrade request.";
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

const humanizeSlug = (value) =>
  String(value || "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

onMounted(async () => {
  await refresh();
});
</script>
