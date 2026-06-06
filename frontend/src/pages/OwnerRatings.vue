<template>
  <div class="space-y-4">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal space-y-3 p-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 space-y-0.5">
          <p class="ui-section-kicker">{{ t("ownerRatings.kicker") }}</p>
          <h1 class="ui-display text-xl font-semibold text-white sm:text-2xl">{{ t("ownerRatings.title") }}</h1>
          <p class="ui-subtle">{{ t("ownerRatings.description") }}</p>
        </div>
        <div class="flex shrink-0 flex-wrap items-center gap-2">
          <button
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1.5 px-3 text-sm"
            :disabled="exporting || !ratings.length"
            @click="exportCsv"
          >
            <AppIcon name="download" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ exporting ? t("ownerRatings.exporting") : t("ownerRatings.exportCsv") }}
          </button>
          <button
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1.5 px-3 text-sm"
            :disabled="loading || updating"
            @click="fetchRatings(true)"
          >
            <AppIcon name="refresh" class="h-3.5 w-3.5" :class="updating ? 'animate-spin' : ''" aria-hidden="true" />
            {{ t("ownerRatings.refresh") }}
          </button>
        </div>
      </div>

      <!-- Summary stats skeleton -->
      <div v-if="loading && !summary" class="animate-pulse grid grid-cols-3 gap-2 rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-3">
        <div class="flex flex-col items-center gap-1.5">
          <div class="h-6 w-10 rounded bg-slate-700/50" />
          <div class="h-2.5 w-16 rounded bg-slate-800/50" />
        </div>
        <div class="flex flex-col items-center gap-1.5 border-x border-slate-800">
          <div class="h-6 w-10 rounded bg-slate-700/50" />
          <div class="h-2.5 w-16 rounded bg-slate-800/50" />
        </div>
        <div class="flex flex-col items-center gap-1.5">
          <div class="h-6 w-10 rounded bg-slate-700/50" />
          <div class="h-2.5 w-16 rounded bg-slate-800/50" />
        </div>
      </div>

      <!-- Summary stats -->
      <div v-if="summary" class="grid grid-cols-3 gap-px overflow-hidden rounded-xl border border-slate-800 bg-slate-800">
        <div class="bg-slate-950/70 px-3 py-3 text-center">
          <p class="text-xl font-bold text-white tabular-nums">{{ summary.count }}</p>
          <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerRatings.totalRatings") }}</p>
        </div>
        <div class="bg-slate-950/70 px-3 py-3 text-center">
          <p class="text-xl font-bold text-amber-400 tabular-nums">
            {{ summary.average !== null ? summary.average.toFixed(1) : "—" }}
          </p>
          <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerRatings.averageScore") }}</p>
        </div>
        <div class="bg-slate-950/70 px-3 py-3 text-center">
          <p class="text-xl font-bold text-white tabular-nums">{{ summary.comments }}</p>
          <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerRatings.withComments") }}</p>
        </div>
      </div>

      <!-- Score distribution bar -->
      <div v-if="ratings.length" class="space-y-1.5">
        <div v-for="s in [5, 4, 3, 2, 1]" :key="s" class="flex items-center gap-2 text-xs">
          <span class="w-4 shrink-0 text-end font-semibold text-amber-400 tabular-nums">{{ s }}</span>
          <div class="h-2 min-w-0 flex-1 rounded-full bg-slate-800" role="progressbar" :aria-valuenow="scorePercent(s)" aria-valuemin="0" aria-valuemax="100">
            <div
              class="h-full rounded-full bg-amber-400/70 transition-all duration-500"
              :style="{ width: `${scorePercent(s)}%` }"
            />
          </div>
          <span class="w-6 shrink-0 tabular-nums text-slate-500">{{ scoreCounts[s] || 0 }}</span>
        </div>
      </div>

      <!-- Score filter pills -->
      <div v-if="ratings.length" class="ui-scroll-row min-w-0 max-w-full">
        <button
          v-for="f in scoreFilters"
          :key="f.value"
          type="button"
          class="ui-chip ui-press shrink-0"
          :class="activeScore === f.value ? 'router-link-active' : ''"
          :aria-pressed="activeScore === f.value"
          @click="activeScore = f.value"
        >
          {{ f.label }}
        </button>
      </div>
    </header>

    <!-- Loading: skeleton cards -->
    <div v-if="loading" class="space-y-3" aria-busy="true">
      <div
        v-for="i in 4"
        :key="i"
        class="ui-skeleton h-28"
        :style="{ '--ui-delay': `${(i - 1) * 28}ms` }"
      />
    </div>

    <!-- Empty -->
    <div v-else-if="!ratings.length" class="ui-empty-state ui-reveal text-center">
      <AppIcon name="star" class="mx-auto mb-2 h-8 w-8 text-slate-600" aria-hidden="true" />
      <p class="text-sm font-semibold text-slate-100">{{ t("ownerRatings.emptyTitle") }}</p>
      <p class="text-xs text-slate-400">{{ t("ownerRatings.emptyBody") }}</p>
    </div>

    <!-- Ratings list -->
    <div v-else class="space-y-3">
      <article
        v-for="(r, index) in filtered"
        :key="r.id"
        class="ui-panel ui-surface-lift ui-reveal p-4 space-y-2.5"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
      >
        <!-- Top row: stars + score · date -->
        <div class="flex flex-wrap items-start justify-between gap-2">
          <!-- Stars + score -->
          <div class="flex items-center gap-2">
            <span class="text-lg leading-none text-amber-400" aria-hidden="true">{{ "★".repeat(r.score) }}<span class="text-slate-600">{{ "★".repeat(5 - r.score) }}</span></span>
            <span
              class="rounded-full px-2 py-0.5 text-xs font-bold"
              :class="{
                'bg-emerald-500/15 text-emerald-300': r.score >= 4,
                'bg-amber-500/15 text-amber-300': r.score === 3,
                'bg-red-500/15 text-red-300': r.score <= 2,
              }"
            >{{ r.score }}/5</span>
          </div>
          <!-- Date -->
          <p class="text-xs tabular-nums text-slate-500">{{ formatDate(r.created_at) }}</p>
        </div>

        <!-- Customer + order info row -->
        <div class="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span v-if="r.customer_name" class="flex min-w-0 items-center gap-1 font-medium text-slate-200">
            <AppIcon name="user" class="h-3 w-3 shrink-0 text-slate-500" aria-hidden="true" />
            <span class="truncate">{{ r.customer_name }}</span>
          </span>
          <span v-if="r.customer_name && r.order_number" class="text-slate-600" aria-hidden="true">·</span>
          <RouterLink
            :to="{ name: 'owner-orders', query: { q: r.order_number } }"
            class="font-mono text-slate-400 transition hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/50 rounded"
          >#{{ r.order_number }}</RouterLink>
        </div>

        <!-- Comment -->
        <p v-if="r.comment" class="rounded-lg border-s-2 border-slate-700 bg-slate-900/40 py-2 ps-3 pe-3 text-sm italic leading-relaxed text-slate-300">{{ r.comment }}</p>
        <p v-else class="text-xs italic text-slate-600">{{ t("ownerRatings.noComment") }}</p>
      </article>

      <!-- No matches for current filter -->
      <div v-if="!filtered.length && activeScore !== 'all'" class="ui-empty-state text-center">
        <p class="text-sm font-semibold text-slate-100">{{ t("ownerRatings.noMatchFilter") }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onActivated, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { useToastStore } from "../stores/toast";
import { bustCache, isFresh, readCache, writeCache } from "../lib/staleCache";

const { t, currentLocale } = useI18n();
const toast = useToastStore();

const RATINGS_CACHE_KEY = "owner.ratings";
const RATINGS_TTL_MS = 5 * 60 * 1000; // 5 min

const ratings = ref([]);
const loading = ref(false);
const updating = ref(false); // silently revalidating stale cache
const exporting = ref(false);
const activeScore = ref("all");

const scoreFilters = computed(() => [
  { value: "all", label: t("ownerRatings.filterAll") },
  { value: 5, label: "★★★★★" },
  { value: 4, label: "★★★★" },
  { value: 3, label: "★★★" },
  { value: 2, label: "★★" },
  { value: 1, label: "★" },
]);

const filtered = computed(() =>
  activeScore.value === "all"
    ? ratings.value
    : ratings.value.filter((r) => r.score === activeScore.value)
);

const scoreCounts = computed(() => {
  const counts = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
  ratings.value.forEach((r) => { counts[r.score] = (counts[r.score] || 0) + 1; });
  return counts;
});

const scorePercent = (s) => {
  if (!ratings.value.length) return 0;
  return Math.round(((scoreCounts.value[s] || 0) / ratings.value.length) * 100);
};

const summary = computed(() => {
  if (!ratings.value.length) return null;
  const total = ratings.value.length;
  const avg = ratings.value.reduce((sum, r) => sum + r.score, 0) / total;
  const comments = ratings.value.filter((r) => r.comment?.trim()).length;
  return { count: total, average: avg, comments };
});

const formatDate = (iso) => {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
  } catch {
    return iso;
  }
};

const fetchRatings = async (force = false) => {
  if (force) bustCache(RATINGS_CACHE_KEY);
  const cached = readCache(RATINGS_CACHE_KEY);
  if (cached) {
    ratings.value = cached;
    if (isFresh(RATINGS_CACHE_KEY, RATINGS_TTL_MS)) return;
    updating.value = true; // stale — revalidate silently
  } else {
    loading.value = true;
  }
  try {
    const res = await api.get("/owner/ratings/");
    const data = res.data?.ratings ?? res.data ?? [];
    ratings.value = data;
    writeCache(RATINGS_CACHE_KEY, data);
  } catch {
    if (!cached) toast.show(t("ownerRatings.fetchError"), "error");
  } finally {
    loading.value = false;
    updating.value = false;
  }
};

const exportCsv = async () => {
  exporting.value = true;
  try {
    const res = await api.get("/owner/ratings/?format=csv", { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = "ratings.csv";
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    toast.show(t("ownerRatings.exportError"), "error");
  } finally {
    exporting.value = false;
  }
};

onMounted(() => fetchRatings());

// Kept alive — silently revalidate on revisit (cached view shows instantly).
let _activatedOnce = false;
onActivated(() => {
  if (!_activatedOnce) { _activatedOnce = true; return; }
  fetchRatings();
});
</script>
