<template>
  <!-- Readiness skeleton while loading -->
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

  <article v-else class="ui-section-band space-y-3 p-3 sm:space-y-4 sm:p-4">
    <div class="flex items-center justify-between gap-3">
      <p class="text-sm font-medium text-slate-200">{{ t("ownerHome.launchProgress") }}</p>
      <span
        class="text-sm font-semibold"
        :class="readinessScore === 100 ? 'text-emerald-400' : 'text-[var(--color-secondary)]'"
      >
        {{ readinessScore === 100 ? "✓ " : "" }}{{ readinessScore }}%
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
        class="h-full rounded-full transition-all duration-300"
        :class="readinessScore === 100 ? 'bg-emerald-500' : 'bg-[var(--color-secondary)]'"
        :style="{ width: `${readinessScore}%` }"
      />
    </div>

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
          <span class="ui-readiness-dot mt-1 shrink-0" />
          <div class="min-w-0">
            <p class="text-[13px] font-medium text-slate-100 sm:text-sm">{{ item.label }}</p>
            <RouterLink
              v-if="item.to"
              :to="item.to"
              class="mt-1.5 inline-flex text-[11px] text-brand-secondary hover:underline sm:text-xs"
            >
              {{ item.actionLabel }}
            </RouterLink>
          </div>
        </div>
        <span
          class="shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold"
          :class="item.ready ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'"
        >
          {{ item.ready ? t("ownerHome.ready") : t("ownerHome.missing") }}
        </span>
      </article>
    </div>
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
