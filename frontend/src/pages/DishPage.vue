<template>
  <div class="relative ui-safe-bottom" :class="dish ? 'pb-56 sm:pb-10' : 'pb-8'">

    <!-- ── Loading ─────────────────────────────────────────────── -->
    <div v-if="menu.loading" role="status" aria-live="polite" aria-label="Loading dish details">
      <div class="ui-skeleton" style="height:min(70vw,400px)"></div>
      <div class="mt-5 space-y-4 px-4">
        <div class="flex gap-2">
          <div class="ui-skeleton h-5 w-20 rounded-full"></div>
          <div class="ui-skeleton h-5 w-14 rounded-full"></div>
        </div>
        <div class="ui-skeleton h-8 w-4/5 rounded-xl"></div>
        <div class="ui-skeleton h-5 w-2/3 rounded-xl"></div>
        <div class="ui-skeleton h-24 rounded-xl"></div>
        <div class="ui-skeleton h-36 rounded-xl"></div>
      </div>
    </div>

    <!-- ── Not found ────────────────────────────────────────────── -->
    <div v-else-if="!dish" class="ui-empty-state mx-4 mt-8 space-y-3 rounded-2xl" role="alert">
      <p class="ui-kicker">{{ categoryName }}</p>
      <p class="text-lg font-bold text-slate-100">{{ t('dishPage.notFoundTitle') }}</p>
      <p class="text-sm leading-relaxed text-slate-400">{{ t('dishPage.notFoundText') }}</p>
      <RouterLink :to="{ name: 'menu' }" class="ui-btn-primary justify-center">
        <AppIcon name="menu" class="h-3.5 w-3.5" />
        {{ t('customerLayout.navMenu') }}
      </RouterLink>
    </div>

    <!-- ── Main ─────────────────────────────────────────────────── -->
    <template v-else>

      <!-- Full-bleed hero image -->
      <div
        data-theme-dark
        class="relative overflow-hidden bg-slate-950"
        style="height:min(70vw,400px)"
      >
        <DishImage
          :src="dish.image_url"
          :name="dish.name"
          :seed="dish.slug"
          img-class="h-full w-full object-cover transition-transform duration-500"
          :class="dish.image_url ? 'cursor-zoom-in' : ''"
          loading="eager"
          fetchpriority="high"
          @click="dish.image_url && (lightboxOpen = true)"
        />
        <!-- gradient from top so controls are always readable -->
        <div class="pointer-events-none absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-black/65 to-transparent" />
        <!-- gradient at bottom for depth -->
        <div class="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-black/40 to-transparent" />

        <!-- Back -->
        <button
          class="ui-touch-target absolute start-3 top-3 flex h-10 w-10 items-center justify-center rounded-full border border-white/25 bg-black/50 text-white backdrop-blur-md transition hover:bg-black/70 active:scale-95"
          :aria-label="t('common.goBack')"
          @click="router.back()"
        >
          <AppIcon name="arrowLeft" class="h-4 w-4 rtl:scale-x-[-1]" />
        </button>

        <!-- Cart badge -->
        <RouterLink
          v-if="cart.count"
          :to="{ name: 'cart' }"
          :aria-label="t('dishPage.cartWithCount', { count: cart.count })"
          class="absolute end-3 top-3 flex h-10 items-center gap-1.5 rounded-full border border-white/25 bg-black/50 px-3.5 text-xs font-bold text-white backdrop-blur-md transition hover:bg-black/70"
        >
          <AppIcon name="cart" class="h-3.5 w-3.5" />
          {{ cart.count }}
        </RouterLink>

        <!-- Zoom hint — only shown when a real image exists -->
        <div
          v-if="dish.image_url"
          class="pointer-events-none absolute bottom-3 end-3 flex h-8 w-8 items-center justify-center rounded-full bg-black/45 text-white/70 backdrop-blur-sm"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"/>
            <path d="M8 6a.75.75 0 01.75.75V7.5h.75a.75.75 0 010 1.5H8.75v.75a.75.75 0 01-1.5 0V9H6.5a.75.75 0 010-1.5h.75V6.75A.75.75 0 018 6z"/>
          </svg>
        </div>
      </div>

      <!-- ── Content ──────────────────────────────────────────── -->
      <div class="px-4 pt-5 space-y-6 ui-reveal">

        <!-- Chips / status badges -->
        <div class="flex flex-wrap gap-2">
          <span class="ui-chip-strong text-[11px] tracking-wide uppercase">{{ categoryName }}</span>
          <span v-for="tag in dish.tags" :key="tag" class="ui-chip text-[11px]">{{ t(`dishPage.tag_${tag}`) }}</span>
          <span v-if="isBrowseOnlyPlan" class="ui-chip bg-sky-500/20 text-sky-200 text-[11px]">{{ t('dishPage.menuOnly') }}</span>
          <span v-if="dish.is_available === false" class="ui-chip border-red-500/40 bg-red-500/10 text-red-300 text-[11px]">{{ t('menu.soldOut') }}</span>
          <span v-if="dish.is_schedule_available === false" class="ui-chip border-slate-600/50 bg-slate-800/60 text-slate-400 text-[11px]">{{ t('menu.notAvailableNow') }}</span>
        </div>

        <!-- Title + price -->
        <div class="flex items-start gap-4">
          <h1 class="ui-display flex-1 text-2xl font-extrabold leading-snug tracking-tight text-slate-50 sm:text-3xl">{{ dish.name }}</h1>
          <span class="mt-0.5 shrink-0 rounded-full bg-[var(--color-secondary)] px-4 py-1.5 text-sm font-extrabold tabular-nums text-slate-900 shadow-lg shadow-[var(--color-secondary)]/30">
            {{ formatPrice(dish.price) }}
          </span>
        </div>

        <!-- Description -->
        <p v-if="dish.description" class="text-[15px] leading-relaxed text-slate-300/90">{{ dish.description }}</p>

        <!-- Option groups -->
        <div v-if="dish.option_groups?.length" class="ui-section-band space-y-5">
          <fieldset v-for="group in dish.option_groups" :key="group.id" class="space-y-3 border-0 m-0 p-0">
            <div class="flex items-center justify-between gap-2">
              <legend class="float-left text-sm font-bold text-slate-200 tracking-tight">
                {{ group.name }}
                <span v-if="group.min_select > 0" class="ms-1.5 rounded-full bg-amber-400/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300 ring-1 ring-amber-400/20">{{ t('dishPage.required') }}</span>
              </legend>
              <span class="ui-data-strip text-[11px] shrink-0">{{ group.max_select > 1 ? t('dishPage.pickUpTo', { n: group.max_select }) : t('dishPage.pickOne') }}</span>
            </div>
            <ul class="grid gap-2 text-sm sm:grid-cols-2 clear-both">
              <li
                v-for="opt in group.options" :key="opt.id"
                class="ui-selection-card"
                :data-active="groupIsSelected(group.id, opt.id)"
                :data-warning="group.min_select > 0 && groupSelectedCount(group.id) < group.min_select"
              >
                <label class="flex w-full cursor-pointer items-center gap-3 py-0.5">
                  <input
                    v-if="group.max_select === 1"
                    type="radio"
                    :name="`group-${group.id}`"
                    :value="opt.id"
                    :checked="groupIsSelected(group.id, opt.id)"
                    class="h-4 w-4 shrink-0 accent-[var(--color-secondary)]"
                    @change="toggleInGroup(group.id, opt.id, group.max_select, group.min_select)"
                  />
                  <input
                    v-else
                    type="checkbox"
                    :value="opt.id"
                    :checked="groupIsSelected(group.id, opt.id)"
                    class="h-4 w-4 shrink-0 rounded accent-[var(--color-secondary)]"
                    @change="toggleInGroup(group.id, opt.id, group.max_select, group.min_select)"
                  />
                  <p class="min-w-0 flex-1 font-medium text-slate-100 leading-snug">{{ opt.name }}</p>
                  <span v-if="Number(opt.price_delta) > 0" class="shrink-0 text-xs font-bold tabular-nums text-[var(--color-secondary)]">
                    +{{ formatPrice(opt.price_delta) }}
                  </span>
                </label>
              </li>
            </ul>
          </fieldset>
          <p v-if="hasGroupMissing" role="alert" class="flex items-center gap-1.5 text-xs font-medium text-amber-300">
            <AppIcon name="info" class="h-3 w-3 shrink-0" aria-hidden="true" />
            {{ t('dishPage.selectRequiredOptions') }}
          </p>
        </div>

        <!-- Flat options (legacy) -->
        <fieldset v-if="dish.options?.length" class="ui-section-band space-y-3 border-0 m-0 p-0">
          <legend class="text-sm font-bold text-slate-200 tracking-tight">{{ t('dishPage.options') }}</legend>
          <ul class="grid gap-2 text-sm sm:grid-cols-2">
            <li
              v-for="opt in dish.options" :key="opt.id"
              class="ui-selection-card"
              :data-active="isOptionSelected(opt.id)"
              :data-warning="opt.is_required && !isOptionSelected(opt.id)"
            >
              <label class="flex w-full cursor-pointer items-center gap-3 py-0.5">
                <input
                  v-model="selectedOptionIds"
                  type="checkbox"
                  :value="opt.id"
                  class="h-4 w-4 shrink-0 rounded accent-[var(--color-secondary)]"
                />
                <div class="min-w-0 flex-1">
                  <p class="font-medium text-slate-100 leading-snug">{{ opt.name }}</p>
                  <p v-if="opt.is_required" class="text-[10px] text-amber-300 mt-0.5">{{ t('dishPage.required') }}</p>
                </div>
                <span class="shrink-0 text-xs font-bold tabular-nums text-[var(--color-secondary)]">+{{ formatPrice(opt.price_delta) }}</span>
              </label>
            </li>
          </ul>
          <p v-if="hasUngroupedRequiredMissing" role="alert" class="flex items-center gap-1.5 text-xs font-medium text-amber-300">
            <AppIcon name="info" class="h-3 w-3 shrink-0" aria-hidden="true" />
            {{ t('dishPage.selectRequiredOptions') }}
          </p>
        </fieldset>

        <!-- Desktop add-to-cart (sm+) -->
        <div class="hidden sm:block rounded-2xl border border-slate-700/50 bg-slate-900/60 p-5 space-y-4 shadow-lg shadow-black/20">
          <!-- Selected options summary -->
          <div v-if="selectedOptionObjects.length" class="flex flex-wrap gap-1.5">
            <span
              v-for="opt in selectedOptionObjects" :key="opt.id"
              class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-800/70 px-2.5 py-1 text-[11px] text-slate-300"
            >
              {{ opt.name }}
              <span v-if="Number(opt.price_delta) > 0" class="font-semibold text-[var(--color-secondary)]">+{{ formatPrice(opt.price_delta) }}</span>
            </span>
          </div>
          <!-- Price + controls row -->
          <div class="flex items-center gap-3">
            <span class="ui-qty-control inline-flex items-center rounded-full border p-1">
              <button class="ui-press h-9 w-9 rounded-full text-base font-bold text-slate-200" :aria-label="t('dishPage.decreaseQuantity')" @click="decrementQty">−</button>
              <input v-model.number="qty" type="number" min="1" max="99" aria-valuemin="1" aria-valuemax="99" class="w-10 border-0 bg-transparent text-center text-sm font-semibold text-slate-100 focus:outline-none" :aria-label="t('dishPage.qty')" />
              <button class="ui-press h-9 w-9 rounded-full text-base font-bold text-slate-200" :aria-label="t('dishPage.increaseQuantity')" @click="incrementQty">+</button>
            </span>
            <div class="min-w-0">
              <p class="text-xl font-extrabold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(totalWithOptions) }}</p>
              <p v-if="qty > 1" class="text-[11px] text-slate-500 tabular-nums">{{ qty }} × {{ formatPrice(unitPriceWithOptions) }}</p>
            </div>
            <button
              class="ui-btn-primary ms-auto px-7 py-3 text-sm font-bold tracking-tight"
              :disabled="orderingDisabled"
              :class="orderingDisabled ? 'cursor-not-allowed opacity-60' : ''"
              @click="addToCart"
            >
              <AppIcon v-if="!isBrowseOnlyPlan" name="plus" class="h-4 w-4" />
              {{ isBrowseOnlyPlan ? t('dishPage.browseOnlyPlan') : cart.canCheckout || cart.canWhatsapp ? t('dishPage.addToCart') : t('dishPage.addContactToOrder') }}
            </button>
            <button
              class="ui-share-btn shrink-0 rounded-xl border border-slate-700/60 bg-slate-800/50 p-2.5 text-slate-400 transition-colors hover:text-slate-200 hover:bg-slate-700/50"
              :aria-label="t('dishPage.shareDish')"
              @click="shareDish"
            >
              <AppIcon name="share" class="h-4 w-4" />
            </button>
          </div>
          <p v-if="hasRequiredMissing" role="alert" class="flex items-center gap-1.5 text-xs font-medium text-amber-300">
            <AppIcon name="info" class="h-3 w-3 shrink-0" aria-hidden="true" />
            {{ t('dishPage.selectRequiredOptions') }}
          </p>
          <p v-if="!isRestaurantOpen" class="text-xs text-amber-300">{{ t('dishPage.restaurantClosedNotice') }}</p>
        </div>

        <!-- Similar dishes -->
        <div v-if="similarDishes.length" :ref="similarVis.target" class="space-y-3 pb-4">
          <p class="ui-kicker tracking-widest">{{ t('dishPage.similarDishes') }}</p>
          <div class="grid gap-3 sm:grid-cols-2">
            <template v-if="showSimilarSkeletons">
              <div v-for="n in 2" :key="'sk-' + n" class="h-32 ui-skeleton rounded-2xl"></div>
            </template>
            <RouterLink
              v-for="(item, index) in visibleSimilarDishes" :key="item.slug"
              :to="{ name: 'dish', params: { category: props.category, dish: item.slug } }"
              class="group ui-panel ui-surface-lift ui-reveal overflow-hidden"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
              :aria-label="item.name"
            >
              <div class="relative h-28 overflow-hidden rounded-t-2xl">
                <DishImage :src="item.image_url" :name="item.name" :seed="item.slug" img-class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.05]" loading="lazy" />
              </div>
              <div class="flex items-start justify-between gap-2 p-3 pb-3.5">
                <p class="line-clamp-2 text-sm font-semibold leading-snug text-slate-100">{{ item.name }}</p>
                <p class="shrink-0 text-sm font-extrabold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(item.price) }}</p>
              </div>
            </RouterLink>
          </div>
        </div>

      </div>
    </template>

    <!-- ══ Lightbox ══ -->
    <Teleport to="body">
      <Transition name="lightbox">
        <div
          v-if="lightboxOpen && dish"
          ref="lightboxDialogRef"
          role="dialog"
          aria-modal="true"
          aria-labelledby="dish-lightbox-dialog-title"
          class="fixed inset-0 z-[200] flex cursor-zoom-out items-center justify-center bg-black/96 backdrop-blur-sm"
          @click="lightboxOpen = false"
        >
          <h2 id="dish-lightbox-dialog-title" class="sr-only">{{ dish.name }}</h2>
          <img
            :src="dish.image_url"
            :alt="dish.name"
            loading="lazy"
            decoding="async"
            class="max-h-[95vh] max-w-[95vw] rounded-xl object-contain shadow-2xl shadow-black/60"
            @click.stop
          />
          <button
            class="absolute end-4 top-4 flex h-10 w-10 items-center justify-center rounded-full border border-white/20 bg-black/60 text-white transition-colors hover:bg-black/80"
            :aria-label="t('common.close')"
            @click="lightboxOpen = false"
            @keydown.esc="lightboxOpen = false"
          >
            <AppIcon name="close" class="h-5 w-5" />
          </button>
        </div>
      </Transition>
    </Teleport>

    <!-- ══ Mobile sticky bottom bar ══ -->
    <div
      v-if="dish"
      class="ui-dish-bar fixed bottom-[5.15rem] start-3 end-3 z-20 overflow-hidden rounded-2xl px-4 py-3.5 backdrop-blur-xl sm:hidden"
      :class="hasRequiredMissing ? 'ring-1 ring-amber-500/50' : ''"
    >
      <!-- top shimmer line — amber when options missing, secondary otherwise -->
      <div
        class="pointer-events-none absolute inset-x-0 top-0 h-px"
        :style="hasRequiredMissing
          ? 'background: linear-gradient(90deg, transparent, rgba(245,158,11,0.7), transparent)'
          : 'background: linear-gradient(90deg, transparent, rgba(var(--color-secondary-rgb,245,158,11),0.5), transparent)'"
      />

      <!-- Row 1: dish name + price -->
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="truncate text-sm font-bold text-slate-100 leading-snug">{{ dish.name }}</p>
          <!-- selected options summary chips -->
          <div v-if="selectedOptionObjects.length" class="mt-1.5 flex flex-wrap gap-1">
            <span
              v-for="opt in selectedOptionObjects"
              :key="opt.id"
              class="inline-flex items-center gap-0.5 rounded-full border border-slate-700/60 bg-slate-800/70 px-2 py-0.5 text-[10px] text-slate-300"
            >
              {{ opt.name }}<span v-if="Number(opt.price_delta) > 0" class="font-semibold text-[var(--color-secondary)]">&nbsp;+{{ formatPrice(opt.price_delta) }}</span>
            </span>
          </div>
          <!-- required-options warning -->
          <p v-if="hasRequiredMissing" role="alert" class="mt-1 flex items-center gap-1 text-[11px] font-medium text-amber-400">
            <AppIcon name="info" class="h-3 w-3 shrink-0" aria-hidden="true" />
            {{ t('dishPage.selectRequiredOptions') }}
          </p>
        </div>
        <!-- price block -->
        <div class="shrink-0 text-right">
          <p class="text-base font-extrabold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(totalWithOptions) }}</p>
          <p v-if="qty > 1" class="text-[11px] tabular-nums text-slate-500">{{ qty }} × {{ formatPrice(unitPriceWithOptions) }}</p>
        </div>
      </div>

      <!-- Row 2: qty stepper + share + add button -->
      <div class="mt-3 flex items-center gap-2">
        <span class="ui-qty-control inline-flex items-center rounded-full border p-1">
          <button class="ui-press h-8 w-8 rounded-full text-base font-bold text-slate-200" :aria-label="t('dishPage.decreaseQuantity')" @click="decrementQty">−</button>
          <input v-model.number="qty" type="number" min="1" max="99" aria-valuemin="1" aria-valuemax="99" class="w-10 border-0 bg-transparent text-center text-sm font-semibold text-slate-100 focus:outline-none" :aria-label="t('dishPage.qty')" />
          <button class="ui-press h-8 w-8 rounded-full text-base font-bold text-slate-200" :aria-label="t('dishPage.increaseQuantity')" @click="incrementQty">+</button>
        </span>
        <button
          class="ui-share-btn shrink-0 rounded-xl border border-slate-700/60 bg-slate-800/50 p-2.5 text-slate-400 transition-colors hover:text-slate-200"
          :aria-label="t('dishPage.shareDish')"
          @click="shareDish"
        >
          <AppIcon name="share" class="h-4 w-4" />
        </button>
        <button
          class="ui-btn-primary ms-auto flex-1 py-3 text-sm font-bold tracking-tight"
          :disabled="orderingDisabled"
          :class="orderingDisabled ? 'cursor-not-allowed opacity-60' : ''"
          @click="addToCart"
        >
          <AppIcon name="plus" class="h-4 w-4" />
          {{ isBrowseOnlyPlan ? t('dishPage.viewOnly') : t('dishPage.add') }}
        </button>
      </div>
    </div>

  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch, watchEffect } from 'vue';
import { useRouter } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import DishImage from '../components/DishImage.vue';
import { useI18n } from '../composables/useI18n';
import { useFocusTrap } from '../composables/useFocusTrap';
import { useMenuStore } from '../stores/menu';
import { useCartStore } from '../stores/cart';
import { useToastStore } from '../stores/toast';
import { useTenantStore } from '../stores/tenant';
import { useVisibility } from '../composables/useVisibility';
import { trackEvent } from '../lib/analytics';

const props = defineProps({ category: String, dish: String });

const router = useRouter();
const menu   = useMenuStore();
const cart   = useCartStore();
const tenant = useTenantStore();
const toast  = useToastStore();
const { currentLocale, formatPrice, t } = useI18n();
const similarVis = useVisibility();

const qty               = ref(1);
const selectedOptionIds = ref([]);
const groupSelections   = ref({});
const lightboxOpen      = ref(false);
const lightboxDialogRef = ref(null);
useFocusTrap(lightboxDialogRef, lightboxOpen);

const meta          = computed(() => tenant.resolvedMeta || null);
const dishes        = computed(() => menu.dishes[props.category] || []);
const dish          = computed(() => dishes.value.find((d) => d.slug === props.dish));

const menuCategories = computed(() => Array.isArray(menu.categories) ? menu.categories : []);
const categoryName   = computed(() => menuCategories.value.find((c) => c.slug === props.category)?.name || props.category);

const similarDishes = computed(() =>
  dishes.value.filter((d) => d.slug !== props.dish).sort((a, b) => (a.price || 0) - (b.price || 0)).slice(0, 4)
);
const showSimilarSkeletons  = computed(() => menu.loading && !similarVis.isVisible.value);
const visibleSimilarDishes  = computed(() => similarVis.isVisible.value ? similarDishes.value : []);

const isBrowseOnlyPlan  = computed(() => tenant.isBrowseOnlyPlan === true);
const isRestaurantOpen  = computed(() => meta.value?.profile?.is_open !== false);

// ── Option helpers ────────────────────────────────────────────────────────────
const groupIsSelected = (groupId, optionId) => {
  const sel = groupSelections.value[groupId];
  return Array.isArray(sel) ? sel.includes(optionId) : sel === optionId;
};

const toggleInGroup = (groupId, optionId, maxSelect, minSelect = 0) => {
  const current = Array.isArray(groupSelections.value[groupId])
    ? [...groupSelections.value[groupId]]
    : groupSelections.value[groupId] != null ? [groupSelections.value[groupId]] : [];
  const idx = current.indexOf(optionId);
  if (idx >= 0) {
    if (current.length > Math.max(minSelect, 0)) current.splice(idx, 1);
  } else {
    if (current.length >= maxSelect) current.shift();
    current.push(optionId);
  }
  groupSelections.value = { ...groupSelections.value, [groupId]: current };
};

const allSelectedOptionIds = computed(() => {
  const grouped = Object.values(groupSelections.value)
    .flatMap((sel) => (Array.isArray(sel) ? sel : sel != null ? [sel] : []))
    .filter((id) => id != null);
  return [...selectedOptionIds.value, ...grouped];
});

const allSelectedOptionIdsSorted = computed(() =>
  [...allSelectedOptionIds.value].map((x) => Number(x)).filter((x) => Number.isInteger(x) && x > 0).sort((a, b) => a - b)
);

const selectedOptionObjects = computed(() => {
  if (!dish.value) return [];
  const allOptions = [...(dish.value.options || []), ...(dish.value.option_groups || []).flatMap((g) => g.options || [])];
  const byId = new Map(allOptions.map((o) => [o.id, o]));
  return allSelectedOptionIdsSorted.value.map((id) => byId.get(id)).filter(Boolean);
});

const selectedOptionNote = computed(() => {
  if (!selectedOptionObjects.value.length || !dish.value) return '';
  const bits = selectedOptionObjects.value.map((opt) => `${opt.name} (+${formatPrice(opt.price_delta)})`);
  return `${t('dishPage.options')}: ${bits.join(', ')}`;
});

const unitOptionTotal      = computed(() => selectedOptionObjects.value.reduce((sum, opt) => sum + Number(opt.price_delta || 0), 0));
const unitPriceWithOptions = computed(() => (Number(dish.value?.price) || 0) + unitOptionTotal.value);
const totalWithOptions     = computed(() => unitPriceWithOptions.value * (qty.value || 1));

const groupSelectedCount = (groupId) => {
  const sel = groupSelections.value[groupId];
  return Array.isArray(sel) ? sel.length : sel != null ? 1 : 0;
};

const hasUngroupedRequiredMissing = computed(() =>
  dish.value?.options?.some((opt) => opt.is_required && !selectedOptionIds.value.includes(opt.id)) || false
);
const hasGroupMissing = computed(() =>
  dish.value?.option_groups?.some((g) => g.min_select > 0 && groupSelectedCount(g.id) < g.min_select) || false
);
const hasRequiredMissing  = computed(() => hasUngroupedRequiredMissing.value || hasGroupMissing.value);
const isDishSoldOut       = computed(() => dish.value?.is_available === false);
const isDishScheduleUnavailable = computed(() => dish.value?.is_schedule_available === false);
const orderingDisabled    = computed(() => hasRequiredMissing.value || !isRestaurantOpen.value || isBrowseOnlyPlan.value || isDishSoldOut.value || isDishScheduleUnavailable.value);
const isOptionSelected    = (optionId) => selectedOptionIds.value.includes(optionId);

// ── Qty ───────────────────────────────────────────────────────────────────────
const normalizeQty  = (v) => { const p = Number(v); return !Number.isFinite(p) ? 1 : Math.min(99, Math.max(1, Math.round(p))); };
const incrementQty  = () => { qty.value = normalizeQty((qty.value || 1) + 1); };
const decrementQty  = () => { qty.value = normalizeQty((qty.value || 1) - 1); };

// ── Cart ──────────────────────────────────────────────────────────────────────
const addToCart = () => {
  if (!isRestaurantOpen.value)        { toast.show(t('dishPage.restaurantCurrentlyClosed'), 'error'); return; }
  if (isDishSoldOut.value)            { toast.show(t('menu.soldOutToast'), 'error'); return; }
  if (isDishScheduleUnavailable.value){ toast.show(t('menu.notAvailableNow'), 'error'); return; }
  if (isBrowseOnlyPlan.value)         { toast.show(t('dishPage.orderingDisabledForPlan'), 'info'); return; }
  if (!dish.value) return;
  if (hasRequiredMissing.value)       { toast.show(t('dishPage.selectRequiredOptionsFirst'), 'error'); return; }
  const quantity = qty.value > 0 ? qty.value : 1;
  const optionSig = allSelectedOptionIdsSorted.value.join(',');
  cart.add({
    key: `${dish.value.slug}::${optionSig}`,
    slug: dish.value.slug,
    name: dish.value.name,
    price: Number(unitPriceWithOptions.value),
    currency: dish.value.currency,
    qty: quantity,
    note: selectedOptionNote.value,
    option_ids: allSelectedOptionIdsSorted.value,
    option_labels: selectedOptionObjects.value.map((opt) => opt.name),
  });
  toast.show(t('dishPage.addedToCart'), 'success');
};

// ── Share ─────────────────────────────────────────────────────────────────────
const shareDish = async () => {
  if (!dish.value) return;
  const url = window.location.href;
  const title = dish.value.name || '';
  const text = dish.value.description ? dish.value.description.slice(0, 100) : title;
  if (typeof navigator.share === 'function') {
    try { await navigator.share({ title, text, url }); return; } catch { /* best-effort: ignore failures */ }
  }
  try { await navigator.clipboard.writeText(url); toast.show(t('dishPage.shareDishCopied'), 'success'); }
  catch { toast.show(t('dishPage.shareDishFailed'), 'error'); }
};

// ── Watches ───────────────────────────────────────────────────────────────────
watch(() => dish.value?.id, () => { qty.value = 1; selectedOptionIds.value = []; groupSelections.value = {}; });

watch(() => dish.value?.slug, (slug) => {
  if (!slug) return;
  trackEvent('dish_view', { source: 'customer_dish', category_slug: props.category, dish_slug: slug }, { onceKey: `dish:${slug}` });
}, { immediate: true });

watch(() => props.category, (slug) => {
  if (slug) { if (!menuCategories.value.length) menu.fetchCategories(); menu.fetchDishesByCategory(slug); }
}, { flush: 'post' });

watch(() => currentLocale.value, () => {
  if (!props.category) return;
  menu.fetchCategories(true);
  menu.fetchDishesByCategory(props.category, true);
});

onMounted(() => {
  if (!tenant.meta) tenant.fetchMeta();
  if (!menuCategories.value.length) menu.fetchCategories();
  if (!menu.dishes[props.category]) menu.fetchDishesByCategory(props.category);
});

watchEffect(() => {
  qty.value = normalizeQty(qty.value);
  if (dish.value?.options?.length) {
    dish.value.options.forEach((opt) => {
      if (opt.is_required && !selectedOptionIds.value.includes(opt.id)) selectedOptionIds.value.push(opt.id);
    });
  }
  if (dish.value?.option_groups?.length) {
    dish.value.option_groups.forEach((group) => {
      if (group.min_select > 0 && group.options?.length && groupSelectedCount(group.id) === 0) {
        groupSelections.value = { ...groupSelections.value, [group.id]: [group.options[0].id] };
      }
    });
  }
});
</script>

<style scoped>
.lightbox-enter-active { transition: opacity 200ms ease; }
.lightbox-leave-active { transition: opacity 150ms ease; }
.lightbox-enter-from,
.lightbox-leave-to     { opacity: 0; }
</style>
