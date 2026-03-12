<template>
  <div class="space-y-4 px-4 py-3 pb-32 sm:pb-8 ui-safe-bottom">
    <header class="ui-hero-stage ui-reveal overflow-hidden p-4 md:p-5">
      <div
        class="grid gap-4 lg:grid-cols-[minmax(0,1.15fr),20rem] lg:items-start"
      >
        <div class="space-y-3">
          <div class="space-y-1.5">
            <p class="ui-kicker">{{ t('menu.kicker') }}</p>
            <h1
              class="ui-display text-xl font-semibold tracking-tight text-white md:text-3xl"
            >
              {{ tenantName }}
            </h1>
            <p class="max-w-2xl text-sm leading-relaxed text-slate-300">
              {{ t('menu.intro') }}
            </p>
          </div>

          <div class="flex flex-wrap gap-2">
            <span class="ui-chip-strong"
            >{{ categories.length }} {{ t('common.categories') }}</span
            >
            <span class="ui-chip"
            >{{ totalDishes }} {{ t('common.dishes') }}</span
            >
            <span class="ui-chip"
            >{{ t('menu.mode') }}: {{ orderingModeLabel }}</span
            >
          </div>

          <div v-if="heroCategories.length" class="flex flex-wrap gap-2">
            <button
              v-for="cat in heroCategories"
              :key="`hero-${cat.slug}`"
              class="ui-pill-nav text-xs"
              @click="goToCategory(cat.slug)"
            >
              {{ cat.name }}
            </button>
          </div>
        </div>

        <div class="grid gap-3">
          <button
            v-if="heroCategory"
            class="group ui-spotlight-card ui-press overflow-hidden text-left"
            @click="goToCategory(heroCategory.slug)"
          >
            <div class="absolute inset-0">
              <img
                :src="heroCategory.image_url || placeholder"
                :alt="heroCategory.name"
                class="h-full w-full object-cover opacity-35 transition-transform duration-500 group-hover:scale-105"
                loading="lazy"
              />
              <div
                class="absolute inset-0 bg-gradient-to-br from-slate-950/80 via-slate-950/65 to-slate-950/85"
              ></div>
            </div>
            <div class="relative space-y-3">
              <div class="flex items-start justify-between gap-3">
                <span class="ui-chip-strong"
                >{{ heroCategory.dishes?.length || 0 }}
                  {{ t('common.dishes') }}</span
                >
                <span class="ui-chip text-[var(--color-secondary)]">{{
                  t('common.categories')
                }}</span>
              </div>
              <div class="space-y-1">
                <p class="line-clamp-1 text-lg font-semibold text-white">
                  {{ heroCategory.name }}
                </p>
                <p class="text-xs text-slate-300">{{ orderingModeLabel }}</p>
              </div>
            </div>
          </button>

          <RouterLink
            v-if="cart.count"
            :to="{ name: 'cart' }"
            class="ui-section-band flex items-center justify-between gap-3 p-4 text-left transition-colors hover:border-[var(--color-secondary)]/55"
          >
            <div class="space-y-1">
              <p class="text-xs uppercase tracking-[0.18em] text-slate-500">
                {{ t('common.cart') }}
              </p>
              <p class="text-base font-semibold text-slate-100">
                {{ itemCountLabel(cart.count) }}
              </p>
            </div>
            <p class="text-lg font-semibold text-[var(--color-secondary)]">
              {{ formatCurrency(cart.total, cartCurrency) }}
            </p>
          </RouterLink>
        </div>
      </div>
    </header>

    <section
      class="ui-glass ui-reveal ui-surface-lift sticky top-[calc(var(--safe-top)+4.8rem)] z-10 space-y-3 p-3.5 md:static md:p-4"
      style="--ui-delay: 50ms"
    >
      <div class="grid gap-3 md:grid-cols-[1fr,auto] md:items-center">
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
            {{ t('common.clear') }}
          </button>
        </div>

        <div
          class="grid grid-cols-2 gap-2 text-xs text-slate-400 md:flex md:flex-wrap md:items-center"
        >
          <button
            class="ui-pill-nav text-xs md:min-w-[7rem]"
            :class="
              sortBy === 'position'
                ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                : ''
            "
            @click="sortBy = 'position'"
          >
            {{ t('menu.sortOrder') }}
          </button>
          <button
            class="ui-pill-nav text-xs md:min-w-[7rem]"
            :class="
              sortBy === 'count'
                ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                : ''
            "
            @click="sortBy = 'count'"
          >
            {{ t('menu.sortItems') }}
          </button>
        </div>
      </div>
      <div
        class="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500"
      >
        <p>{{ t('menu.tip') }}</p>
        <p class="ui-chip">{{ totalDishes }} {{ t('common.dishes') }}</p>
      </div>
      <div
        v-if="categories.length"
        class="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        <button
          v-for="cat in categories.slice(0, 8)"
          :key="`quick-${cat.slug}`"
          class="ui-chip whitespace-nowrap transition-colors hover:border-[var(--color-secondary)]/55 hover:text-[var(--color-secondary)]"
          @click="goToCategory(cat.slug)"
        >
          {{ cat.name }}
        </button>
      </div>
      <div class="ui-toolbar-band grid gap-3 md:grid-cols-[minmax(0,1fr),auto] md:items-center">
        <div class="flex flex-wrap items-center gap-2 text-xs text-slate-300">
          <span class="ui-data-strip">{{ categories.length }} {{ t('common.categories') }}</span>
          <span class="ui-data-strip">{{ totalDishes }} {{ t('common.dishes') }}</span>
          <span v-if="highlightCategory" class="ui-data-strip">{{ highlightCategory.name }}</span>
          <span v-if="search" class="ui-data-strip text-[var(--color-secondary)]">{{ search }}</span>
        </div>
        <div class="grid grid-cols-2 gap-2 sm:flex">
          <RouterLink :to="{ name: 'customer-home' }" class="ui-btn-outline justify-center text-xs sm:text-sm">
            {{ t('customerLayout.navInfo') }}
          </RouterLink>
          <RouterLink :to="{ name: 'reserve' }" class="ui-btn-primary justify-center text-xs sm:text-sm">
            {{ t('customerLayout.navReserve') }}
          </RouterLink>
        </div>
      </div>
    </section>

    <section
      v-if="featuredCategoryCards.length"
      class="grid gap-3 xl:grid-cols-[minmax(0,1.12fr),320px]"
    >
      <article class="ui-section-band ui-reveal p-4 md:p-5" style="--ui-delay: 80ms">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="space-y-1">
            <p class="ui-kicker">{{ t('menu.kicker') }}</p>
            <h2 class="text-xl font-semibold text-white">{{ t('customerLeadPage.browseTitle') }}</h2>
          </div>
          <span class="ui-chip-strong">
            {{ featuredCategoryCards.length }} {{ t('common.categories') }}
          </span>
        </div>

        <div class="mt-4 grid gap-3 md:grid-cols-3">
          <button
            v-for="category in featuredCategoryCards"
            :key="`featured-${category.slug}`"
            class="ui-orbit-card ui-surface-lift ui-press overflow-hidden p-0 text-left transition hover:border-[var(--color-secondary)]/70"
            @click="goToCategory(category.slug)"
          >
            <div class="relative min-h-[176px] overflow-hidden">
              <img
                :src="category.image_url || placeholder"
                :alt="category.name"
                class="absolute inset-0 h-full w-full object-cover opacity-50"
                loading="lazy"
              />
              <div class="absolute inset-0 bg-gradient-to-br from-slate-950/82 via-slate-950/70 to-slate-950/86"></div>

              <div class="relative flex min-h-[176px] flex-col justify-between p-4">
                <div class="flex items-start justify-between gap-3">
                  <span class="ui-chip-strong">
                    {{ category.dishes?.length || 0 }} {{ t('common.dishes') }}
                  </span>
                  <span class="ui-chip text-[10px]">{{ category.rank }}</span>
                </div>
                <div class="space-y-1">
                  <p class="line-clamp-1 text-lg font-semibold text-white">
                    {{ category.name }}
                  </p>
                  <p class="line-clamp-2 text-sm text-slate-300">
                    {{ category.description || t('menu.tip') }}
                  </p>
                </div>
              </div>
            </div>
          </button>
        </div>
      </article>

      <aside class="ui-command-deck ui-reveal p-4 md:p-5" style="--ui-delay: 110ms">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t('customerLeadPage.stepOne') }}</p>
          <h2 class="text-xl font-semibold text-white">{{ t('menu.kicker') }}</h2>
          <p class="text-sm text-slate-300">{{ t('menu.tip') }}</p>
        </div>

        <div class="mt-4 grid gap-2">
          <button
            v-for="category in categories.slice(0, 5)"
            :key="`rail-${category.slug}`"
            class="ui-admin-subcard flex items-center justify-between gap-3 text-left transition hover:border-[var(--color-secondary)]/70"
            @click="goToCategory(category.slug)"
          >
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold text-white">{{ category.name }}</p>
              <p class="mt-1 text-xs text-slate-400">
                {{ category.dishes?.length || 0 }} {{ t('common.dishes') }}
              </p>
            </div>
            <span class="ui-chip text-[10px]">{{ t('categoryCard.go') }}</span>
          </button>
        </div>
      </aside>
    </section>

    <div class="grid gap-4 sm:grid-cols-2">
      <CategoryCard
        v-for="(cat, index) in categories"
        :key="cat.slug"
        :title="cat.name"
        :image="cat.image_url || placeholder"
        :count="cat.dishes?.length || 0"
        :index="index"
        @click="goToCategory(cat.slug)"
      />

      <div
        v-if="!menu.loading && !categories.length"
        class="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 text-slate-300 sm:col-span-2"
      >
        <p class="font-semibold text-slate-100">{{ t('menu.noMatchTitle') }}</p>
        <p class="mt-1 text-sm text-slate-400">{{ t('menu.noMatchText') }}</p>
      </div>

      <div v-if="menu.loading" class="space-y-3 sm:col-span-2">
        <div
          v-for="n in 4"
          :key="n"
          class="h-48 animate-pulse rounded-3xl bg-slate-800/50"
        ></div>
      </div>

      <p v-if="menu.error" class="text-sm text-red-400 sm:col-span-2">
        {{ menu.error }}
      </p>
    </div>

    <section v-if="categories.length" class="ui-section-band ui-reveal space-y-3 p-4" style="--ui-delay: 110ms">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t('menu.kicker') }}</p>
          <h2 class="text-xl font-semibold text-white">{{ tenantName }}</h2>
          <p class="text-sm text-slate-400">{{ t('menu.tip') }}</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <RouterLink :to="{ name: 'customer-home' }" class="ui-btn-outline justify-center">
            {{ t('common.landing') }}
          </RouterLink>
          <RouterLink v-if="cart.count" :to="{ name: 'cart' }" class="ui-btn-outline justify-center">
            {{ t('common.cart') }}
          </RouterLink>
          <RouterLink :to="{ name: 'reserve' }" class="ui-btn-primary justify-center">
            {{ t('common.reserve') }}
          </RouterLink>
        </div>
      </div>
    </section>

    <RouterLink
      v-if="cart.count"
      :to="{ name: 'cart' }"
      class="fixed bottom-20 left-3 right-3 z-20 flex items-center justify-between rounded-2xl border border-slate-700/80 bg-slate-950/92 px-4 py-3 text-sm text-slate-100 shadow-xl shadow-black/40 backdrop-blur sm:hidden"
    >
      <div>
        <p class="text-xs text-slate-400">{{ t('common.cart') }}</p>
        <p class="font-semibold">{{ itemCountLabel(cart.count) }}</p>
      </div>
      <p class="text-base font-semibold text-[var(--color-secondary)]">
        {{ formatCurrency(cart.total, cartCurrency) }}
      </p>
    </RouterLink>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import CategoryCard from '../components/CategoryCard.vue';
import { useI18n } from '../composables/useI18n';
import { trackEvent } from '../lib/analytics';
import { useCartStore } from '../stores/cart';
import { useMenuStore } from '../stores/menu';
import { useTenantStore } from '../stores/tenant';

const menu = useMenuStore();
const tenant = useTenantStore();
const cart = useCartStore();
const router = useRouter();
const { formatCurrency, t } = useI18n();

const search = ref('');
const sortBy = ref('position');
const placeholder =
  'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80';
const meta = computed(() => tenant.resolvedMeta || null);
const menuCategories = computed(() =>
  Array.isArray(menu.categories) ? menu.categories : []
);

const tenantName = computed(
  () => meta.value?.name || t('customerLayout.fallbackTenantName')
);
const orderingModeLabel = computed(() => {
  const mode = String(
    tenant.entitlements?.ordering_mode || 'browse'
  ).toLowerCase();
  if (mode === 'checkout') return t('customerLeadPage.checkout');
  if (mode === 'whatsapp') return t('customerLeadPage.whatsapp');
  return t('customerLeadPage.browseOnly');
});
const cartCurrency = computed(() => {
  const firstItemCurrency = cart.items.find((item) => item.currency)?.currency;
  return firstItemCurrency || meta.value?.plan?.currency || 'USD';
});
const heroCategories = computed(() => categories.value.slice(0, 4));
const heroCategory = computed(() => {
  const ranked = [...menuCategories.value].sort(
    (a, b) => (b.dishes?.length || 0) - (a.dishes?.length || 0)
  );
  return ranked[0] || null;
});
const highlightCategory = computed(() => categories.value[0] || heroCategory.value || null);
const featuredCategoryCards = computed(() =>
  [...categories.value]
    .sort((a, b) => (b.dishes?.length || 0) - (a.dishes?.length || 0))
    .slice(0, 3)
    .map((category, index) => ({
      ...category,
      rank: String(index + 1).padStart(2, '0'),
    }))
);

const categories = computed(() => {
  const term = search.value.toLowerCase();
  const filtered = menuCategories.value.filter((cat) => {
    const name = String(cat.name || '').toLowerCase();
    return !term || name.includes(term);
  });

  const sorted = [...filtered];
  if (sortBy.value === 'count') {
    sorted.sort((a, b) => (b.dishes?.length || 0) - (a.dishes?.length || 0));
  } else {
    sorted.sort((a, b) => (a.position || 0) - (b.position || 0));
  }
  return sorted;
});

const totalDishes = computed(() =>
  categories.value.reduce(
    (sum, cat) => sum + Number(cat?.dishes?.length || 0),
    0
  )
);
const goToCategory = (slug) =>
  router.push({ name: 'category', params: { slug } });
const clearSearch = () => {
  search.value = '';
};

onMounted(async () => {
  if (!menuCategories.value.length) await menu.fetchCategories();
  trackEvent('menu_view', { source: 'customer_menu_browse' });
});
</script>
