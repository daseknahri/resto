<template>
  <div
    :class="[
      'space-y-4 px-3 py-2 sm:space-y-5 sm:px-4 sm:py-3 sm:pb-8 ui-safe-bottom',
      cart.count ? 'pb-44' : 'pb-24',
    ]"
  >
    <!-- Hero: restaurant identity -->
    <header class="ui-hero-stage ui-reveal overflow-hidden border border-slate-800/80 bg-slate-950/82 p-0">
      <div class="relative min-h-[14rem] overflow-hidden rounded-[1.35rem] bg-slate-950/92 sm:min-h-[16rem]">
        <img
          v-if="heroImage"
          :src="heroImage"
          :alt="`${tenantName} cover`"
          class="absolute inset-0 h-full w-full object-cover"
          loading="eager"
          fetchpriority="high"
          decoding="async"
          @error="handleHeroImageError"
        />
        <div class="absolute inset-0 bg-gradient-to-t from-slate-950/95 via-slate-950/55 to-slate-950/20"></div>
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(20,184,166,0.10),transparent_32%),radial-gradient(circle_at_bottom_left,rgba(245,158,11,0.10),transparent_30%)]"></div>

        <div class="relative flex h-full flex-col justify-end space-y-3 p-4 md:p-6">
          <div class="flex items-end gap-4">
            <img
              v-if="logoImage"
              :src="logoImage"
              :alt="`${tenantName} logo`"
              class="h-16 w-16 shrink-0 rounded-2xl border-2 border-white/20 object-cover shadow-2xl shadow-black/50 sm:h-20 sm:w-20"
              loading="eager"
              decoding="async"
              @error="handleLogoImageError"
            />
            <div class="min-w-0 space-y-1">
              <p class="ui-kicker">{{ t('menu.kicker') }}</p>
              <h1 class="ui-display text-2xl font-semibold tracking-tight text-white sm:text-3xl">{{ tenantName }}</h1>
              <p v-if="tenantDescription" class="line-clamp-1 text-sm text-slate-300">{{ tenantDescription }}</p>
            </div>
          </div>

          <div class="flex flex-wrap gap-2">
            <span class="ui-chip-strong">{{ statusLabel }}</span>
            <span v-if="locationLine" class="ui-chip">
              <AppIcon name="info" class="h-3.5 w-3.5" />
              {{ locationLine }}
            </span>
          </div>
        </div>
      </div>
    </header>

    <!-- Filter bar: search + section/category pills -->
    <div class="ui-panel space-y-3 p-3 sm:p-4">
      <div class="relative">
        <input
          v-model.trim="search"
          class="ui-input pr-10"
          :placeholder="t('menu.searchPlaceholder')"
        />
        <button
          v-if="search"
          class="absolute right-2 top-1/2 -translate-y-1/2 rounded-full border border-slate-700/80 p-1 text-slate-300 hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)]"
          @click="clearSearch"
        >
          <span class="sr-only">{{ t('common.clear') }}</span>
          <AppIcon name="close" class="h-3.5 w-3.5" />
        </button>
      </div>

      <div v-if="superCategories.length" class="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <button
          v-for="group in superCategories"
          :key="group.slug"
          class="ui-pill-nav shrink-0 whitespace-nowrap px-3 py-1.5 text-xs"
          :data-active="selectedSuperCategorySlug === group.slug"
          @click="selectedSuperCategorySlug = group.slug"
        >
          {{ group.name }}
        </button>
      </div>

      <div v-if="visibleCategories.length" class="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <button
          v-for="cat in visibleCategories"
          :key="`cat-${cat.slug}`"
          class="ui-pill-nav shrink-0 whitespace-nowrap px-3 py-1.5 text-xs"
          :data-active="selectedCategorySlug === cat.slug"
          @click="selectCategory(cat.slug)"
        >
          {{ cat.name }}
        </button>
      </div>
    </div>

    <!-- Category heading -->
    <div v-if="selectedCategory" class="px-1 space-y-0.5">
      <p class="ui-kicker">{{ selectedSuperCategory?.name }}</p>
      <h2 class="ui-display text-xl font-semibold text-white sm:text-2xl">{{ selectedCategory.name }}</h2>
      <p v-if="selectedCategory.description" class="text-sm text-slate-400">{{ selectedCategory.description }}</p>
    </div>

    <!-- Dish grid -->
    <div v-if="selectedCategorySlug && menu.loading && !selectedDishes.length" class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <div v-for="n in 6" :key="n" class="ui-skeleton h-80 rounded-[1.8rem]"></div>
    </div>

    <div v-else-if="filteredDishes.length" class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <article
        v-for="dish in filteredDishes"
        :key="dish.slug"
        class="group overflow-hidden rounded-[1.8rem] border border-slate-800/80 bg-slate-950/82 shadow-[0_20px_50px_rgba(2,6,23,0.36)] transition-all duration-300 hover:border-slate-700/80 hover:shadow-[0_28px_64px_rgba(2,6,23,0.48)]"
      >
        <!-- Image -->
        <button type="button" class="block w-full text-left" @click="goToDish(dish)">
          <div class="relative aspect-[4/3] overflow-hidden bg-slate-900">
            <img
              v-if="dish.image_url"
              :src="dish.image_url"
              :alt="dish.name"
              class="h-full w-full object-cover transition duration-500 group-hover:scale-[1.04]"
              loading="lazy"
              decoding="async"
              @error="handleDishImageError"
            />
            <div v-else class="absolute inset-0 flex items-center justify-center bg-slate-900">
              <AppIcon name="menu" class="h-12 w-12 text-slate-700" />
            </div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/20 to-transparent"></div>
            <!-- Price badge -->
            <div class="absolute right-3 top-3">
              <span class="rounded-full bg-[var(--color-secondary)] px-3 py-1 text-xs font-bold text-slate-950 shadow-lg">
                {{ formatCurrency(dish.price, dish.currency || cartCurrency) }}
              </span>
            </div>
            <!-- Category chip -->
            <div class="absolute inset-x-0 bottom-0 px-3 pb-3">
              <span class="ui-chip-strong text-[11px]">{{ selectedCategory?.name }}</span>
            </div>
          </div>
        </button>

        <!-- Info + actions -->
        <div class="space-y-3 p-4">
          <div class="space-y-1">
            <h3 class="text-base font-semibold leading-snug text-white">{{ dish.name }}</h3>
            <p class="line-clamp-2 text-sm text-slate-400">{{ dish.description || '' }}</p>
          </div>
          <div v-if="dish.tags?.length" class="flex flex-wrap gap-1">
            <span v-for="tag in dish.tags" :key="tag" class="rounded-full border border-slate-700/60 px-2 py-0.5 text-[10px] text-slate-400">{{ t(`dishPage.tag_${tag}`) }}</span>
          </div>
          <div v-if="dish.options?.length || dish.option_groups?.length" class="flex flex-wrap gap-1.5">
            <span v-if="dish.options?.length" class="ui-data-strip text-[11px]">{{ t('dishPage.optionsCount', { count: dish.options.length }) }}</span>
            <span v-if="dish.option_groups?.length" class="ui-data-strip text-[11px]">{{ dish.option_groups.length }} {{ t('stepDishes.optionGroupsTitle') }}</span>
          </div>
          <div class="flex gap-2">
            <button
              v-if="!isBrowseOnly && isRestaurantOpen"
              class="ui-btn-primary flex-1 justify-center gap-2 py-2 text-sm"
              @click.stop="quickAdd(dish)"
            >
              <AppIcon name="plus" class="h-4 w-4" />
              {{ t('dishPage.add') }}
            </button>
            <button
              class="ui-btn-outline flex-1 justify-center gap-2 py-2 text-sm"
              :class="isBrowseOnly || !isRestaurantOpen ? 'flex-1' : ''"
              @click.stop="goToDish(dish)"
            >
              <AppIcon name="eye" class="h-3.5 w-3.5" />
              {{ t('category.viewDish') }}
            </button>
          </div>
        </div>
      </article>
    </div>

    <div v-else-if="!menu.loading" class="ui-empty-state space-y-4 text-slate-300">
      <div class="space-y-2 text-center">
        <div class="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl border border-slate-700/80 bg-slate-950/70 text-slate-200">
          <AppIcon name="search" class="h-5 w-5" />
        </div>
        <p class="ui-kicker">{{ selectedSuperCategory?.name || t('menu.kicker') }}</p>
        <p class="text-xl font-semibold text-slate-100">{{ t('menu.noMatchTitle') }}</p>
        <p class="text-sm text-slate-400">{{ t('menu.noMatchText') }}</p>
      </div>
      <button class="ui-btn-outline justify-center" @click="clearSearch">
        <AppIcon name="close" class="h-3.5 w-3.5" />
        {{ t('common.clear') }}
      </button>
    </div>

    <p v-if="menu.error" class="text-sm text-red-400">{{ menu.error }}</p>

    <!-- Sticky cart bar (mobile) -->
    <RouterLink
      v-if="cart.count"
      :to="{ name: 'cart' }"
      class="fixed bottom-[5.15rem] left-2.5 right-2.5 z-20 flex items-center justify-between rounded-2xl border border-[var(--color-secondary)]/30 bg-slate-950/95 px-4 py-3 shadow-2xl shadow-black/50 backdrop-blur sm:hidden"
    >
      <div>
        <p class="text-xs text-slate-400">{{ t('common.cart') }}</p>
        <p class="font-semibold text-white">{{ itemCountLabel(cart.count) }}</p>
      </div>
      <div class="flex items-center gap-2">
        <p class="text-base font-bold text-[var(--color-secondary)]">
          {{ formatCurrency(cart.total, cartCurrency) }}
        </p>
        <AppIcon name="cart" class="h-4 w-4 text-[var(--color-secondary)]" />
      </div>
    </RouterLink>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { withImageFallback } from '../lib/images';
import { trackEvent } from '../lib/analytics';
import { getTodayClosingTime, getNextOpenInfo, isCurrentlyOpenBySchedule } from '../lib/businessHours';
import { useCartStore } from '../stores/cart';
import { useMenuStore } from '../stores/menu';
import { useTenantStore } from '../stores/tenant';
import { useToastStore } from '../stores/toast';

const menu = useMenuStore();
const tenant = useTenantStore();
const cart = useCartStore();
const toast = useToastStore();
const router = useRouter();
const { currentLocale, formatCurrency, itemCountLabel, t } = useI18n();

const search = ref('');
const selectedSuperCategorySlug = ref('');
const selectedCategorySlug = ref('');
const meta = computed(() => tenant.resolvedMeta || null);
const profile = computed(() => meta.value?.profile || null);
const menuCategories = computed(() => (Array.isArray(menu.categories) ? menu.categories : []));
const storeSuperCategories = computed(() => (Array.isArray(menu.superCategories) ? menu.superCategories : []));
const isBrowseOnly = computed(() => tenant.isBrowseOnlyPlan === true);
const isRestaurantOpen = computed(() => profile.value?.is_open !== false);

const tenantName = computed(() => meta.value?.name || t('customerLayout.fallbackTenantName'));
const tenantDescription = computed(() => String(profile.value?.description || profile.value?.tagline || '').trim() || t('customerLeadPage.fallbackDescription'));
const heroImage = computed(() => String(profile.value?.hero_url || '').trim());
const logoImage = computed(() => String(profile.value?.logo_url || '').trim());
const locationLine = computed(() => String(profile.value?.address || meta.value?.name || '').trim());
const statusLabel = computed(() => {
  if (profile.value?.is_open === false) return t('customerLeadPage.closedNow');
  const schedule = profile.value?.business_hours_schedule;
  if (schedule && Object.keys(schedule).length) {
    const openBySchedule = isCurrentlyOpenBySchedule(schedule);
    if (openBySchedule === true) {
      const closeTime = getTodayClosingTime(schedule);
      return closeTime ? t('menu.opensUntil', { time: closeTime }) : t('customerLeadPage.openNow');
    }
    if (openBySchedule === false) {
      const next = getNextOpenInfo(schedule, currentLocale.value);
      if (next) {
        const dayPart = next.isTomorrow ? t('menu.tomorrow') : next.dayLabel;
        return t('menu.opensAt', { day: dayPart, time: next.openTime });
      }
    }
  }
  return t('customerLeadPage.openNow');
});
const cartCurrency = computed(() => {
  const firstItemCurrency = cart.items.find((item) => item.currency)?.currency;
  return firstItemCurrency || meta.value?.plan?.currency || 'USD';
});
const superCategories = computed(() => {
  if (storeSuperCategories.value.length) return [...storeSuperCategories.value].sort((a, b) => (a.position || 0) - (b.position || 0));
  const seen = new Map();
  menuCategories.value.forEach((category) => {
    const slug = String(category.super_category_slug || 'menu').trim();
    if (!slug || seen.has(slug)) return;
    seen.set(slug, {
      id: category.super_category || slug,
      slug,
      name: category.super_category_name || 'Menu',
      position: 0,
    });
  });
  return [...seen.values()];
});
const visibleCategories = computed(() => {
  const activeSlug = String(selectedSuperCategorySlug.value || '').trim();
  return [...menuCategories.value]
    .filter((category) => !activeSlug || String(category.super_category_slug || '').trim() === activeSlug)
    .sort((a, b) => (a.position || 0) - (b.position || 0));
});
const selectedSuperCategory = computed(() => superCategories.value.find((group) => group.slug === selectedSuperCategorySlug.value) || null);
const selectedCategory = computed(() => visibleCategories.value.find((category) => category.slug === selectedCategorySlug.value) || null);
const selectedDishes = computed(() => menu.dishes[selectedCategorySlug.value] || []);
const filteredDishes = computed(() => {
  const query = search.value.trim().toLowerCase();
  if (!query) return selectedDishes.value;
  return selectedDishes.value.filter((dish) => {
    if ([dish.name, dish.description, dish.slug].filter(Boolean).some((value) => String(value).toLowerCase().includes(query))) return true;
    return (dish.tags || []).some((tag) => tag.replace('_', ' ').includes(query));
  });
});

const syncSelection = () => {
  if (!superCategories.value.length) {
    selectedSuperCategorySlug.value = '';
    selectedCategorySlug.value = '';
    return;
  }
  if (!superCategories.value.some((group) => group.slug === selectedSuperCategorySlug.value)) {
    selectedSuperCategorySlug.value = String(superCategories.value[0]?.slug || '');
  }
  if (!visibleCategories.value.length) {
    selectedCategorySlug.value = '';
    return;
  }
  if (!visibleCategories.value.some((category) => category.slug === selectedCategorySlug.value)) {
    selectedCategorySlug.value = String(visibleCategories.value[0]?.slug || '');
  }
};

const selectCategory = (slug) => {
  selectedCategorySlug.value = slug;
};
const goToDish = (dish) => {
  if (!selectedCategorySlug.value || !dish?.slug) return;
  router.push({ name: 'dish', params: { category: selectedCategorySlug.value, dish: dish.slug } });
};
const quickAdd = (dish) => {
  if (!dish) return;
  const hasRequiredGroups = dish.option_groups?.some((g) => g.min_select > 0) || false;
  const requiredOptions = Array.isArray(dish.options) ? dish.options.filter((o) => o.is_required) : [];
  if (hasRequiredGroups || requiredOptions.length) {
    goToDish(dish);
    return;
  }
  cart.add({
    key: `${dish.slug}::`,
    slug: dish.slug,
    name: dish.name,
    price: Number(dish.price || 0),
    currency: dish.currency || cartCurrency.value,
    qty: 1,
    note: '',
    option_ids: [],
    option_labels: [],
  });
  toast.show(t('dishPage.addedToCart'), 'success');
};
const clearSearch = () => {
  search.value = '';
};

const handleHeroImageError = (event) => withImageFallback(event);
const handleLogoImageError = (event) => withImageFallback(event);
const handleDishImageError = (event) => withImageFallback(event);

watch([superCategories, menuCategories], syncSelection, { immediate: true });
watch(
  () => selectedCategorySlug.value,
  async (slug) => {
    if (!slug) return;
    await menu.fetchDishesByCategory(slug);
  },
  { immediate: true }
);

onMounted(async () => {
  if (!menuCategories.value.length) await menu.fetchCategories();
  trackEvent('menu_view', { source: 'customer_menu_browse' });
});

watch(
  () => currentLocale.value,
  () => {
    menu.fetchCategories(true);
  }
);
</script>
