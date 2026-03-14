<template>
  <div class="space-y-3 px-3 py-2 pb-24 sm:space-y-4 sm:px-4 sm:py-3 sm:pb-8 ui-safe-bottom">
    <header class="ui-hero-stage ui-reveal overflow-hidden p-3 md:p-4">
      <div class="space-y-3">
        <div class="space-y-1">
          <h1 class="ui-display text-lg font-semibold tracking-tight text-white md:text-2xl">
            {{ tenantName }}
          </h1>
          <p class="text-xs text-slate-400 md:text-sm">{{ t('menu.intro') }}</p>
        </div>

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
          v-if="categories.length"
          class="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          <button
            v-for="cat in categories.slice(0, 8)"
            :key="`quick-${cat.slug}`"
            class="ui-state-chip whitespace-nowrap"
            @click="goToCategory(cat.slug)"
          >
            {{ cat.name }}
          </button>
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
      <p class="text-base font-semibold text-[var(--color-secondary)]">
        {{ formatCurrency(cart.total, cartCurrency) }}
      </p>
    </RouterLink>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
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
const { currentLocale, formatCurrency, itemCountLabel, t } = useI18n();

const search = ref('');
const placeholder =
  'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80';
const meta = computed(() => tenant.resolvedMeta || null);
const menuCategories = computed(() =>
  Array.isArray(menu.categories) ? menu.categories : []
);

const tenantName = computed(
  () => meta.value?.name || t('customerLayout.fallbackTenantName')
);
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
