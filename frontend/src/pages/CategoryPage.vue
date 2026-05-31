<template>
  <div class="space-y-4 px-3 py-3 pb-24 sm:space-y-5 sm:px-4 sm:py-4 ui-safe-bottom">
    <!-- Category hero -->
    <header class="ui-hero-stage ui-reveal overflow-hidden border border-slate-800/80 bg-slate-950/84 p-0">
      <div class="relative min-h-[11rem] overflow-hidden rounded-[1.35rem] bg-slate-950/90 sm:min-h-[13rem]">
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
        <div class="absolute inset-0 bg-gradient-to-t from-slate-950/95 via-slate-950/50 to-slate-950/15"></div>

        <div class="relative flex h-full flex-col justify-end space-y-2 p-4 md:p-5">
          <div class="space-y-1">
            <p class="ui-kicker">{{ t("category.kicker") }}</p>
            <h1 class="ui-display text-2xl font-semibold capitalize text-white md:text-3xl">{{ categoryName }}</h1>
            <p v-if="categoryDescription" class="max-w-2xl text-sm text-slate-300">{{ categoryDescription }}</p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <span class="ui-chip text-[11px]">{{ itemCountLabel(filteredDishes.length) }}</span>
            <RouterLink :to="{ name: 'menu' }" class="ui-chip text-[11px] hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)]">
              <AppIcon name="menu" class="h-3 w-3" />
              {{ t("customerLayout.navMenu") }}
            </RouterLink>
          </div>
        </div>
      </div>
    </header>

    <!-- Search -->
    <div class="relative">
      <input v-model.trim="search" type="search" class="ui-input pr-10" :aria-label="t('category.searchPlaceholder')" :placeholder="t('category.searchPlaceholder')" enterkeyhint="search" />
      <button
        v-if="search"
        class="absolute right-2 top-1/2 -translate-y-1/2 rounded-full border border-slate-700/80 p-1 text-slate-300 hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)]"
        @click="search = ''"
      >
        <span class="sr-only">{{ t("common.clear") }}</span>
        <AppIcon name="close" class="h-3.5 w-3.5" />
      </button>
    </div>

    <!-- Dish grid -->
    <div v-if="menu.loading && !filteredDishes.length" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="n in 6" :key="`loading-${n}`" class="ui-skeleton h-80 rounded-[1.8rem]"></div>
    </div>

    <div v-else-if="filteredDishes.length" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <article
        v-for="(dish, dishIndex) in filteredDishes"
        :key="dish.slug"
        class="group relative ui-content-auto overflow-hidden rounded-[1.8rem] border bg-slate-950/82 shadow-[0_20px_50px_rgba(2,6,23,0.36)] transition-all duration-300"
        :class="cartQty(dish) > 0
          ? 'border-[var(--color-secondary)]/45 shadow-[0_20px_50px_rgba(245,158,11,0.10)]'
          : 'border-slate-800/80 hover:border-slate-700/80 hover:shadow-[0_28px_64px_rgba(2,6,23,0.48)]'"
      >
        <!-- in-cart top accent -->
        <div
          v-if="cartQty(dish) > 0"
          class="pointer-events-none absolute inset-x-0 top-0 h-[2px] rounded-t-[1.8rem]"
          style="background: linear-gradient(90deg, transparent, rgba(245,158,11,0.7), transparent)"
        />
        <!-- Image -->
        <RouterLink :to="{ name: 'dish', params: { category: props.slug, dish: dish.slug } }" class="block">
          <div class="relative aspect-[4/3] overflow-hidden bg-slate-900">
            <img
              :src="dish.image_url || placeholder"
              :alt="dish.name"
              class="h-full w-full object-cover transition duration-500 group-hover:scale-[1.04]"
              :loading="dishIndex < 2 ? 'eager' : 'lazy'"
              :fetchpriority="dishIndex < 1 ? 'high' : 'auto'"
              decoding="async"
              @error="handleDishImageError"
            />
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-slate-950/15 to-transparent"></div>
            <!-- In-cart badge -->
            <div v-if="cartQty(dish) > 0" class="absolute left-3 top-3">
              <span class="flex items-center gap-1 rounded-full bg-[var(--color-secondary)] px-2.5 py-0.5 text-[11px] font-bold text-slate-950 shadow-lg">
                ✓ {{ cartQty(dish) }}×
              </span>
            </div>
            <!-- Price badge -->
            <div class="absolute right-3 top-3">
              <span class="rounded-full bg-[var(--color-secondary)] px-3 py-1 text-xs font-bold text-slate-950 shadow-lg">
                {{ formatPrice(dish.price) }}
              </span>
            </div>
          </div>
        </RouterLink>

        <!-- Content -->
        <div class="space-y-3 p-4">
          <div class="space-y-1">
            <h3 class="text-base font-semibold leading-snug text-white">{{ dish.name }}</h3>
            <p class="line-clamp-2 text-sm text-slate-400">{{ dish.description || '' }}</p>
          </div>

          <div v-if="dish.tags?.length" class="flex flex-wrap gap-1">
            <span
              v-for="tag in dish.tags"
              :key="tag"
              class="rounded-full border border-slate-700/60 px-2 py-0.5 text-[10px] text-slate-400"
            >{{ t(`dishPage.tag_${tag}`) }}</span>
          </div>

          <div v-if="dish.options?.length || dish.option_groups?.length" class="flex flex-wrap gap-1.5">
            <span v-if="dish.options?.length" class="ui-data-strip text-[11px]">
              {{ t("dishPage.optionsCount", { count: dish.options.length }) }}
            </span>
            <span v-if="dish.option_groups?.length" class="ui-data-strip text-[11px]">
              {{ dish.option_groups.length }} {{ t("stepDishes.optionGroupsTitle") }}
            </span>
          </div>

          <div class="flex gap-2">
            <button
              v-if="!quickAddDisabled"
              class="ui-btn-primary flex-1 justify-center gap-1.5 py-2 text-sm"
              @click="addDishQuick(dish)"
            >
              <AppIcon name="plus" class="h-4 w-4" />
              {{ t("dishPage.add") }}
            </button>
            <RouterLink
              :to="{ name: 'dish', params: { category: props.slug, dish: dish.slug } }"
              class="ui-btn-outline justify-center gap-1.5 py-2 text-sm"
              :class="quickAddDisabled ? 'flex-1' : ''"
            >
              <AppIcon name="eye" class="h-3.5 w-3.5" />
              {{ t("category.viewDish") }}
            </RouterLink>
          </div>
        </div>
      </article>
    </div>

    <div v-else-if="!menu.loading" class="ui-empty-state space-y-3 text-center">
      <div class="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl border border-slate-700/80 bg-slate-950/70 text-slate-200">
        <AppIcon name="search" class="h-5 w-5" />
      </div>
      <div class="space-y-1">
        <p class="ui-kicker">{{ categoryName }}</p>
        <p class="text-lg font-semibold text-white">{{ t("category.noMatch") }}</p>
      </div>
      <div class="flex flex-wrap justify-center gap-2">
        <button class="ui-btn-outline justify-center" @click="search = ''">
          <AppIcon name="close" class="h-3.5 w-3.5" />
          {{ t("common.clear") }}
        </button>
        <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline justify-center">
          <AppIcon name="menu" class="h-3.5 w-3.5" />
          {{ t("customerLayout.navMenu") }}
        </RouterLink>
      </div>
    </div>

    <div v-if="menu.error" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
      <p class="flex-1 text-sm text-red-300">{{ menu.error }}</p>
      <button class="shrink-0 text-xs text-slate-400 underline hover:text-slate-200" @click="menu.fetchCategories(true); menu.fetchDishesByCategory(props.slug, true)">{{ t('common.retry') }}</button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
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
const { currentLocale, formatCurrency, formatPrice, itemCountLabel, t } = useI18n();
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

const placeholder = "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=600&q=80";
const handleCategoryImageError = (event) => withImageFallback(event);
const handleDishImageError = (event) => withImageFallback(event, placeholder);

const addDishQuick = (dish) => {
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
