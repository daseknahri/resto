<template>
  <!-- Readiness skeleton while loading -->
  <div v-if="loading" role="status" class="ui-section-band animate-pulse space-y-3 p-3 sm:space-y-4 sm:p-4" aria-busy="true" :aria-label="t('ownerHome.launchProgress')">
    <div class="flex items-center justify-between gap-3">
      <div class="h-3.5 w-28 rounded bg-slate-700/60" />
      <div class="h-3.5 w-10 rounded bg-slate-700/60" />
    </div>
    <div class="h-2 rounded-full bg-slate-800" />
    <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
      <div v-for="i in 5" :key="i" class="ui-readiness-item flex items-center justify-between gap-3">
        <div class="h-3 flex-1 rounded bg-slate-700/50" />
        <div class="h-5 w-14 shrink-0 rounded-full bg-slate-700/40" />
      </div>
    </div>
  </div>

  <!-- Setup progress: hidden once complete (100%) so an established restaurant gets a
       cleaner dashboard. The component stays mounted to keep feeding dish data upward. -->
  <!-- TODO: requires logic change — readinessScore === 100 is unreachable here (outer condition is < 100);
       the completion message (line ~49) and emerald colour state are permanently dead.
       Fix: change outer condition to v-else-if="readinessScore <= 100" or restructure. -->
  <article
    v-else-if="readinessScore < 100"
    class="ui-section-band ui-reveal space-y-3 p-3 sm:space-y-4 sm:p-4"
    aria-labelledby="readiness-heading"
    aria-live="polite"
  >
    <div class="flex items-center justify-between gap-3">
      <div class="min-w-0">
        <p class="ui-kicker">{{ t("ownerHome.launchChecklist") }}</p>
        <h2 id="readiness-heading" class="mt-0.5 text-base font-semibold text-white">{{ t("ownerHome.launchProgress") }}</h2>
      </div>
      <span
        class="tabular-nums text-sm font-semibold"
        :class="readinessScore === 100 ? 'text-emerald-400' : 'text-[var(--color-secondary)]'"
        aria-hidden="true"
      >
        {{ readinessScore }}%
      </span>
    </div>

    <div
      class="h-2 overflow-hidden rounded-full bg-slate-800"
      role="progressbar"
      :aria-valuenow="readinessScore"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-label="t('ownerHome.launchProgress')"
    >
      <div
        class="h-full rounded-full transition-all duration-[var(--motion-slow)]"
        :class="readinessScore === 100 ? 'bg-emerald-500' : 'bg-[var(--color-secondary)]'"
        :style="{ width: `${readinessScore}%` }"
      />
    </div>

    <p v-if="readinessScore === 100" class="text-xs text-emerald-400/80">
      {{ t("ownerHome.readinessDone") }}
    </p>

    <ul role="list" class="grid list-none gap-2 p-0 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
      <li
        v-for="(item, index) in readinessItems"
        :key="item.label"
        class="ui-readiness-item ui-reveal flex items-start justify-between gap-3"
        :data-complete="item.ready"
        :data-warning="!item.ready"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
      >
        <div class="flex min-w-0 items-start gap-3">
          <span class="ui-readiness-dot mt-1 shrink-0" aria-hidden="true" />
          <div class="min-w-0">
            <p class="text-[13px] font-medium text-slate-100 sm:text-sm">{{ item.label }}</p>
            <RouterLink
              v-if="item.to"
              :to="item.to"
              :aria-label="`${item.actionLabel} — ${item.label}`"
              class="mt-1.5 inline-flex text-[11px] text-brand-secondary hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)] sm:text-xs"
            >
              {{ item.actionLabel }}
            </RouterLink>
          </div>
        </div>
        <span
          class="ui-status-pill shrink-0"
          :class="item.ready ? 'border-emerald-500/30 bg-emerald-500/15 text-emerald-300' : 'border-amber-500/30 bg-amber-500/15 text-amber-300'"
        >
          {{ item.ready ? t("ownerHome.ready") : t("ownerHome.missing") }}
        </span>
      </li>
    </ul>
  </article>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { useTenantStore } from "../stores/tenant";

const { t } = useI18n();
const tenant = useTenantStore();

// ── Own loading state — independent of the parent page ───────────────────────
const loading = ref(true);
const categoriesCount = ref(0);
const dishesCount = ref(0);

// Expose counts so the parent can pass them to the dish availability panel
// without that panel having to fetch again.
const emit = defineEmits(["loaded"]);

// ── Readiness derived from local data + tenant profile ────────────────────────
const profile = computed(() => tenant.meta?.profile || {});
const published = computed(() => profile.value?.is_menu_published === true);

const hasContact = computed(() =>
  Boolean((profile.value?.phone || "").trim() || (profile.value?.whatsapp || "").trim())
);
const hasTheme = computed(() =>
  Boolean(
    (profile.value?.logo_url || "").trim() ||
    (profile.value?.hero_url || "").trim() ||
    profile.value?.primary_color ||
    profile.value?.secondary_color
  )
);

const readinessScore = computed(() => {
  const checks = [
    hasContact.value,
    hasTheme.value,
    categoriesCount.value > 0,
    dishesCount.value > 0,
    published.value,
  ];
  return Math.round((checks.filter(Boolean).length / checks.length) * 100);
});

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

// ── Fetch categories + dishes counts independently ────────────────────────────
const load = async () => {
  loading.value = true;
  try {
    // Fetch enough dish fields to compute sold-out count — needed by the
    // alerts strip in the parent without triggering a second dishes fetch.
    const [cats, dishes] = await Promise.all([
      api.get("/categories/", { timeout: 5000 }),
      api.get("/dishes/", { timeout: 5000 }),
    ]);
    const catList = Array.isArray(cats.data) ? cats.data : [];
    const dishList = Array.isArray(dishes.data) ? dishes.data : [];
    categoriesCount.value = catList.length;
    dishesCount.value = dishList.length;
    const soldOutCount = dishList.filter((d) => d.is_published && !d.is_available).length;

    // Build slug → name maps so siblings can resolve analytics slugs to labels
    const categoryNameBySlug = Object.fromEntries(
      catList.map((c) => [c.slug, c.name]).filter(([s]) => s)
    );
    const dishNameBySlug = Object.fromEntries(
      dishList.map((d) => [d.slug, d.name]).filter(([s]) => s)
    );

    emit("loaded", {
      categoriesCount: categoriesCount.value,
      dishesCount: dishesCount.value,
      soldOutCount,
      categoryNameBySlug,
      dishNameBySlug,
      // Pass the raw dish list so the dish panel can use it as initial data
      // without triggering a second /dishes/ fetch when the user opens the panel.
      dishesData: dishList,
    });
  } catch {
    // Readiness degrades gracefully — missing counts just show "missing"
    emit("loaded", { categoriesCount: 0, dishesCount: 0, soldOutCount: 0, categoryNameBySlug: {}, dishNameBySlug: {}, dishesData: [] });
  } finally {
    loading.value = false;
  }
};

onMounted(load);

// Expose load() so the parent's manual-refresh button can re-fetch readiness
// data (counts, sold-out count, name maps) along with everything else.
defineExpose({ load });
</script>
