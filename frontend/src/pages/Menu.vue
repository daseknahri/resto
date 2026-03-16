<template>
  <div
    :class="[
      'space-y-4 px-3 py-2 sm:space-y-5 sm:px-4 sm:py-3 sm:pb-8 ui-safe-bottom',
      cart.count ? 'pb-44' : 'pb-24',
    ]"
  >
    <header class="ui-hero-stage ui-reveal overflow-hidden border border-slate-800/80 bg-slate-950/82 p-0">
      <div class="relative min-h-[16rem] overflow-hidden rounded-[1.35rem] bg-slate-950/92 sm:min-h-[18rem]">
        <img
          v-if="heroImage"
          :src="heroImage"
          :alt="`${tenantName} cover`"
          class="absolute inset-0 h-full w-full object-cover"
          loading="eager"
          fetchpriority="high"
          decoding="async"
        />
        <div class="absolute inset-0 bg-slate-950/84"></div>
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(20,184,166,0.12),transparent_32%),radial-gradient(circle_at_bottom_left,rgba(245,158,11,0.12),transparent_30%)]"></div>

        <div class="relative space-y-4 p-3 md:p-5">
          <div class="flex items-start justify-between gap-3">
            <div class="flex min-w-0 items-start gap-3">
              <img
                v-if="logoImage"
                :src="logoImage"
                :alt="`${tenantName} logo`"
                class="h-14 w-14 rounded-2xl border border-slate-700/70 object-cover shadow-xl shadow-black/35"
                loading="eager"
                decoding="async"
              />
              <div class="min-w-0 space-y-1">
                <p class="ui-kicker">{{ t('menu.kicker') }}</p>
                <h1 class="ui-display text-xl font-semibold tracking-tight text-white md:text-2xl">{{ tenantName }}</h1>
                <p class="line-clamp-2 text-sm text-slate-300">{{ tenantDescription }}</p>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2 sm:min-w-[220px]">
              <div class="rounded-2xl border border-slate-800/80 bg-slate-950/60 px-3 py-2 backdrop-blur-xl">
                <p class="ui-kicker mb-1">{{ t('stepSuperCategories.heading') }}</p>
                <p class="text-sm font-semibold text-slate-100">{{ itemCountLabel(superCategories.length) }}</p>
              </div>
              <div class="rounded-2xl border border-slate-800/80 bg-slate-950/60 px-3 py-2 backdrop-blur-xl">
                <p class="ui-kicker mb-1">{{ t('common.cart') }}</p>
                <p class="text-sm font-semibold text-slate-100">{{ itemCountLabel(cart.count) }}</p>
              </div>
            </div>
          </div>

          <div class="flex flex-wrap gap-2">
            <span class="ui-chip-strong">{{ statusLabel }}</span>
            <span v-if="locationLine" class="ui-chip">
              <AppIcon name="info" class="h-3.5 w-3.5" />
              {{ locationLine }}
            </span>
            <span v-if="selectedSuperCategory" class="ui-chip">
              <AppIcon name="menu" class="h-3.5 w-3.5" />
              {{ selectedSuperCategory.name }}
            </span>
          </div>

          <div class="rounded-2xl border border-slate-800/80 bg-slate-950/72 p-3 shadow-xl shadow-black/25 backdrop-blur-xl space-y-3">
            <div class="relative">
              <input
                v-model.trim="search"
                class="ui-input pr-12"
                :placeholder="t('menu.searchPlaceholder')"
              />
              <button
                v-if="search"
                class="absolute right-2 top-1/2 -translate-y-1/2 rounded-full border border-slate-700/80 px-2 py-1 text-[11px] text-slate-300 hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)]"
                @click="clearSearch"
              >
                <span class="sr-only">{{ t('common.clear') }}</span>
                <AppIcon name="close" class="h-3.5 w-3.5" />
              </button>
            </div>

            <div v-if="superCategories.length" class="space-y-2">
              <div class="flex items-center justify-between gap-3">
                <p class="ui-kicker">{{ t('stepSuperCategories.heading') }}</p>
                <span class="ui-chip text-[11px]">{{ itemCountLabel(superCategories.length) }}</span>
              </div>
              <div class="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                <button
                  v-for="group in superCategories"
                  :key="group.slug"
                  class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs"
                  :data-active="selectedSuperCategorySlug === group.slug"
                  @click="selectedSuperCategorySlug = group.slug"
                >
                  {{ group.name }}
                </button>
              </div>
            </div>

            <div v-if="visibleCategories.length" class="space-y-2">
              <div class="flex items-center justify-between gap-3">
                <p class="ui-kicker">{{ t('customerLeadPage.categories') }}</p>
                <span class="ui-chip text-[11px]">{{ itemCountLabel(visibleCategories.length) }}</span>
              </div>
              <div class="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                <button
                  v-for="cat in visibleCategories"
                  :key="`cat-${cat.slug}`"
                  class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs"
                  :data-active="selectedCategorySlug === cat.slug"
                  @click="selectCategory(cat.slug)"
                >
                  {{ cat.name }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>

    <section class="ui-panel overflow-hidden p-4 sm:p-5 space-y-4">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div class="space-y-1">
          <p class="ui-kicker">{{ selectedSuperCategory?.name || t('stepSuperCategories.heading') }}</p>
          <h2 class="ui-display text-2xl font-semibold text-white sm:text-3xl">{{ selectedCategory?.name || t('menu.kicker') }}</h2>
          <p class="text-sm text-slate-400">{{ selectedCategory?.description || tenantDescription }}</p>
        </div>
        <div class="ui-scroll-row">
          <span class="ui-data-strip">{{ itemCountLabel(filteredDishes.length) }}</span>
          <span class="ui-data-strip">{{ itemCountLabel(visibleCategories.length) }} {{ t('common.categories') }}</span>
        </div>
      </div>

      <div v-if="selectedCategorySlug && menu.loading && !selectedDishes.length" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <div v-for="n in 3" :key="n" class="ui-skeleton h-72 rounded-[1.8rem]"></div>
      </div>

      <div v-else-if="filteredDishes.length" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="dish in filteredDishes"
          :key="dish.slug"
          class="overflow-hidden rounded-[1.8rem] border border-slate-800/80 bg-slate-950/82 shadow-[0_20px_50px_rgba(2,6,23,0.36)]"
        >
          <button type="button" class="block w-full text-left" @click="goToDish(dish)">
            <div class="relative aspect-[4/3] overflow-hidden bg-slate-900">
              <img
                v-if="dish.image_url"
                :src="dish.image_url"
                :alt="dish.name"
                class="h-full w-full object-cover transition duration-500 hover:scale-[1.03]"
                loading="lazy"
                decoding="async"
              />
              <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/15 to-transparent"></div>
              <div class="absolute inset-x-0 bottom-0 flex items-center justify-between px-4 pb-4">
                <span class="ui-chip-strong">{{ selectedCategory?.name }}</span>
                <span class="rounded-full border border-white/15 bg-slate-950/75 px-2.5 py-1 text-[11px] font-semibold text-white">
                  {{ formatCurrency(dish.price, dish.currency || cartCurrency) }}
                </span>
              </div>
            </div>
            <div class="space-y-3 p-4">
              <div class="space-y-1">
                <h3 class="text-lg font-semibold text-white">{{ dish.name }}</h3>
                <p class="line-clamp-2 text-sm text-slate-400">{{ dish.description || t('stepDishes.descriptionPlaceholder') }}</p>
              </div>
              <div class="flex items-center justify-between gap-3">
                <div class="flex flex-wrap gap-2">
                  <span class="ui-data-strip">{{ formatCurrency(dish.price, dish.currency || cartCurrency) }}</span>
                  <span v-if="dish.options?.length" class="ui-data-strip">{{ itemCountLabel(dish.options.length) }}</span>
                </div>
                <span class="inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-700 bg-slate-950 text-slate-100">
                  <AppIcon name="info" class="h-4 w-4" />
                </span>
              </div>
            </div>
          </button>
        </article>
      </div>

      <div v-else class="ui-empty-state space-y-4 text-slate-300">
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

      <p v-if="menu.error" class="text-sm text-red-400">
        {{ menu.error }}
      </p>
    </section>

    <RouterLink
      v-if="cart.count"
      :to="{ name: 'cart' }"
      class="fixed bottom-[5.15rem] left-2.5 right-2.5 z-20 flex items-center justify-between rounded-2xl border border-slate-700/80 bg-slate-950/92 px-3.5 py-2.5 text-sm text-slate-100 shadow-xl shadow-black/40 backdrop-blur sm:hidden"
    >
      <div>
        <p class="text-xs text-slate-400">{{ t('common.cart') }}</p>
        <p class="font-semibold">{{ itemCountLabel(cart.count) }}</p>
      </div>
      <div class="flex items-center gap-2">
        <p class="text-base font-semibold text-[var(--color-secondary)]">
          {{ formatCurrency(cart.total, cartCurrency) }}
        </p>
        <AppIcon name="cart" class="h-4 w-4 text-slate-200" />
      </div>
    </RouterLink>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { trackEvent } from '../lib/analytics';
import { useCartStore } from '../stores/cart';
import { useMenuStore } from '../stores/menu';
import { useTenantStore } from '../stores/tenant';

const menu = useMenuStore();
const tenant = useTenantStore();
const cart = useCartStore();
const router = useRouter();
const { currentLocale, formatCurrency, itemCountLabel, t } = useI18n();

const search = ref('');
const selectedSuperCategorySlug = ref('');
const selectedCategorySlug = ref('');
const meta = computed(() => tenant.resolvedMeta || null);
const profile = computed(() => meta.value?.profile || null);
const menuCategories = computed(() => (Array.isArray(menu.categories) ? menu.categories : []));
const storeSuperCategories = computed(() => (Array.isArray(menu.superCategories) ? menu.superCategories : []));

const tenantName = computed(() => meta.value?.name || t('customerLayout.fallbackTenantName'));
const tenantDescription = computed(() => String(profile.value?.description || profile.value?.tagline || '').trim() || t('customerLeadPage.fallbackDescription'));
const heroImage = computed(() => String(profile.value?.hero_url || '').trim());
const logoImage = computed(() => String(profile.value?.logo_url || '').trim());
const locationLine = computed(() => String(profile.value?.address || meta.value?.name || '').trim());
const statusLabel = computed(() => (profile.value?.is_open === false ? t('customerLeadPage.closedNow') : t('customerLeadPage.openNow')));
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
  return selectedDishes.value.filter((dish) => [dish.name, dish.description, dish.slug].filter(Boolean).some((value) => String(value).toLowerCase().includes(query)));
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
const clearSearch = () => {
  search.value = '';
};

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
