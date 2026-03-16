<template>
  <div
    :class="[
      'space-y-3 px-3 py-2 sm:space-y-4 sm:px-4 sm:py-3 sm:pb-8 ui-safe-bottom',
      cart.count ? 'pb-44' : 'pb-24',
    ]"
  >
    <header class="ui-hero-stage ui-reveal overflow-hidden border border-slate-800/80 bg-slate-950/82 p-0">
      <div class="relative min-h-[15rem] overflow-hidden rounded-[1.35rem] bg-slate-950/90 sm:min-h-[17rem]">
        <img
          v-if="heroImage"
          :src="heroImage"
          :alt="`${tenantName} cover`"
          class="absolute inset-0 h-full w-full object-cover"
          loading="eager"
          fetchpriority="high"
          decoding="async"
        />
        <div class="absolute inset-0 bg-slate-950/82"></div>
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(20,184,166,0.12),transparent_30%),radial-gradient(circle_at_bottom_left,rgba(245,158,11,0.12),transparent_28%)]"></div>

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
                <h1 class="ui-display text-xl font-semibold tracking-tight text-white md:text-2xl">
                  {{ tenantName }}
                </h1>
                <p class="line-clamp-2 text-sm text-slate-300">{{ tenantDescription }}</p>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2 sm:min-w-[220px]">
              <div class="rounded-2xl border border-slate-800/80 bg-slate-950/60 px-3 py-2 backdrop-blur-xl">
                <p class="ui-kicker mb-1">{{ t("customerLeadPage.categories") }}</p>
                <p class="text-sm font-semibold text-slate-100">{{ categories.length }}</p>
              </div>
              <div class="rounded-2xl border border-slate-800/80 bg-slate-950/60 px-3 py-2 backdrop-blur-xl">
                <p class="ui-kicker mb-1">{{ t("common.cart") }}</p>
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
          </div>

          <div class="rounded-2xl border border-slate-800/80 bg-slate-950/72 p-3 shadow-xl shadow-black/25 backdrop-blur-xl">
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

            <div v-if="categories.length" class="mt-3 space-y-2">
              <div class="flex items-center justify-between gap-3">
                <p class="ui-kicker">{{ t("customerLeadPage.categories") }}</p>
                <span class="ui-chip text-[11px]">{{ itemCountLabel(categories.length) }}</span>
              </div>
              <div class="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                <button
                  v-for="cat in categories.slice(0, 7)"
                  :key="`quick-${cat.slug}`"
                  class="ui-pill-nav whitespace-nowrap px-3 py-1 text-xs"
                  @click="goToCategory(cat.slug)"
                >
                  {{ cat.name }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>

    <div class="grid gap-4 sm:grid-cols-2">
      <CategoryCard
        v-for="(cat, index) in categories"
        :key="cat.slug"
        :title="cat.name"
        :image="cat.image_url || placeholder"
        :count="cat.dishes?.length || 0"
        :index="index"
        :eager="index < 2"
        @click="goToCategory(cat.slug)"
      />

      <div
        v-if="!menu.loading && !categories.length"
        class="ui-empty-state space-y-4 text-slate-300 sm:col-span-2"
      >
        <div class="space-y-1">
          <p class="ui-kicker">{{ t('menu.kicker') }}</p>
          <p class="text-xl font-semibold text-slate-100">{{ t('menu.noMatchTitle') }}</p>
          <p class="text-sm text-slate-400">{{ t('menu.noMatchText') }}</p>
        </div>
        <button class="ui-btn-outline justify-center" @click="clearSearch">
          <AppIcon name="close" class="h-3.5 w-3.5" />
          {{ t('common.clear') }}
        </button>
      </div>

      <div v-if="menu.loading" class="grid gap-4 sm:col-span-2 sm:grid-cols-2">
        <div
          v-for="n in 4"
          :key="n"
          class="ui-skeleton h-56 rounded-[1.8rem]"
        ></div>
      </div>

      <p v-if="menu.error" class="text-sm text-red-400 sm:col-span-2">
        {{ menu.error }}
      </p>
    </div>

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
const { currentLocale, formatCurrency, itemCountLabel, t } = useI18n();

const search = ref('');
const placeholder =
  'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80';
const meta = computed(() => tenant.resolvedMeta || null);
const profile = computed(() => meta.value?.profile || null);
const menuCategories = computed(() =>
  Array.isArray(menu.categories) ? menu.categories : []
);

const tenantName = computed(
  () => meta.value?.name || t('customerLayout.fallbackTenantName')
);
const tenantDescription = computed(
  () => String(profile.value?.description || profile.value?.tagline || '').trim() || t('customerLeadPage.fallbackDescription')
);
const heroImage = computed(() => String(profile.value?.hero_url || '').trim());
const logoImage = computed(() => String(profile.value?.logo_url || '').trim());
const locationLine = computed(() => String(profile.value?.address || meta.value?.name || '').trim());
const statusLabel = computed(() => (profile.value?.is_open === false ? t('customerLeadPage.closedNow') : t('customerLeadPage.openNow')));
const cartCurrency = computed(() => {
  const firstItemCurrency = cart.items.find((item) => item.currency)?.currency;
  return firstItemCurrency || meta.value?.plan?.currency || 'USD';
});
const categories = computed(() => {
  const term = search.value.toLowerCase();
  const filtered = menuCategories.value.filter((cat) => {
    const name = String(cat.name || '').toLowerCase();
    return !term || name.includes(term);
  });

  return [...filtered].sort((a, b) => (a.position || 0) - (b.position || 0));
});
const goToCategory = (slug) =>
  router.push({ name: 'category', params: { slug } });
const clearSearch = () => {
  search.value = '';
};

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
