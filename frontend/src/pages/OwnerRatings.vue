<template>
  <div class="space-y-4">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal space-y-4 px-4 py-4 sm:px-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 space-y-1">
          <p class="ui-kicker">{{ t("ownerRatings.kicker") }}</p>
          <h1 class="ui-display text-2xl font-bold tracking-tight text-white sm:text-3xl">{{ t("ownerRatings.title") }}</h1>
          <p class="ui-subtle">{{ t("ownerRatings.description") }}</p>
        </div>
        <div class="flex shrink-0 flex-wrap items-center gap-2">
          <button
            type="button"
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
            :disabled="exporting || !ratings.length"
            :aria-busy="exporting"
            :aria-label="exporting ? t('common.loading') : undefined"
            @click="exportCsv"
          >
            <AppIcon name="download" :class="['h-3.5 w-3.5', exporting ? 'animate-bounce' : '']" aria-hidden="true" />
            {{ exporting ? t("ownerRatings.exporting") : t("ownerRatings.exportCsv") }}
          </button>
          <button
            type="button"
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
            :disabled="loading || updating"
            @click="fetchRatings(true)"
          >
            <AppIcon name="refresh" class="h-3.5 w-3.5" :class="updating ? 'animate-spin' : ''" aria-hidden="true" />
            {{ t("ownerRatings.refresh") }}
          </button>
        </div>
      </div>

      <!-- Summary stats skeleton -->
      <div v-if="loading && !summary" class="animate-pulse grid grid-cols-3 gap-px overflow-hidden rounded-xl border border-slate-800 bg-slate-800">
        <div class="flex flex-col items-center gap-2 bg-slate-950/70 px-3 py-4">
          <div class="h-7 w-12 rounded bg-slate-700/50" />
          <div class="h-2.5 w-20 rounded bg-slate-800/50" />
        </div>
        <div class="flex flex-col items-center gap-2 bg-slate-950/70 px-3 py-4">
          <div class="h-7 w-12 rounded bg-slate-700/50" />
          <div class="h-2.5 w-20 rounded bg-slate-800/50" />
        </div>
        <div class="flex flex-col items-center gap-2 bg-slate-950/70 px-3 py-4">
          <div class="h-7 w-12 rounded bg-slate-700/50" />
          <div class="h-2.5 w-20 rounded bg-slate-800/50" />
        </div>
      </div>

      <!-- Summary stats -->
      <div v-if="summary" class="grid grid-cols-3 gap-px overflow-hidden rounded-xl border border-slate-800 bg-slate-800">
        <div class="bg-slate-950/70 px-3 py-4 text-center">
          <p class="text-2xl font-bold leading-none text-white tabular-nums">{{ summary.count }}</p>
          <p class="ui-stat-label mt-1.5">{{ t("ownerRatings.totalRatings") }}</p>
        </div>
        <div class="bg-slate-950/70 px-3 py-4 text-center">
          <p class="text-2xl font-bold leading-none text-amber-400 tabular-nums">
            {{ summary.average !== null ? summary.average.toFixed(1) : "—" }}
          </p>
          <p class="ui-stat-label mt-1.5">{{ t("ownerRatings.averageScore") }}</p>
        </div>
        <div class="bg-slate-950/70 px-3 py-4 text-center">
          <p class="text-2xl font-bold leading-none text-white tabular-nums">{{ summary.comments }}</p>
          <p class="ui-stat-label mt-1.5">{{ t("ownerRatings.withComments") }}</p>
        </div>
      </div>

      <!-- Score distribution bar -->
      <div v-if="ratings.length" class="space-y-2">
        <div v-for="s in [5, 4, 3, 2, 1]" :key="s" class="flex items-center gap-2.5 text-xs">
          <span class="w-4 shrink-0 text-end font-bold text-amber-400 tabular-nums">{{ s }}</span>
          <div class="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-slate-800/80" role="progressbar" :aria-label="t('ownerRatings.starLabel', { n: s })" :aria-valuenow="scorePercent(s)" aria-valuemin="0" aria-valuemax="100">
            <div
              class="h-full rounded-full bg-amber-400/75 transition-all duration-500"
              :style="{ width: `${scorePercent(s)}%` }"
            />
          </div>
          <span class="w-6 shrink-0 text-end tabular-nums text-slate-500">{{ scoreCounts[s] || 0 }}</span>
        </div>
      </div>

      <!-- Score filter pills -->
      <div v-if="ratings.length" class="ui-scroll-row min-w-0 max-w-full" role="group" :aria-label="t('ownerRatings.filterAll')">
        <button
          v-for="f in scoreFilters"
          :key="f.value"
          type="button"
          class="ui-chip ui-press shrink-0"
          :class="activeScore === f.value ? 'router-link-active' : ''"
          :aria-pressed="activeScore === f.value"
          :aria-label="f.value === 'all' ? f.label : t('ownerRatings.starsLabel', { n: f.value })"
          @click="activeScore = f.value"
        >
          {{ f.label }}<span v-if="f.value !== 'all' && scoreCounts[f.value]" class="ms-1 text-[10px] font-normal tabular-nums opacity-60">({{ scoreCounts[f.value] }})</span>
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
    <div v-else-if="!ratings.length" class="ui-empty-state ui-reveal py-12 text-center">
      <AppIcon name="star" class="mx-auto mb-3 h-10 w-10 text-slate-700" aria-hidden="true" />
      <p class="text-sm font-semibold text-slate-100">{{ t("ownerRatings.emptyTitle") }}</p>
      <p class="mt-1 text-xs text-slate-400">{{ t("ownerRatings.emptyBody") }}</p>
    </div>

    <!-- Ratings list -->
    <div v-else class="space-y-3">
      <article
        v-for="(r, index) in filtered"
        :key="r.id"
        class="ui-panel ui-surface-lift ui-reveal space-y-3 p-4"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        :aria-label="r.customer_name ? r.customer_name + ', ' + r.score + '/5' : r.score + '/5'"
      >
        <!-- Top row: stars + score · date -->
        <div class="flex flex-wrap items-center justify-between gap-2">
          <!-- Stars + score badge -->
          <div class="flex items-center gap-2.5">
            <span class="text-base leading-none tracking-tight text-amber-400" aria-hidden="true">{{ "★".repeat(r.score) }}<span class="text-slate-700">{{ "★".repeat(5 - r.score) }}</span></span>
            <span
              class="ui-status-pill text-xs font-semibold"
              :class="{
                'border-emerald-500/30 bg-emerald-500/15 text-emerald-300': r.score >= 4,
                'border-amber-500/30 bg-amber-500/15 text-amber-300': r.score === 3,
                'border-red-500/30 bg-red-500/15 text-red-300': r.score <= 2,
              }"
            >{{ r.score }}/5</span>
          </div>
          <!-- Date -->
          <time class="text-xs tabular-nums text-slate-500" :datetime="r.created_at">{{ formatDate(r.created_at) }}</time>
        </div>

        <!-- Customer + order info row -->
        <div class="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span v-if="r.customer_name" class="flex min-w-0 items-center gap-1.5 font-medium text-slate-300">
            <AppIcon name="user" class="h-3 w-3 shrink-0 text-slate-500" aria-hidden="true" />
            <span class="truncate">{{ r.customer_name }}</span>
          </span>
          <span v-if="r.customer_name && r.order_number" class="text-slate-700" aria-hidden="true">·</span>
          <RouterLink
            :to="{ name: 'owner-orders', query: { q: r.order_number } }"
            class="rounded font-mono text-slate-400 transition hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/50"
          >#{{ r.order_number }}</RouterLink>
        </div>

        <!-- Comment -->
        <p v-if="r.comment" class="rounded-lg border-s-2 border-slate-600/60 bg-slate-900/50 py-2.5 ps-3.5 pe-3 text-sm italic leading-relaxed text-slate-300">{{ r.comment }}</p>
        <p v-else class="text-xs italic text-slate-600">{{ t("ownerRatings.noComment") }}</p>

        <!-- Owner reply section -->
        <div class="border-t border-slate-800/60 pt-3">
          <!-- Existing reply: show text + edit/delete controls -->
          <template v-if="r.owner_reply && !replyEditing.has(r.id)">
            <div class="flex min-w-0 items-start justify-between gap-2">
              <div class="min-w-0 space-y-1">
                <p class="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-secondary)]/70">{{ t("ownerRatings.replyKicker") }}</p>
                <p class="text-sm leading-relaxed text-slate-300">{{ r.owner_reply }}</p>
                <p v-if="r.owner_reply_at" class="text-[11px] text-slate-500">{{ t("ownerRatings.replyPostedAt", { date: formatDate(r.owner_reply_at) }) }}</p>
              </div>
              <div class="flex shrink-0 items-center gap-1.5">
                <button
                  type="button"
                  class="rounded-lg border border-slate-700/50 px-2.5 py-1 text-[11px] font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/50"
                  @click="startEdit(r)"
                >{{ t("ownerRatings.replyEdit") }}</button>
                <button
                  type="button"
                  class="rounded-lg border border-red-500/25 px-2.5 py-1 text-[11px] font-medium text-red-400/80 transition hover:border-red-500/50 hover:text-red-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500/40 disabled:opacity-40"
                  :disabled="replyDeleting.has(r.id)"
                  @click="deleteReply(r)"
                >{{ replyDeleting.has(r.id) ? t("ownerRatings.replyDeleting") : t("ownerRatings.replyDelete") }}</button>
              </div>
            </div>
          </template>

          <!-- Reply form: composing new or editing existing -->
          <template v-else-if="replyEditing.has(r.id)">
            <div class="space-y-2">
              <p class="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-secondary)]/70">{{ t("ownerRatings.replyKicker") }}</p>
              <textarea
                :ref="el => { if (el) replyTextareaRefs[r.id] = el; }"
                v-model="replyDrafts[r.id]"
                rows="3"
                maxlength="1000"
                :placeholder="t('ownerRatings.replyPlaceholder')"
                class="ui-textarea w-full resize-none text-sm"
              />
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  class="ui-btn-primary inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs disabled:opacity-40"
                  :disabled="replySaving.has(r.id) || !replyDrafts[r.id]?.trim()"
                  @click="saveReply(r)"
                >
                  <svg v-if="replySaving.has(r.id)" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                  {{ replySaving.has(r.id) ? t("ownerRatings.replySaving") : t("ownerRatings.replySave") }}
                </button>
                <button
                  type="button"
                  class="rounded-lg px-2.5 py-1.5 text-xs text-slate-400 transition hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-600"
                  @click="cancelEdit(r)"
                >{{ t("common.cancel") }}</button>
              </div>
            </div>
          </template>

          <!-- No reply yet: collapsed "Add reply" button -->
          <template v-else>
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-slate-500 transition hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/40"
              @click="startEdit(r)"
            >
              <AppIcon name="plus" class="h-3 w-3 shrink-0" aria-hidden="true" />
              {{ t("ownerRatings.replyAddPrompt") }}
            </button>
          </template>
        </div>
      </article>

      <!-- No matches for current filter -->
      <div v-if="!filtered.length && activeScore !== 'all'" class="ui-empty-state py-10 text-center">
        <AppIcon name="star" class="mx-auto mb-3 h-8 w-8 text-slate-700" aria-hidden="true" />
        <p class="text-sm font-semibold text-slate-100">{{ t("ownerRatings.noMatchFilter") }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onActivated, onMounted, reactive, ref } from "vue";
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

// ── Reply state ───────────────────────────────────────────────────────────────
// Sets used instead of maps so Vue reactivity works cleanly with has/add/delete.
const replyEditing = ref(new Set());   // rating IDs currently showing the compose form
const replySaving = ref(new Set());    // rating IDs with in-flight POST
const replyDeleting = ref(new Set());  // rating IDs with in-flight DELETE
const replyDrafts = reactive({});      // ratingId → draft string
const replyTextareaRefs = reactive({}); // ratingId → textarea DOM ref

const startEdit = async (r) => {
  replyDrafts[r.id] = r.owner_reply || "";
  replyEditing.value = new Set([...replyEditing.value, r.id]);
  await nextTick();
  if (replyTextareaRefs[r.id]) replyTextareaRefs[r.id].focus();
};

const cancelEdit = (r) => {
  const next = new Set(replyEditing.value);
  next.delete(r.id);
  replyEditing.value = next;
};

const saveReply = async (r) => {
  const text = (replyDrafts[r.id] || "").trim();
  if (!text) return;
  replySaving.value = new Set([...replySaving.value, r.id]);
  try {
    const res = await api.post(`/owner/ratings/${r.id}/reply/`, { reply: text });
    // Patch the local rating object so the UI updates without a refetch
    const idx = ratings.value.findIndex((x) => x.id === r.id);
    if (idx !== -1) {
      ratings.value[idx] = { ...ratings.value[idx], owner_reply: res.data.owner_reply, owner_reply_at: res.data.owner_reply_at };
    }
    cancelEdit(r);
    toast.show(t("ownerRatings.replySaved"), "success");
  } catch {
    toast.show(t("ownerRatings.replyError"), "error");
  } finally {
    const next = new Set(replySaving.value);
    next.delete(r.id);
    replySaving.value = next;
  }
};

const deleteReply = async (r) => {
  replyDeleting.value = new Set([...replyDeleting.value, r.id]);
  try {
    await api.delete(`/owner/ratings/${r.id}/reply/`);
    const idx = ratings.value.findIndex((x) => x.id === r.id);
    if (idx !== -1) {
      ratings.value[idx] = { ...ratings.value[idx], owner_reply: "", owner_reply_at: null };
    }
    toast.show(t("ownerRatings.replyDeleted"), "success");
  } catch {
    toast.show(t("ownerRatings.replyDeleteError"), "error");
  } finally {
    const next = new Set(replyDeleting.value);
    next.delete(r.id);
    replyDeleting.value = next;
  }
};

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
    : ratings.value.filter((r) => Number(r.score) === Number(activeScore.value))
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
    toast.show(t("ownerRatings.exportSuccess"), "success");
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
