<template>
  <div class="space-y-3 px-3 py-3 pb-28 sm:space-y-4 sm:px-4 sm:py-4 sm:pb-8 ui-safe-bottom">
    <div v-if="menu.loading" class="space-y-3" role="status" aria-live="polite">
      <div class="ui-skeleton h-64 rounded-[1.6rem]"></div>
      <div class="ui-skeleton h-48 rounded-[1.4rem]"></div>
      <p class="text-sm text-slate-400">{{ t('dishPage.loadingDish') }}</p>
    </div>

    <div v-else-if="!dish" class="ui-empty-state space-y-3" role="alert">
      <div class="space-y-1">
        <p class="ui-kicker">{{ categoryName }}</p>
        <p class="text-lg font-semibold text-slate-100">{{ t('dishPage.notFoundTitle') }}</p>
        <p class="text-sm text-slate-400">{{ t('dishPage.notFoundText') }}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <RouterLink :to="{ name: 'category', params: { slug: props.category } }" class="ui-btn-outline justify-center">
          {{ t('dishPage.backToCategory', { category: categoryName }) }}
        </RouterLink>
        <RouterLink :to="{ name: 'menu' }" class="ui-btn-primary justify-center">
          {{ t('customerLayout.navMenu') }}
        </RouterLink>
      </div>
    </div>

    <div v-else class="ui-hero-stage ui-reveal overflow-hidden shadow-2xl shadow-black/30">
      <div class="relative h-[30vh] min-h-[176px] max-h-[280px] w-full sm:h-72">
        <img
          :src="dish.image_url || placeholder"
          :alt="dish.name"
          class="h-full w-full object-cover"
          loading="lazy"
          referrerpolicy="no-referrer"
        />
        <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/25 to-transparent"></div>
        <div class="absolute inset-x-3 bottom-3 space-y-2 sm:inset-x-4 sm:bottom-4">
          <div class="flex flex-wrap items-center gap-2">
            <span class="ui-chip-strong">{{ categoryName }}</span>
            <span v-if="dish.is_vegan" class="ui-chip">{{ t('dishPage.vegan') }}</span>
            <span v-if="dish.is_spicy" class="ui-chip">{{ t('dishPage.spicy') }}</span>
            <span v-if="isBrowseOnlyPlan" class="ui-chip bg-sky-500/20 text-sky-200">{{ t('dishPage.menuOnly') }}</span>
          </div>
          <div class="flex items-end justify-between gap-3">
            <h1 class="ui-display text-2xl font-semibold text-white sm:text-3xl">{{ dish.name }}</h1>
            <p class="rounded-full bg-white/95 px-3 py-1.5 text-sm font-semibold text-slate-900">
              {{ formatCurrency(dish.price, dish.currency) }}
            </p>
          </div>
        </div>
      </div>

      <div class="grid gap-4 p-3 sm:p-4 lg:grid-cols-[minmax(0,1fr),19rem]">
        <section class="space-y-4">
          <div class="flex flex-wrap items-center gap-2">
            <RouterLink :to="{ name: 'category', params: { slug: props.category } }" class="ui-btn-outline justify-center text-xs sm:text-sm">
              {{ t('dishPage.backToCategory', { category: categoryName }) }}
            </RouterLink>
            <RouterLink v-if="cart.count" :to="{ name: 'cart' }" class="ui-btn-outline justify-center text-xs sm:text-sm">
              {{ t('common.cart') }} / {{ cart.count }}
            </RouterLink>
          </div>

          <div class="ui-section-band">
            <p class="leading-relaxed text-slate-200">{{ dish.description || t('dishPage.noDescription') }}</p>
          </div>

          <div v-if="dish.options?.length" class="ui-section-band space-y-3">
            <div class="flex items-center justify-between gap-2">
              <p class="text-sm text-slate-300">{{ t('dishPage.options') }}</p>
              <span class="ui-data-strip">
                {{ t('dishPage.optionsCount', { count: selectedOptionObjects.length }) }}
              </span>
            </div>
            <ul class="grid gap-2 sm:grid-cols-2 text-sm">
              <li
                v-for="opt in dish.options"
                :key="opt.id"
                class="ui-selection-card"
                :data-active="isOptionSelected(opt.id)"
                :data-warning="opt.is_required && !isOptionSelected(opt.id)"
              >
                <label class="flex w-full items-center gap-2">
                  <input
                    v-model="selectedOptionIds"
                    type="checkbox"
                    :value="opt.id"
                    class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]"
                  />
                  <div class="min-w-0 flex-1">
                    <p class="font-semibold text-slate-100">{{ opt.name }}</p>
                    <p v-if="opt.is_required" class="text-[11px] text-amber-300">{{ t('dishPage.required') }}</p>
                  </div>
                  <span class="text-slate-300">+{{ formatCurrency(opt.price_delta, dish.currency) }}</span>
                </label>
              </li>
            </ul>
            <p v-if="hasRequiredMissing" class="text-xs text-amber-300">
              {{ t('dishPage.selectRequiredOptions') }}
            </p>
          </div>

          <div v-if="similarDishes.length || menu.loading" ref="similarVis.target" class="space-y-2 pt-1">
            <p class="text-sm text-slate-300">{{ t('dishPage.similarDishes') }}</p>
            <div class="grid gap-3 sm:grid-cols-2">
              <template v-if="showSimilarSkeletons">
                <div v-for="n in 2" :key="'sk-' + n" class="h-28 animate-pulse rounded-2xl bg-slate-800/50"></div>
              </template>
              <RouterLink
                v-for="item in visibleSimilarDishes"
                :key="item.slug"
                :to="{ name: 'dish', params: { category: props.category, dish: item.slug } }"
                class="group ui-surface-lift overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60 transition-colors hover:border-[var(--color-secondary)]/60"
              >
                <div class="relative h-24 w-full overflow-hidden">
                  <img :src="item.image_url || placeholder" :alt="item.name" class="h-full w-full object-cover transition-transform group-hover:scale-[1.02]" loading="lazy" />
                </div>
                <div class="space-y-1 p-3">
                  <p class="line-clamp-1 text-sm font-semibold text-slate-100">{{ item.name }}</p>
                  <p class="text-sm font-semibold text-[var(--color-secondary)]">{{ formatCurrency(item.price, item.currency) }}</p>
                </div>
              </RouterLink>
            </div>
          </div>
        </section>

        <aside class="hidden space-y-3 sm:block lg:sticky lg:top-[calc(var(--safe-top)+5.5rem)] lg:self-start">
          <div class="ui-spotlight-card space-y-3 p-4">
            <div>
              <p class="ui-kicker">{{ t('dishPage.total') }}</p>
              <p class="text-3xl font-semibold text-white">{{ formatCurrency(totalWithOptions, dish.currency) }}</p>
            </div>

            <label class="inline-flex items-center gap-2 text-sm text-slate-300">
              {{ t('dishPage.qty') }}
              <span class="inline-flex items-center rounded-full border border-slate-700 bg-slate-900/70 p-1">
                <button class="ui-press h-8 w-8 rounded-full text-sm text-slate-200 hover:bg-slate-800" :aria-label="t('dishPage.decreaseQuantity')" @click="decrementQty">-</button>
                <input v-model.number="qty" type="number" min="1" max="99" class="w-12 border-0 bg-transparent text-center text-sm text-slate-100 focus:outline-none" />
                <button class="ui-press h-8 w-8 rounded-full text-sm text-slate-200 hover:bg-slate-800" :aria-label="t('dishPage.increaseQuantity')" @click="incrementQty">+</button>
              </span>
            </label>

            <div class="grid gap-2">
              <button
                class="ui-btn-primary w-full justify-center"
                :class="orderingDisabled ? 'cursor-not-allowed opacity-60' : ''"
                :disabled="orderingDisabled"
                @click="addToCart"
                @keydown.enter.prevent="addToCart"
                @keydown.space.prevent="addToCart"
              >
                {{
                  isBrowseOnlyPlan
                    ? t('dishPage.browseOnlyPlan')
                    : cart.canCheckout || cart.canWhatsapp
                      ? t('dishPage.addToCart')
                      : t('dishPage.addContactToOrder')
                }}
              </button>
              <RouterLink :to="{ name: 'cart' }" class="ui-btn-outline w-full justify-center">
                {{ t('common.cart') }}
              </RouterLink>
              <button
                v-if="cart.canWhatsapp"
                class="ui-btn-outline w-full justify-center"
                :disabled="!canWhatsappShare || !isRestaurantOpen"
                :class="!canWhatsappShare || !isRestaurantOpen ? 'cursor-not-allowed opacity-50' : ''"
                @click="canWhatsappShare ? shareWhatsapp() : null"
                @keydown.enter.prevent="canWhatsappShare ? shareWhatsapp() : null"
                @keydown.space.prevent="canWhatsappShare ? shareWhatsapp() : null"
              >
                {{
                  !isRestaurantOpen
                    ? t('dishPage.restaurantClosed')
                    : canWhatsappShare
                      ? t('dishPage.shareViaWhatsApp')
                      : t('dishPage.addRestaurantPhoneToEnable')
                }}
              </button>
            </div>

            <p v-if="hasRequiredMissing" class="text-xs text-amber-300">{{ t('dishPage.selectRequiredOptions') }}</p>
            <p v-if="!isRestaurantOpen" class="text-xs text-amber-300">{{ t('dishPage.restaurantClosedNotice') }}</p>
          </div>
        </aside>
      </div>
    </div>

    <div
      v-if="dish"
      class="fixed bottom-20 left-3 right-3 z-20 rounded-2xl border border-slate-800/80 bg-slate-900/92 px-3.5 py-2.5 backdrop-blur sm:hidden"
    >
      <div class="flex items-center justify-between gap-3">
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold text-slate-100">{{ dish.name }}</p>
          <p class="text-xs text-slate-400">
            {{
              hasRequiredMissing
                ? t('dishPage.selectRequiredOptions')
                : `${selectedOptionObjects.length} ${t('dishPage.options')}`
            }}
          </p>
        </div>
        <p class="shrink-0 text-lg font-semibold text-[var(--color-secondary)]">
          {{ formatCurrency(totalWithOptions, dish.currency) }}
        </p>
      </div>

      <div class="mt-2.5 flex items-center gap-2">
        <span class="inline-flex items-center rounded-full border border-slate-700 bg-slate-900/70 p-1">
          <button class="ui-press h-8 w-8 rounded-full text-sm text-slate-200 hover:bg-slate-800" :aria-label="t('dishPage.decreaseQuantity')" @click="decrementQty">-</button>
          <input v-model.number="qty" type="number" min="1" max="99" class="w-10 border-0 bg-transparent text-center text-sm text-slate-100 focus:outline-none" />
          <button class="ui-press h-8 w-8 rounded-full text-sm text-slate-200 hover:bg-slate-800" :aria-label="t('dishPage.increaseQuantity')" @click="incrementQty">+</button>
        </span>
        <button
          class="ui-btn-primary ml-auto px-4 py-2"
          :disabled="orderingDisabled"
          :class="orderingDisabled ? 'cursor-not-allowed opacity-60' : ''"
          @click="addToCart"
          @keydown.enter.prevent="addToCart"
          @keydown.space.prevent="addToCart"
        >
          {{ isBrowseOnlyPlan ? t('dishPage.viewOnly') : t('dishPage.add') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch, watchEffect } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from '../composables/useI18n';
import { useMenuStore } from '../stores/menu';
import { useCartStore } from '../stores/cart';
import { useToastStore } from '../stores/toast';
import { useTenantStore } from '../stores/tenant';
import { useVisibility } from '../composables/useVisibility';
import { trackEvent } from '../lib/analytics';

const props = defineProps({ category: String, dish: String });

const route = useRoute();
const menu = useMenuStore();
const cart = useCartStore();
const tenant = useTenantStore();
const toast = useToastStore();
const { currentLocale, formatCurrency, itemCountLabel, t } = useI18n();
const similarVis = useVisibility();
const qty = ref(1);
const selectedOptionIds = ref([]);
const whatsappPhone = (import.meta.env.VITE_CONTACT_PHONE || '').replace(
  /[^\d+]/g,
  ''
);
const copyStatus = ref('');
const meta = computed(() => tenant.resolvedMeta || null);

const dishes = computed(() => menu.dishes[props.category] || []);
const dish = computed(() => dishes.value.find((d) => d.slug === props.dish));
const placeholder =
  'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=900&q=80';
const menuCategories = computed(() =>
  Array.isArray(menu.categories) ? menu.categories : []
);
const categoryName = computed(
  () =>
    menuCategories.value.find((c) => c.slug === props.category)?.name ||
    props.category
);
const similarDishes = computed(() =>
  dishes.value
    .filter((d) => d.slug !== props.dish)
    .sort((a, b) => (a.price || 0) - (b.price || 0))
    .slice(0, 3)
);
const showSimilarSkeletons = computed(
  () => menu.loading && !similarVis.isVisible
);
const visibleSimilarDishes = computed(() =>
  similarVis.isVisible ? similarDishes.value : []
);
const isBrowseOnlyPlan = computed(() => tenant.isBrowseOnlyPlan === true);
const isRestaurantOpen = computed(() => meta.value?.profile?.is_open !== false);
const orderingStateLabel = computed(() => {
  if (isBrowseOnlyPlan.value) return t('dishPage.menuOnly');
  return isRestaurantOpen.value ? t('customerLeadPage.openNow') : t('customerLeadPage.closedNow');
});
const selectionStateLabel = computed(() => {
  if (hasRequiredMissing.value) return t('dishPage.selectRequiredOptions');
  if (selectedOptionObjects.value.length) {
    return t('dishPage.optionsCount', { count: selectedOptionObjects.value.length });
  }
  return orderingStateLabel.value;
});
const selectionDotClass = computed(() => {
  if (hasRequiredMissing.value) return 'bg-amber-400';
  if (selectedOptionObjects.value.length) return 'bg-emerald-400';
  return isRestaurantOpen.value ? 'bg-[var(--color-secondary)]' : 'bg-rose-400';
});
const shareUrl = computed(() => {
  if (typeof window === 'undefined') return route.fullPath;
  return `${window.location.origin}${route.fullPath}`;
});

const prefMotionReduce =
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const selectedOptionObjects = computed(() => {
  if (!dish.value?.options) return [];
  const byId = new Map(dish.value.options.map((o) => [o.id, o]));
  return selectedOptionIds.value.map((id) => byId.get(id)).filter(Boolean);
});

const selectedOptionNote = computed(() => {
  if (!selectedOptionObjects.value.length || !dish.value) return '';
  const bits = selectedOptionObjects.value.map(
    (opt) =>
      `${opt.name} (+${formatCurrency(opt.price_delta, dish.value.currency)})`
  );
  return `${t('dishPage.options')}: ${bits.join(', ')}`;
});

const selectedOptionIdsSorted = computed(() =>
  [...selectedOptionIds.value]
    .map((x) => Number(x))
    .filter((x) => Number.isInteger(x) && x > 0)
    .sort((a, b) => a - b)
);

const unitOptionTotal = computed(() =>
  selectedOptionObjects.value.reduce(
    (sum, opt) => sum + Number(opt.price_delta || 0),
    0
  )
);

const unitPriceWithOptions = computed(() => {
  if (!dish.value) return 0;
  return (Number(dish.value.price) || 0) + unitOptionTotal.value;
});

const baseTotal = computed(() => {
  if (!dish.value) return 0;
  const unit = Number(dish.value.price) || 0;
  return unit * (qty.value || 1);
});

const extrasTotal = computed(() => {
  return unitOptionTotal.value * (qty.value || 1);
});

const totalWithOptions = computed(() => {
  if (!dish.value) return 0;
  return baseTotal.value + extrasTotal.value;
});

const hasRequiredMissing = computed(
  () =>
    dish.value?.options?.some(
      (opt) => opt.is_required && !selectedOptionIds.value.includes(opt.id)
    ) || false
);

const orderingDisabled = computed(
  () =>
    hasRequiredMissing.value ||
    !isRestaurantOpen.value ||
    isBrowseOnlyPlan.value
);

const canWhatsappShare = computed(
  () => !!whatsappPhone && cart.canWhatsapp && !hasRequiredMissing.value
);
const isOptionSelected = (optionId) =>
  selectedOptionIds.value.includes(optionId);

const normalizeQty = (value) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 1;
  return Math.min(99, Math.max(1, Math.round(parsed)));
};

const incrementQty = () => {
  qty.value = normalizeQty((qty.value || 1) + 1);
};

const decrementQty = () => {
  qty.value = normalizeQty((qty.value || 1) - 1);
};

const addToCart = () => {
  if (!isRestaurantOpen.value) {
    toast.show(t('dishPage.restaurantCurrentlyClosed'), 'error');
    return;
  }
  if (isBrowseOnlyPlan.value) {
    toast.show(t('dishPage.orderingDisabledForPlan'), 'info');
    return;
  }
  if (!dish.value) return;
  if (hasRequiredMissing.value) {
    toast.show(t('dishPage.selectRequiredOptionsFirst'), 'error');
    return;
  }
  const quantity = qty.value && qty.value > 0 ? qty.value : 1;
  const optionSig = selectedOptionIdsSorted.value.join(',');
  cart.add({
    key: `${dish.value.slug}::${optionSig}`,
    slug: dish.value.slug,
    name: dish.value.name,
    price: Number(unitPriceWithOptions.value),
    currency: dish.value.currency,
    qty: quantity,
    note: selectedOptionNote.value,
    option_ids: selectedOptionIdsSorted.value,
    option_labels: selectedOptionObjects.value.map((opt) => opt.name),
  });
  toast.show(t('dishPage.addedToCart'), 'success');
};

const shareWhatsapp = () => {
  if (!isRestaurantOpen.value) {
    toast.show(t('dishPage.restaurantCurrentlyClosed'), 'error');
    return;
  }
  if (!dish.value) return;
  if (!whatsappPhone) {
    toast.show(t('dishPage.addRestaurantWhatsappToEnable'), 'error');
    return;
  }
  const lines = [
    t('dishPage.whatsappOrderIntro'),
    `- ${qty.value} x ${dish.value.name} (${formatCurrency(totalWithOptions.value, dish.value.currency)})`,
    ...selectedOptionObjects.value.map(
      (opt) =>
        `  - ${opt.name} (+${formatCurrency(opt.price_delta, dish.value.currency)})`
    ),
  ];
  const msg = encodeURIComponent(lines.join('\n'));
  trackEvent('order_handoff_click', {
    source: 'dish_quick_share',
    category_slug: props.category,
    dish_slug: dish.value.slug,
    metadata: { qty: qty.value },
  });
  window.open(
    `https://wa.me/${whatsappPhone}?text=${msg}`,
    '_blank',
    'noopener,noreferrer'
  );
  toast.show(t('dishPage.openingWhatsApp'), 'info');
};

const summaryText = computed(() => {
  if (!dish.value) return '';
  const parts = [
    `${qty.value} x ${dish.value.name} (${formatCurrency(totalWithOptions.value, dish.value.currency)})`,
    ...selectedOptionObjects.value.map(
      (opt) =>
        `- ${opt.name} (+${formatCurrency(opt.price_delta, dish.value.currency)})`
    ),
  ];
  return parts.join('\n');
});

const copySummary = async () => {
  if (!summaryText.value) return;
  try {
    await navigator.clipboard.writeText(summaryText.value);
    copyStatus.value = t('dishPage.summaryCopied');
    toast.show(t('dishPage.summaryCopiedToClipboard'), 'success');
  } catch {
    copyStatus.value = t('dishPage.copyFailed');
    toast.show(t('dishPage.copyFailed'), 'error');
  }
  setTimeout(() => (copyStatus.value = ''), 2000);
};

const copyLink = async () => {
  if (!shareUrl.value) return;
  try {
    await navigator.clipboard.writeText(shareUrl.value);
    toast.show(t('dishPage.linkCopied'), 'success');
  } catch {
    toast.show(t('dishPage.copyFailed'), 'error');
  }
};

const resetOptions = () => {
  selectedOptionIds.value = [];
  if (dish.value?.options?.length) {
    dish.value.options.forEach((opt) => {
      if (opt.is_required && !selectedOptionIds.value.includes(opt.id)) {
        selectedOptionIds.value.push(opt.id);
      }
    });
  }
};

const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: prefMotionReduce ? 'auto' : 'smooth' });
};

watch(
  () => dish.value?.id,
  () => {
    qty.value = 1;
    selectedOptionIds.value = [];
  }
);

watch(
  () => dish.value?.slug,
  (slug) => {
    if (!slug) return;
    trackEvent(
      'dish_view',
      {
        source: 'customer_dish',
        category_slug: props.category,
        dish_slug: slug,
      },
      { onceKey: `dish:${slug}` }
    );
  },
  { immediate: true }
);

watch(
  () => props.category,
  (slug) => {
    if (slug) {
      if (!menuCategories.value.length) menu.fetchCategories();
      menu.fetchDishesByCategory(slug);
    }
  },
  { flush: 'post' }
);

onMounted(() => {
  if (!tenant.meta) tenant.fetchMeta();
  if (!menuCategories.value.length) menu.fetchCategories();
  if (!menu.dishes[props.category]) menu.fetchDishesByCategory(props.category);
});

watchEffect(() => {
  qty.value = normalizeQty(qty.value);
  if (dish.value?.options?.length) {
    dish.value.options.forEach((opt) => {
      if (opt.is_required && !selectedOptionIds.value.includes(opt.id)) {
        selectedOptionIds.value.push(opt.id);
      }
    });
  }
});

watch(
  () => currentLocale.value,
  () => {
    if (!props.category) return;
    menu.fetchCategories(true);
    menu.fetchDishesByCategory(props.category, true);
  }
);
</script>

