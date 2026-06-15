<template>
  <div class="ui-safe-bottom px-3 py-3 pb-24 sm:px-4 sm:py-4">
    <!-- Restaurant hero (same as Menu.vue) -->
    <header class="ui-hero-stage ui-reveal mb-4 overflow-hidden border border-slate-800/80 bg-slate-950/82 p-0">
      <div class="relative min-h-[13rem] overflow-hidden rounded-[1.35rem] bg-slate-950/92 sm:min-h-[15rem]">
        <img
          v-if="heroImage"
          :src="heroImage"
          :alt="t('menuSelect.heroCoverAlt', { name: tenantName })"
          class="absolute inset-0 h-full w-full object-cover"
          loading="eager"
          fetchpriority="high"
          decoding="async"
        />
        <div class="absolute inset-0 bg-gradient-to-t from-slate-950/96 via-slate-950/55 to-slate-950/20" />
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(20,184,166,0.10),transparent_32%),radial-gradient(circle_at_bottom_left,rgba(245,158,11,0.10),transparent_30%)]" />

        <div class="relative flex h-full flex-col justify-end space-y-3 p-4 md:p-6">
          <div class="flex items-end gap-4">
            <img
              v-if="logoImage"
              :src="logoImage"
              :alt="t('menuSelect.logoAlt', { name: tenantName })"
              class="h-16 w-16 shrink-0 rounded-2xl border-2 border-white/20 object-cover shadow-2xl shadow-black/50 sm:h-20 sm:w-20"
              loading="eager"
              decoding="async"
              @error="$event.target.style.display='none'"
            />
            <div class="min-w-0 space-y-1">
              <p class="ui-kicker">{{ t('menu.kicker') }}</p>
              <h1 class="ui-display text-2xl font-semibold tracking-tight text-white sm:text-3xl">{{ tenantName }}</h1>
              <p v-if="tenantDescription" class="line-clamp-1 ui-subtle" :title="tenantDescription">{{ tenantDescription }}</p>
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <span
              class="ui-status-pill"
              :class="isRestaurantOpen
                ? 'border-emerald-500/40 bg-emerald-500/12 text-emerald-300'
                : 'border-red-500/35 bg-red-500/10 text-red-300'"
            >
              <span
                class="ui-live-dot"
                :class="isRestaurantOpen ? 'bg-emerald-400' : 'bg-red-500'"
                aria-hidden="true"
              />
              {{ statusLabel }}
            </span>
          </div>
        </div>
      </div>
    </header>

    <!-- Loading state -->
    <div
      v-if="menu.loading && !publishedMenus.length"
      class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
      role="status"
      :aria-label="t('menuSelect.kicker')"
      aria-busy="true"
    >
      <div v-for="n in 3" :key="n" class="ui-skeleton rounded-[1.8rem]" style="height: 17rem;" />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!menu.loading && !menu.error && !publishedMenus.length"
      class="ui-empty-state mt-3 p-8 text-center"
      role="status"
    >
      <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-slate-700/60 bg-slate-900/60">
        <AppIcon name="menu" class="h-7 w-7 text-slate-400" aria-hidden="true" />
      </div>
      <p class="text-base font-semibold tracking-tight text-slate-100">{{ t('menuSelect.emptyTitle') }}</p>
      <p class="mt-1.5 text-sm text-slate-400">{{ t('menuSelect.emptyBody') }}</p>
    </div>

    <!-- Menu cards -->
    <div v-else-if="publishedMenus.length" class="space-y-4">
      <div class="space-y-1 px-1 pt-1">
        <p class="ui-section-kicker">{{ t('menuSelect.kicker') }}</p>
        <h2 class="ui-display text-2xl font-semibold tracking-tight text-white sm:text-3xl">{{ t('menuSelect.title') }}</h2>
        <p class="ui-subtle mt-0.5">{{ t('menuSelect.subtitle', { count: publishedMenus.length }) }}</p>
      </div>

      <ul class="grid list-none gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <li v-for="(sc, i) in publishedMenus" :key="sc.slug">
        <RouterLink
          :to="{ name: 'menu-browse', params: { menuSlug: sc.slug } }"
          class="ui-surface-lift ui-reveal group relative block overflow-hidden rounded-[1.8rem] border border-slate-800/80 bg-slate-950/82 shadow-[0_16px_42px_rgba(2,6,23,0.36)] hover:border-[var(--color-secondary)]/40 hover:shadow-[0_20px_56px_rgba(2,6,23,0.52)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-secondary)]"
          :style="{ '--ui-delay': `${Math.min(i, 6) * 50}ms` }"
          :aria-label="sc.is_temporarily_disabled
            ? `${sc.name} — ${t('menuSelect.unavailable')}`
            : t('menuSelect.browseLinkLabel', { name: sc.name }) + ', ' + t('menuSelect.categoryCount', { count: sc.category_count || menuCategoryCount(sc.slug) })"
        >
          <!-- Card image area -->
          <div class="relative h-44 w-full overflow-hidden bg-slate-900 sm:h-48">
            <img
              v-if="menuCoverImage(sc)"
              :src="menuCoverImage(sc)"
              alt=""
              class="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
              loading="lazy"
              decoding="async"
              @error="$event.target.style.display='none'"
            />
            <!-- Gradient placeholder when no image -->
            <div
              v-else
              class="absolute inset-0 flex items-center justify-center overflow-hidden"
              aria-hidden="true"
              :style="`background: linear-gradient(135deg, rgba(245,158,11,0.16) 0%, rgba(15,118,110,0.13) 50%, rgba(6,11,18,0.80) 100%)`"
            >
              <div class="pointer-events-none absolute inset-0" style="background-image: radial-gradient(rgba(245,158,11,0.20) 1px, transparent 1px); background-size: 14px 14px;" />
              <span class="relative select-none text-5xl font-bold tracking-tight text-[var(--color-secondary)]/30">
                {{ sc.name.charAt(0).toUpperCase() }}
              </span>
            </div>

            <!-- Overlay gradient -->
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/30 to-transparent" />

            <!-- Top-end: category count chip (RTL-safe) -->
            <div class="absolute end-3 top-3">
              <span class="rounded-full border border-slate-700/55 bg-slate-950/80 px-3 py-1 text-[11px] font-semibold tabular-nums text-slate-200 backdrop-blur-md">
                {{ t('menuSelect.categoryCount', { count: sc.category_count || menuCategoryCount(sc.slug) }) }}
              </span>
            </div>

            <!-- Disabled badge (RTL-safe) -->
            <div v-if="sc.is_temporarily_disabled" class="absolute start-3 top-3">
              <span class="rounded-full border border-amber-500/40 bg-amber-500/20 px-2.5 py-0.5 text-[11px] font-semibold text-amber-200 backdrop-blur-sm">
                {{ sc.disabled_note || t('menuSelect.temporarilyUnavailable') }}
              </span>
            </div>
          </div>

          <!-- Card content -->
          <div class="space-y-3 p-4 pb-4">
            <div class="space-y-1">
              <h3 class="text-[0.95rem] font-bold leading-snug tracking-tight text-white transition-colors duration-200 group-hover:text-[var(--color-secondary)]">
                {{ sc.name }}
              </h3>
              <p v-if="sc.description" class="line-clamp-2 text-[13px] leading-relaxed text-slate-400" :title="sc.description">{{ sc.description }}</p>
            </div>

            <!-- CTA row -->
            <div class="flex items-center justify-between gap-2 pt-0.5">
              <span class="min-w-0 truncate text-[12px] tabular-nums text-slate-500">
                {{ t('menuSelect.dishCount', { count: menuDishCount(sc.slug) }) }}
              </span>
              <span
                class="inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-semibold transition-all duration-200"
                :class="sc.is_temporarily_disabled
                  ? 'border-slate-700/60 bg-slate-800/60 text-slate-500'
                  : 'border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)] group-hover:border-[var(--color-secondary)]/70 group-hover:bg-[var(--color-secondary)]/20'"
              >
                <AppIcon name="menu" class="h-3.5 w-3.5" aria-hidden="true" />
                {{ sc.is_temporarily_disabled ? t('menuSelect.unavailable') : t('menuSelect.browse') }}
              </span>
            </div>
          </div>

          <!-- Bottom accent line on hover -->
          <div class="pointer-events-none absolute inset-x-0 bottom-0 h-[2px] origin-center scale-x-0 transition-transform duration-300 group-hover:scale-x-100" style="background: linear-gradient(90deg, transparent, rgba(245,158,11,0.6), transparent)" aria-hidden="true" />
        </RouterLink>
        </li>
      </ul>
    </div>

    <!-- Error -->
    <div v-if="menu.error" class="mt-3 flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
      <p class="flex-1 text-sm text-red-300">{{ menu.error }}</p>
      <button class="ui-press ui-touch-target shrink-0 text-xs text-slate-400 underline hover:text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400" @click="menu.fetchCategories(true)">{{ t('common.retry') }}</button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { getTodayClosingTime, isCurrentlyOpenBySchedule, isRestaurantOpenNow } from '../lib/businessHours';
import { useMenuStore } from '../stores/menu';
import { useTenantStore } from '../stores/tenant';

const menu = useMenuStore();
const tenant = useTenantStore();
const router = useRouter();
const { t } = useI18n();

// ── Tenant data ──────────────────────────────────────────────────────────────
const meta = computed(() => tenant.resolvedMeta || null);
const profile = computed(() => meta.value?.profile || null);
const tenantName = computed(() => meta.value?.name || t('customerLayout.fallbackTenantName'));
const tenantDescription = computed(() => String(profile.value?.description || profile.value?.tagline || '').trim());
const heroImage = computed(() => String(profile.value?.hero_url || '').trim());
const logoImage = computed(() => String(profile.value?.logo_url || '').trim());

// Server-authoritative open/closed verdict (tenant-local, temp-disable + closure
// aware), shared with Menu.vue and the rest of the storefront via lib/businessHours.
const isRestaurantOpen = computed(() => isRestaurantOpenNow(profile.value));

const statusLabel = computed(() => {
  // Keep the badge TEXT in lock-step with the verdict above.
  if (!isRestaurantOpen.value) return t('customerLeadPage.closedNow');
  // Verdict is OPEN; enrich with the closing time when the browser-clock schedule
  // also reads open (avoid contradicting the authoritative verdict when they
  // disagree across timezones).
  const schedule = profile.value?.business_hours_schedule;
  if (schedule && Object.keys(schedule).length) {
    if (isCurrentlyOpenBySchedule(schedule) === true) {
      const closeTime = getTodayClosingTime(schedule);
      return closeTime ? t('menu.opensUntil', { time: closeTime }) : t('customerLeadPage.openNow');
    }
  }
  return t('customerLeadPage.openNow');
});

// ── Menu data ────────────────────────────────────────────────────────────────
const menuCategories = computed(() => Array.isArray(menu.categories) ? menu.categories : []);
const storeSuperCategories = computed(() => Array.isArray(menu.superCategories) ? menu.superCategories : []);

const publishedMenus = computed(() =>
  [...storeSuperCategories.value]
    .filter((sc) => sc.is_published !== false)
    .sort((a, b) => (a.position || 0) - (b.position || 0))
);

/** Cover image: sc.image_url first, then first category image in that menu */
const menuCoverImage = (sc) => {
  if (sc.image_url) return sc.image_url;
  const cat = menuCategories.value.find(
    (c) => String(c.super_category_slug || '') === sc.slug && c.image_url
  );
  return cat?.image_url || '';
};

/** Number of categories in this super-category */
const menuCategoryCount = (slug) =>
  menuCategories.value.filter((c) => String(c.super_category_slug || '') === slug).length;

/** Rough dish count across all categories in this super-category */
const menuDishCount = (slug) => {
  const slugs = menuCategories.value
    .filter((c) => String(c.super_category_slug || '') === slug)
    .map((c) => c.slug);
  return slugs.reduce((sum, s) => sum + (menu.dishes[s]?.length || 0), 0);
};

// ── Auto-redirect when there is only one published menu ──────────────────────
const maybeAutoRedirect = () => {
  // Only redirect when data is loaded and there's exactly one published menu
  if (menu.loading) return;
  if (publishedMenus.value.length === 1) {
    router.replace({ name: 'menu-browse', params: { menuSlug: publishedMenus.value[0].slug } });
  }
};

watch(
  () => [menu.loading, publishedMenus.value.length],
  () => maybeAutoRedirect(),
);

onMounted(async () => {
  await menu.fetchCategories();
  maybeAutoRedirect();
});
</script>
