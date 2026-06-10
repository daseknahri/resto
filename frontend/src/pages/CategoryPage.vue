<template>
  <div class="space-y-5 px-3 py-4 pb-24 sm:space-y-6 sm:px-4 sm:py-5 ui-safe-bottom">
    <!-- Category hero -->
    <header class="ui-hero-stage ui-reveal overflow-hidden border border-slate-800/80 bg-slate-950/84 p-0">
      <div class="relative min-h-[12rem] overflow-hidden rounded-[1.35rem] bg-slate-950/90 sm:min-h-[14rem]">
        <img
          v-if="currentCategory?.image_url"
          :src="currentCategory.image_url"
          :alt="categoryName"
          class="absolute inset-0 h-full w-full object-cover"
          loading="eager"
          fetchpriority="high"
          decoding="async"
          @error="handleCategoryImageError"
        />
        <div aria-hidden="true" class="absolute inset-0 bg-gradient-to-t from-slate-950/97 via-slate-950/55 to-slate-950/10"></div>

        <div class="relative flex h-full flex-col justify-end space-y-3 p-5 md:p-6">
          <div class="space-y-1.5">
            <p class="ui-kicker tracking-widest uppercase text-[10px]">{{ t("category.kicker") }}</p>
            <h1 class="ui-display text-3xl font-bold capitalize tracking-tight text-white md:text-4xl">{{ categoryName }}</h1>
            <p v-if="categoryDescription" class="ui-subtle max-w-2xl text-sm leading-relaxed">{{ categoryDescription }}</p>
          </div>
          <div class="flex flex-wrap items-center gap-2 pt-1">
            <span class="ui-chip tabular-nums text-[11px] font-medium">{{ itemCountLabel(filteredDishes.length) }}</span>
            <RouterLink
              :to="{ name: 'menu' }"
              class="ui-chip text-[11px] font-medium hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)]"
              :aria-label="t('customerLayout.navMenu')"
            >
              <AppIcon name="menu" class="h-3 w-3 rtl:scale-x-[-1]" aria-hidden="true" />
              {{ t("customerLayout.navMenu") }}
            </RouterLink>
          </div>
        </div>
      </div>
    </header>

    <!-- Search -->
    <div class="relative">
      <AppIcon name="search" class="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
      <input
        v-model.trim="search"
        type="search"
        class="ui-input ps-9 pe-10"
        :aria-label="t('category.searchPlaceholder')"
        :placeholder="t('category.searchPlaceholder')"
        enterkeyhint="search"
      />
      <button
        v-if="search"
        class="ui-press ui-touch-target absolute end-2 top-1/2 -translate-y-1/2 rounded-full border border-slate-700/80 p-1 text-slate-300 hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
        :aria-label="t('common.clear')"
        @click="search = ''"
      >
        <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>

    <!-- Dish grid – loading skeletons -->
    <div v-if="menu.loading && !filteredDishes.length" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-label="Loading dishes">
      <div v-for="n in 6" :key="`loading-${n}`" class="ui-skeleton h-80 rounded-[1.8rem]"></div>
    </div>

    <!-- Dish grid – results -->
    <div v-else-if="filteredDishes.length" class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      <article
        v-for="(dish, dishIndex) in filteredDishes"
        :key="dish.slug"
        class="ui-surface-lift ui-reveal group relative ui-content-auto overflow-hidden rounded-[1.8rem] border bg-slate-950/82 shadow-[0_20px_50px_rgba(2,6,23,0.36)] transition-shadow duration-300"
        :class="dish.is_available === false
          ? 'border-slate-800/50 opacity-60'
          : cartQty(dish) > 0
            ? 'border-[var(--color-secondary)]/50 shadow-[0_20px_50px_rgba(245,158,11,0.12)]'
            : 'border-slate-800/80 hover:border-slate-700/60 hover:shadow-[0_28px_64px_rgba(2,6,23,0.52)]'"
        :style="{ '--ui-delay': `${Math.min(dishIndex, 9) * 28}ms` }"
        :aria-label="dish.name"
      >
        <!-- in-cart top accent -->
        <div
          v-if="cartQty(dish) > 0"
          aria-hidden="true"
          class="pointer-events-none absolute inset-x-0 top-0 z-10 h-[2px] rounded-t-[1.8rem]"
          style="background: linear-gradient(90deg, transparent, rgba(245,158,11,0.85), transparent)"
        />
        <!-- Image -->
        <RouterLink :to="{ name: 'dish', params: { category: props.slug, dish: dish.slug } }" class="block" aria-hidden="true" tabindex="-1">
          <div class="relative aspect-[4/3] overflow-hidden bg-slate-900">
            <DishImage
              :src="dish.image_url"
              :name="dish.name"
              :seed="dish.slug"
              img-class="h-full w-full object-cover transition duration-500 group-hover:scale-[1.05]"
              :loading="dishIndex < 2 ? 'eager' : 'lazy'"
              :fetchpriority="dishIndex < 1 ? 'high' : 'auto'"
            />
            <div aria-hidden="true" class="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-slate-950/15 to-transparent"></div>
            <!-- In-cart badge -->
            <div v-if="cartQty(dish) > 0" class="absolute start-3 top-3 z-10">
              <span
                class="flex items-center gap-1 rounded-full bg-[var(--color-secondary)] px-2.5 py-1 text-[11px] font-bold tabular-nums text-slate-950 shadow-md"
                role="status"
              >
                <AppIcon name="check" class="h-3 w-3 shrink-0" aria-hidden="true" />
                <span aria-hidden="true">{{ cartQty(dish) }}&times;</span>
                <span class="sr-only">{{ t('category.inCartBadge', { count: cartQty(dish) }) }}</span>
              </span>
            </div>
            <!-- Sold-out frosted overlay on image -->
            <div
              v-if="dish.is_available === false"
              class="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-slate-950/55 backdrop-blur-[2px]"
              aria-hidden="true"
            >
              <span class="rounded-full border border-slate-600/50 bg-slate-900/90 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-slate-300">
                {{ t('menu.soldOut') }}
              </span>
            </div>
            <!-- Price badge -->
            <div class="absolute end-3 top-3 z-10">
              <span class="rounded-full bg-slate-950/75 px-3 py-1 text-xs font-bold tabular-nums text-[var(--color-secondary)] shadow-md ring-1 ring-[var(--color-secondary)]/30 backdrop-blur-sm">
                {{ formatPrice(dish.price) }}
              </span>
            </div>
          </div>
        </RouterLink>

        <!-- Content -->
        <div class="flex flex-col gap-3 p-4">
          <div class="min-w-0 space-y-1">
            <h3 class="truncate text-base font-semibold leading-snug tracking-tight text-white" :title="dish.name">{{ dish.name }}</h3>
            <p class="line-clamp-2 text-sm leading-relaxed text-slate-400" :title="dish.description || undefined">{{ dish.description || '' }}</p>
          </div>

          <ul v-if="dish.tags?.length" class="flex flex-wrap gap-1 list-none p-0 m-0">
            <li
              v-for="tag in dish.tags"
              :key="tag"
            ><span class="rounded-full border border-slate-700/60 bg-slate-800/40 px-2 py-0.5 text-[10px] text-slate-400">{{ t(`dishPage.tag_${tag}`) }}</span></li>
          </ul>

          <ul v-if="dish.options?.length || dish.option_groups?.length" class="flex flex-wrap gap-1.5 list-none p-0 m-0">
            <li v-if="dish.options?.length"><span class="ui-data-strip tabular-nums text-[11px]">
              {{ t("dishPage.optionsCount", { count: dish.options.length }) }}
            </span></li>
            <li v-if="dish.option_groups?.length"><span class="ui-data-strip tabular-nums text-[11px]">
              {{ dish.option_groups.length }} {{ t("stepDishes.optionGroupsTitle") }}
            </span></li>
          </ul>

          <div class="mt-auto flex gap-2 pt-1">
            <span
              v-if="dish.is_available === false"
              class="flex flex-1 items-center justify-center rounded-xl border border-slate-700/40 bg-slate-800/40 py-2.5 text-xs font-semibold text-slate-500"
            >{{ t('menu.soldOut') }}</span>
            <button
              v-else-if="!quickAddDisabled"
              class="ui-btn-primary ui-press flex-1 justify-center gap-1.5 py-2.5 text-sm font-semibold"
              :aria-label="t('dishPage.add') + ' ' + dish.name"
              @click="addDishQuick(dish)"
            >
              <AppIcon name="plus" class="h-4 w-4 shrink-0" aria-hidden="true" />
              {{ t("dishPage.add") }}
            </button>
            <RouterLink
              :to="{ name: 'dish', params: { category: props.slug, dish: dish.slug } }"
              class="ui-btn-outline justify-center gap-1.5 py-2.5 text-sm"
              :class="quickAddDisabled ? 'flex-1' : ''"
              :aria-label="t('category.viewDish') + ' ' + dish.name"
            >
              <AppIcon name="eye" class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {{ t("category.viewDish") }}
            </RouterLink>
          </div>
        </div>
      </article>
    </div>

    <!-- Empty / no-results state -->
    <div v-else-if="!menu.loading" class="ui-empty-state space-y-4 py-6 text-center" role="status">
      <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-slate-700/80 bg-slate-900/70 text-slate-300 shadow-inner">
        <AppIcon name="search" class="h-6 w-6" aria-hidden="true" />
      </div>
      <div class="space-y-1">
        <p class="ui-kicker tracking-widest uppercase text-[10px]">{{ categoryName }}</p>
        <p class="text-lg font-semibold tracking-tight text-white">{{ t("category.noMatch") }}</p>
      </div>
      <div class="flex flex-wrap justify-center gap-2">
        <button class="ui-btn-outline justify-center gap-1.5" @click="search = ''">
          <AppIcon name="close" class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {{ t("common.clear") }}
        </button>
        <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline justify-center gap-1.5">
          <AppIcon name="menu" class="h-3.5 w-3.5 shrink-0 rtl:scale-x-[-1]" aria-hidden="true" />
          {{ t("customerLayout.navMenu") }}
        </RouterLink>
      </div>
    </div>

    <!-- Error banner -->
    <div v-if="menu.error" class="ui-reveal flex items-start gap-2.5 rounded-xl border border-red-500/30 bg-red-500/8 px-3.5 py-3" role="alert">
      <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
      <p class="flex-1 text-sm leading-relaxed text-red-300">{{ menu.error }}</p>
      <button
        class="ui-press ui-touch-target shrink-0 rounded-full border border-slate-700/70 px-3 py-1 text-xs text-slate-300 transition hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
        @click="menu.fetchCategories(true); menu.fetchDishesByCategory(props.slug, true)"
      >{{ t('common.retry') }}</button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import DishImage from "../components/DishImage.vue";
import { useI18n } from "../composables/useI18n";
import { withImageFallback } from "../lib/images";
import { trackEvent } from "../lib/analytics";
import { useCartStore } from "../stores/cart";
import { useMenuStore } from "../stores/menu";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const props = defineProps({ slug: String });
const router = useRouter();
const menu = useMenuStore();
const cart = useCartStore();
const tenant = useTenantStore();
const toast = useToastStore();
const { currentLocale, formatPrice, itemCountLabel, t } = useI18n();
const search = ref("");

const dishes = computed(() => menu.dishes[props.slug] || []);
const menuCategories = computed(() => (Array.isArray(menu.categories) ? menu.categories : []));
const currentCategory = computed(() => menuCategories.value.find((c) => c.slug === props.slug) || null);
const categoryName = computed(() => currentCategory.value?.name || props.slug);
const categoryDescription = computed(() => {
  const description = String(currentCategory.value?.description || "").trim();
  return description;
});

const isBrowseOnlyPlan = computed(() => tenant.isBrowseOnlyPlan === true);
const isRestaurantOpen = computed(() => tenant.resolvedMeta?.profile?.is_open !== false);
const quickAddDisabled = computed(() => isBrowseOnlyPlan.value || !isRestaurantOpen.value);

const filteredDishes = computed(() => {
  const term = search.value.toLowerCase();
  return dishes.value.filter((dish) => {
    if (!term) return true;
    const name = String(dish.name || "").toLowerCase();
    const description = String(dish.description || "").toLowerCase();
    const tagMatch = (dish.tags || []).some((tag) => tag.replace("_", " ").includes(term));
    return name.includes(term) || description.includes(term) || tagMatch;
  });
});

// How many of this dish are in the cart (across all option combos)
const cartQty = (dish) =>
  cart.items
    .filter((i) => i.slug === dish.slug)
    .reduce((sum, i) => sum + i.qty, 0);

const handleCategoryImageError = (event) => withImageFallback(event);

const addDishQuick = (dish) => {
  if (dish.is_available === false) return; // sold-out guard
  if (isBrowseOnlyPlan.value) {
    toast.show(t("dishPage.orderingDisabledForPlan"), "info");
    return;
  }
  if (!isRestaurantOpen.value) {
    toast.show(t("dishPage.restaurantCurrentlyClosed"), "error");
    return;
  }

  const hasRequiredGroups = dish.option_groups?.some((g) => g.min_select > 0) || false;
  if (hasRequiredGroups) {
    router.push({ name: "dish", params: { category: props.slug, dish: dish.slug } });
    return;
  }

  const requiredOptions = Array.isArray(dish.options)
    ? dish.options.filter((opt) => Boolean(opt.is_required))
    : [];
  const optionIds = requiredOptions
    .map((opt) => Number(opt.id))
    .filter((id) => Number.isInteger(id) && id > 0)
    .sort((a, b) => a - b);
  const optionSig = optionIds.join(",");
  const extras = requiredOptions.reduce((sum, opt) => sum + Number(opt.price_delta || 0), 0);
  const unitPrice = Number(dish.price || 0) + extras;
  const note = requiredOptions.length
    ? `${t("dishPage.options")}: ${requiredOptions.map((opt) => opt.name).join(", ")}`
    : "";

  cart.add({
    key: `${dish.slug}::${optionSig}`,
    slug: dish.slug,
    name: dish.name,
    price: Number(unitPrice),
    currency: dish.currency,
    qty: 1,
    note,
    option_ids: optionIds,
    option_labels: requiredOptions.map((opt) => opt.name),
  });

  toast.show(t("dishPage.addedToCart"), "success");
};

onMounted(() => {
  if (!menuCategories.value.length) menu.fetchCategories();
});

watch(
  () => currentLocale.value,
  () => {
    if (!props.slug) return;
    menu.fetchCategories(true);
    menu.fetchDishesByCategory(props.slug, true);
  }
);

watch(
  () => props.slug,
  (slug) => {
    if (!slug) return;
    search.value = "";
    menu.fetchDishesByCategory(slug);
    trackEvent("category_view", { source: "customer_category", category_slug: slug }, { onceKey: `category:${slug}` });
  },
  { immediate: true }
);
</script>
