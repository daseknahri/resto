<template>
  <div class="px-4 py-6 sm:px-6">
    <!-- Header -->
    <div class="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 class="text-xl font-bold text-slate-100">{{ t("ownerCustomers.title") }}</h1>
        <p class="mt-0.5 text-sm text-slate-400">{{ t("ownerCustomers.subtitle") }}</p>
      </div>
      <button
        class="ui-btn-secondary flex items-center gap-1.5 text-xs"
        :disabled="loading"
        @click="exportCsv"
      >
        <AppIcon name="download" class="h-3.5 w-3.5" />
        {{ t("ownerCustomers.exportCsv") }}
      </button>
    </div>

    <!-- Summary bar skeleton -->
    <div v-if="!summary && loading" class="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
      <div v-for="i in 4" :key="i" class="animate-pulse rounded-2xl border border-slate-700/60 bg-slate-900/60 px-4 py-3 space-y-2">
        <div class="h-2.5 w-16 rounded bg-slate-700/60" />
        <div class="h-7 w-10 rounded bg-slate-800/60" />
      </div>
    </div>

    <!-- Summary bar -->
    <div v-if="summary" class="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
      <button
        v-for="seg in segments"
        :key="seg.key"
        class="rounded-2xl border px-4 py-3 text-left transition"
        :class="
          activeSegment === seg.key
            ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
            : 'border-slate-700/60 bg-slate-900/60 text-slate-300 hover:border-slate-600'
        "
        @click="setSegment(seg.key)"
      >
        <p class="text-xs font-medium opacity-70">{{ seg.label }}</p>
        <p class="mt-0.5 text-2xl font-bold">{{ summary[seg.key] ?? 0 }}</p>
      </button>
    </div>

    <!-- Search -->
    <div class="mb-4 flex items-center gap-2">
      <div class="relative flex-1">
        <AppIcon name="search" class="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
        <input
          v-model="search"
          type="text"
          :aria-label="t('ownerCustomers.searchPlaceholder')"
          :placeholder="t('ownerCustomers.searchPlaceholder')"
          class="ui-input w-full pl-8 text-sm"
          @input="onSearch"
        />
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="mb-4 flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
      <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t("ownerCustomers.loadError") }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="fetchCustomers"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-2">
      <div v-for="i in 6" :key="i" class="h-14 animate-pulse rounded-2xl bg-slate-800/60" />
    </div>

    <!-- Table -->
    <div v-else-if="customers.length" class="overflow-x-auto rounded-2xl border border-slate-700/50">
      <table class="w-full min-w-[820px] text-sm">
        <thead>
          <tr class="border-b border-slate-700/50 bg-slate-900/60 text-xs text-slate-400">
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-4 py-2.5 text-left font-medium"
              :class="col.sortable ? 'cursor-pointer select-none hover:text-slate-200' : ''"
              @click="col.sortable && toggleSort(col.key)"
            >
              <span class="inline-flex items-center gap-1">
                {{ col.label }}
                <span v-if="col.sortable" class="text-[10px] opacity-50">
                  {{ sortKey === col.key ? (sortOrder === 'desc' ? '▼' : '▲') : '⇅' }}
                </span>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in customers"
            :key="c.id"
            class="border-b border-slate-800/60 transition hover:bg-slate-800/30"
          >
            <!-- Name + type -->
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <span
                  class="shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide"
                  :class="c.type === 'account' ? 'bg-sky-500/20 text-sky-300' : 'bg-slate-700/60 text-slate-400'"
                >
                  {{ c.type === 'account' ? t('ownerCustomers.typeAccount') : t('ownerCustomers.typeAnonymous') }}
                </span>
                <span class="font-medium text-slate-100">{{ c.name }}</span>
              </div>
            </td>
            <!-- Contact -->
            <td class="px-4 py-3 text-slate-400">
              <div v-if="c.phone" class="text-xs">{{ c.phone }}</div>
              <div v-if="c.email" class="text-xs">{{ c.email }}</div>
            </td>
            <!-- Orders -->
            <td class="px-4 py-3 text-slate-200">{{ c.order_count }}</td>
            <!-- Total spend -->
            <td class="px-4 py-3 text-slate-200">
              {{ formatMoney(c.total_spend, c.currency) }}
            </td>
            <!-- Avg order -->
            <td class="px-4 py-3 text-slate-400">
              {{ formatMoney(c.avg_order_value, c.currency) }}
            </td>
            <!-- Last order -->
            <td class="px-4 py-3 text-slate-400">
              {{ c.last_order_at ? formatDate(c.last_order_at) : '—' }}
            </td>
            <!-- Trust score -->
            <td class="px-4 py-3">
              <span v-if="c.trust_score != null" :class="trustClass(c.trust_score)">
                {{ c.trust_score.toFixed(1) }}
              </span>
              <span v-else class="text-slate-600">{{ t("ownerCustomers.trustNa") }}</span>
            </td>
            <!-- Reviews (customer's ratings of the restaurant) -->
            <td class="px-4 py-3">
              <span v-if="c.avg_review != null" class="inline-flex items-center gap-1">
                <span class="text-amber-400 text-xs leading-none">★</span>
                <span :class="reviewScoreClass(c.avg_review)" class="font-semibold tabular-nums">{{ c.avg_review.toFixed(1) }}</span>
                <span v-if="c.review_count > 1" class="text-[10px] text-slate-600">({{ c.review_count }})</span>
              </span>
              <span v-else class="text-slate-600">{{ t("ownerCustomers.reviewNa") }}</span>
            </td>
            <!-- Segment -->
            <td class="px-4 py-3">
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="segmentBadgeClass(c.segment)"
              >
                {{ segmentLabel(c.segment) }}
              </span>
            </td>
            <!-- Wallet balance -->
            <td class="px-4 py-3">
              <div v-if="c.customer_id && parseFloat(c.wallet_balance) > 0" class="flex items-center gap-2">
                <span class="font-semibold tabular-nums text-emerald-400 text-xs">{{ formatMoney(parseFloat(c.wallet_balance), c.currency) }}</span>
                <RouterLink
                  :to="{ name: 'owner-wallet', query: { q: c.name } }"
                  class="rounded-full border border-slate-600 px-2 py-0.5 text-[10px] font-semibold text-slate-400 hover:border-[var(--color-secondary)]/60 hover:text-[var(--color-secondary)] transition-colors"
                >{{ t('ownerCustomers.topUpBtn') }}</RouterLink>
              </div>
              <span v-else-if="c.customer_id" class="text-slate-600 text-xs">0</span>
              <span v-else class="text-slate-700 text-xs">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Empty -->
    <div v-else-if="!loading" class="py-16 text-center text-sm text-slate-500">
      {{ t("ownerCustomers.noResults") }}
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";

const { t, currentLocale } = useI18n();

// ── State ─────────────────────────────────────────────────────────────────────
const loading = ref(false);
const error = ref(false);
const customers = ref([]);
const summary = ref(null);

const activeSegment = ref("total");
const search = ref("");
const sortKey = ref("last_order");
const sortOrder = ref("desc");

let searchTimer = null;

// ── Segment config ─────────────────────────────────────────────────────────────
const segments = computed(() => [
  { key: "total",     label: t("ownerCustomers.segmentAll") },
  { key: "new",       label: t("ownerCustomers.segmentNew") },
  { key: "returning", label: t("ownerCustomers.segmentReturning") },
  { key: "at_risk",   label: t("ownerCustomers.segmentAtRisk") },
]);

// ── Table columns ─────────────────────────────────────────────────────────────
const columns = computed(() => [
  { key: "name",     label: t("ownerCustomers.colName"),    sortable: false },
  { key: "contact",  label: t("ownerCustomers.colContact"), sortable: false },
  { key: "order_count", label: t("ownerCustomers.colOrders"), sortable: true },
  { key: "total_spend", label: t("ownerCustomers.colSpend"), sortable: true },
  { key: "avg_order_value", label: t("ownerCustomers.colAvg"), sortable: false },
  { key: "last_order",  label: t("ownerCustomers.colLast"),  sortable: true },
  { key: "trust_score", label: t("ownerCustomers.colTrust"), sortable: false },
  { key: "avg_review",  label: t("ownerCustomers.colReview"), sortable: false },
  { key: "segment",     label: t("ownerCustomers.colSegment"), sortable: false },
  { key: "wallet",      label: t("ownerCustomers.colWallet"), sortable: false },
]);

// ── API ───────────────────────────────────────────────────────────────────────
const fetchCustomers = async () => {
  loading.value = true;
  error.value = false;
  try {
    const params = {
      sort: sortKey.value,
      order: sortOrder.value,
    };
    if (activeSegment.value !== "total") params.segment = activeSegment.value;
    if (search.value.trim()) params.search = search.value.trim();

    const { data } = await api.get("/owner/customers/", { params });
    customers.value = data.customers || [];
    summary.value = data.summary || null;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

// ── Interactions ──────────────────────────────────────────────────────────────
const setSegment = (key) => {
  activeSegment.value = key;
  fetchCustomers();
};

const onSearch = () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(fetchCustomers, 350);
};

const toggleSort = (key) => {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === "desc" ? "asc" : "desc";
  } else {
    sortKey.value = key;
    sortOrder.value = "desc";
  }
  fetchCustomers();
};

const exportCsv = async () => {
  const params = new URLSearchParams({ format: "csv", sort: sortKey.value, order: sortOrder.value });
  if (activeSegment.value !== "total") params.set("segment", activeSegment.value);
  if (search.value.trim()) params.set("search", search.value.trim());
  const url = `/api/owner/customers/?${params.toString()}`;
  const a = document.createElement("a");
  a.href = url;
  a.download = "customers.csv";
  a.click();
};

// ── Formatters ────────────────────────────────────────────────────────────────
const formatMoney = (amount, currency) => {
  if (amount == null) return "—";
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: "currency",
      currency: currency || "MAD",
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency || ""} ${Number(amount).toFixed(2)}`.trim();
  }
};

const formatDate = (iso) => {
  try {
    return new Intl.DateTimeFormat(currentLocale.value, {
      year: "numeric", month: "short", day: "numeric",
    }).format(new Date(iso));
  } catch {
    return iso?.slice(0, 10) ?? "—";
  }
};

const segmentLabel = (seg) => {
  const map = {
    new: t("ownerCustomers.segTagNew"),
    returning: t("ownerCustomers.segTagReturning"),
    at_risk: t("ownerCustomers.segTagAtRisk"),
  };
  return map[seg] ?? seg;
};

const segmentBadgeClass = (seg) => {
  if (seg === "new")       return "bg-sky-500/20 text-sky-300";
  if (seg === "returning") return "bg-emerald-500/20 text-emerald-300";
  if (seg === "at_risk")   return "bg-amber-500/20 text-amber-300";
  return "bg-slate-700/40 text-slate-400";
};

const trustClass = (score) => {
  if (score >= 4) return "font-semibold text-emerald-400";
  if (score >= 3) return "font-semibold text-amber-400";
  return "font-semibold text-red-400";
};

const reviewScoreClass = (score) => {
  if (score >= 4) return "text-emerald-400";
  if (score >= 3) return "text-amber-400";
  return "text-red-400";
};

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(fetchCustomers);
watch(currentLocale, fetchCustomers);
</script>
