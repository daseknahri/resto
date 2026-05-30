<template>
  <div class="relative ui-safe-bottom" :class="dish ? 'pb-56 sm:pb-10' : 'pb-8'">

    <!-- ── Loading ─────────────────────────────────────────────── -->
    <div v-if="menu.loading" role="status" aria-live="polite">
      <div class="ui-skeleton" style="height:min(70vw,400px)"></div>
      <div class="mt-5 space-y-3 px-4">
        <div class="ui-skeleton h-5 w-1/3 rounded-xl"></div>
        <div class="ui-skeleton h-9 w-4/5 rounded-xl"></div>
        <div class="ui-skeleton h-20 rounded-xl"></div>
        <div class="ui-skeleton h-40 rounded-xl"></div>
      </div>
    </div>

    <!-- ── Not found ────────────────────────────────────────────── -->
    <div v-else-if="!dish" class="ui-empty-state mx-3 mt-3 space-y-3" role="alert">
      <p class="ui-kicker">{{ categoryName }}</p>
      <p class="text-lg font-semibold text-slate-100">{{ t('dishPage.notFoundTitle') }}</p>
      <p class="text-sm text-slate-400">{{ t('dishPage.notFoundText') }}</p>
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
        <img
          :src="dish.image_url || placeholder"
          :alt="dish.name"
          class="h-full w-full cursor-zoom-in object-cover transition-transform duration-500"
          loading="eager"
          fetchpriority="high"
          decoding="async"
          referrerpolicy="no-referrer"
          @error="handleDishImageError"
          @click="lightboxOpen = true"
        />
        <!-- gradient from top so controls are always readable -->
        <div class="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-black/55 to-transparent" />

        <!-- Back -->
        <button
          class="absolute left-3 top-3 flex h-9 w-9 items-center justify-center rounded-full border border-white/20 bg-black/45 text-white backdrop-blur-md transition hover:bg-black/65 active:scale-95"
          :aria-label="t('dishPage.goBack')"
          @click="router.back()"
        >
          <AppIcon name="arrowLeft" class="h-4 w-4" />
        </button>

        <!-- Cart badge -->
        <RouterLink
          v-if="cart.count"
          :to="{ name: 'cart' }"
          class="absolute right-3 top-3 flex h-9 items-center gap-1.5 rounded-full border border-white/20 bg-black/45 px-3 text-xs font-semibold text-white backdrop-blur-md"
        >
          <AppIcon name="cart" class="h-3.5 w-3.5" />
          {{ cart.count }}
        </RouterLink>

        <!-- Zoom hint -->
        <div class="pointer-events-none absolute bottom-3 right-3 flex h-7 w-7 items-center justify-center rounded-full bg-black/35 text-white/55 backdrop-blur-sm">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"/>
            <path d="M8 6a.75.75 0 01.75.75V7.5h.75a.75.75 0 010 1.5H8.75v.75a.75.75 0 01-1.5 0V9H6.5a.75.75 0 010-1.5h.75V6.75A.75.75 0 018 6z"/>
          </svg>
        </div>
      </div>

      <!-- ── Content ──────────────────────────────────────────── -->
      <div class="px-4 pt-5 space-y-5">

        <!-- Chips / status badges -->
        <div class="flex flex-wrap gap-1.5">
          <span class="ui-chip-strong text-[11px]">{{ categoryName }}</span>
          <span v-for="tag in dish.tags" :key="tag" class="ui-chip text-[11px]">{{ t(`dishPage.tag_${tag}`) }}</span>
          <span v-if="isBrowseOnlyPlan" class="ui-chip bg-sky-500/20 text-sky-200 text-[11px]">{{ t('dishPage.menuOnly') }}</span>
          <span v-if="dish.is_available === false" class="ui-chip border-red-500/40 bg-red-500/10 text-red-300 text-[11px]">{{ t('menu.soldOut') }}</span>
          <span v-if="dish.is_schedule_available === false" class="ui-chip border-slate-600/50 bg-slate-800/60 text-slate-400 text-[11px]">{{ t('menu.notAvailableNow') }}</span>
        </div>

        <!-- Title + price -->
        <div class="flex items-start gap-3">
          <h1 class="ui-display flex-1 text-2xl font-bold leading-tight text-slate-100 sm:text-3xl">{{ dish.name }}</h1>
          <span class="mt-1 shrink-0 rounded-full bg-[var(--color-secondary)] px-3.5 py-1.5 text-sm font-bold tabular-nums text-slate-900 shadow-lg shadow-[var(--color-secondary)]/25">
            {{ formatPrice(dish.price) }}
          </span>
        </div>

        <!-- Description -->
        <p v-if="dish.description" class="text-[15px] leading-relaxed text-slate-300">{{ dish.description }}</p>

        <!-- Option groups -->
        <div v-if="dish.option_groups?.length" class="ui-section-band space-y-4">
          <div v-for="group in dish.option_groups" :key="group.id" class="space-y-2.5">
            <div class="flex items-center justify-between gap-2">
              <p class="text-sm font-semibold text-slate-200">
                {{ group.name }}
                <span v-if="group.min_select > 0" class="ml-1.5 rounded-full bg-amber-400/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300">{{ t('dishPage.required') }}</span>
              </p>
              <span class="ui-data-strip text-[11px]">{{ group.max_select > 1 ? t('dishPage.pickUpTo', { n: group.max_select }) : t('dishPage.pickOne') }}</span>
            </div>
            <ul class="grid gap-2 text-sm sm:grid-cols-2">
              <li
                v-for="opt in group.options" :key="opt.id"
                class="ui-selection-card"
                :data-active="groupIsSelected(group.id, opt.id)"
                :data-warning="group.min_select > 0 && groupSelectedCount(group.id) < group.min_select"
              >
                <label class="flex w-full cursor-pointer items-center gap-2.5">
                  <input
                    v-if="group.max_select === 1"
                    type="radio"
                    :name="`group-${group.id}`"
                    :value="opt.id"
                    :checked="groupIsSelected(group.id, opt.id)"
                    class="h-4 w-4 accent-[var(--color-secondary)]"
                    @change="toggleInGroup(group.id, opt.id, group.max_select, group.min_select)"
                  />
                  <input
                    v-else
                    type="checkbox"
                    :value="opt.id"
                    :checked="groupIsSelected(group.id, opt.id)"
                    class="h-4 w-4 rounded accent-[var(--color-secondary)]"
                    @change="toggleInGroup(group.id, opt.id, group.max_select, group.min_select)"
                  />
                  <p class="min-w-0 flex-1 font-medium text-slate-100">{{ opt.name }}</p>
                  <span v-if="Number(opt.price_delta) > 0" class="shrink-0 text-xs font-semibold text-[var(--color-secondary)]">
                    +{{ formatPrice(opt.price_delta) }}
                  </span>
                </label>
              </li>
            </ul>
          </div>
          <p v-if="hasGroupMissing" class="text-xs text-amber-300">{{ t('dishPage.selectRequiredOptions') }}</p>
        </div>

        <!-- Flat options (legacy) -->
        <div v-if="dish.options?.length" class="ui-section-band space-y-3">
          <p class="text-sm font-semibold text-slate-200">{{ t('dishPage.options') }}</p>
          <ul class="grid gap-2 text-sm sm:grid-cols-2">
            <li
              v-for="opt in dish.options" :key="opt.id"
              class="ui-selection-card"
              :data-active="isOptionSelected(opt.id)"
              :data-warning="opt.is_required && !isOptionSelected(opt.id)"
            >
              <label class="flex w-full cursor-pointer items-center gap-2.5">
                <input
                  v-model="selectedOptionIds"
                  type="checkbox"
                  :value="opt.id"
                  class="h-4 w-4 rounded accent-[var(--color-secondary)]"
                />
                <div class="min-w-0 flex-1">
                  <p class="font-medium text-slate-100">{{ opt.name }}</p>
                  <p v-if="opt.is_required" class="text-[10px] text-amber-300">{{ t('dishPage.required') }}</p>
                </div>
                <span class="shrink-0 text-xs font-semibold text-[var(--color-secondary)]">+{{ formatPrice(opt.price_delta) }}</span>
              </label>
            </li>
          </ul>
          <p v-if="hasUngroupedRequiredMissing" class="text-xs text-amber-300">{{ t('dishPage.selectRequiredOptions') }}</p>
        </div>

        <!-- Desktop add-to-cart (sm+) -->
        <div class="hidden sm:block rounded-2xl border border-slate-700/60 bg-slate-900/50 p-4 space-y-3">
          <!-- Selected options summary -->
          <div v-if="selectedOptionObjects.length" class="flex flex-wrap gap-1.5">
            <span
              v-for="opt in selectedOptionObjects" :key="opt.id"
              class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-800/60 px-2.5 py-0.5 text-[11px] text-slate-300"
            >
              {{ opt.name }}
              <span v-if="Number(opt.price_delta) > 0" class="text-[var(--color-secondary)]">+{{ formatPrice(opt.price_delta) }}</span>
            </span>
          </div>
          <!-- Price + controls row -->
          <div class="flex items-center gap-3">
            <span class="ui-qty-control inline-flex items-center rounded-full border p-1">
              <button class="ui-press h-8 w-8 rounded-full text-sm text-slate-200" :aria-label="t('dishPage.decreaseQuantity')" @click="decrementQty">−</button>
              <input v-model.number="qty" type="number" min="1" max="99" class="w-10 border-0 bg-transparent text-center text-sm text-slate-100 focus:outline-none" />
              <button class="ui-press h-8 w-8 rounded-full text-sm text-slate-200" :aria-label="t('dishPage.increaseQuantity')" @click="incrementQty">+</button>
            </span>
            <div class="min-w-0">
              <p class="text-xl font-bold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(totalWithOptions) }}</p>
              <p v-if="qty > 1" class="text-[11px] text-slate-500 tabular-nums">{{ qty }} × {{ formatPrice(unitPriceWithOptions) }}</p>
            </div>
            <button
              class="ui-btn-primary ml-auto px-6 py-2.5 text-sm font-semibold"
              :disabled="orderingDisabled"
              :class="orderingDisabled ? 'cursor-not-allowed opacity-60' : ''"
              @click="addToCart"
            >
              <AppIcon v-if="!isBrowseOnlyPlan" name="plus" class="h-4 w-4" />
              {{ isBrowseOnlyPlan ? t('dishPage.browseOnlyPlan') : cart.canCheckout || cart.canWhatsapp ? t('dishPage.addToCart') : t('dishPage.addContactToOrder') }}
            </button>
            <button
              class="ui-share-btn shrink-0 rounded-xl border p-2.5 text-slate-400 transition-colors hover:text-slate-200"
              :aria-label="t('dishPage.shareDish')"
              @click="shareDish"
            >
              <AppIcon name="share" class="h-4 w-4" />
            </button>
          </div>
          <p v-if="hasRequiredMissing" class="text-xs text-amber-300">{{ t('dishPage.selectRequiredOptions') }}</p>
          <p v-if="!isRestaurantOpen" class="text-xs text-amber-300">{{ t('dishPage.restaurantClosedNotice') }}</p>
        </div>

        <!-- Similar dishes -->
        <div v-if="similarDishes.length" :ref="similarVis.target" class="space-y-3 pb-2">
          <p class="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{{ t('dishPage.similarDishes') }}</p>
          <div class="grid gap-3 sm:grid-cols-2">
            <template v-if="showSimilarSkeletons">
              <div v-for="n in 2" :key="'sk-' + n" class="h-28 ui-skeleton rounded-2xl"></div>
            </template>
            <RouterLink
              v-for="item in visibleSimilarDishes" :key="item.slug"
              :to="{ name: 'dish', params: { category: props.category, dish: item.slug } }"
              class="group ui-surface-lift overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-900/55 hover:border-[var(--color-secondary)]/50"
            >
              <div class="relative h-24 overflow-hidden">
                <img :src="item.image_url || placeholder" :alt="item.name" class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.04]" loading="lazy" decoding="async" @error="handleDishImageError" />
              </div>
              <div class="space-y-0.5 p-3">
                <p class="line-clamp-1 text-sm font-semibold text-slate-100">{{ item.name }}</p>
                <p class="text-sm font-bold text-[var(--color-secondary)]">{{ formatPrice(item.price) }}</p>
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
          role="dialog"
          aria-modal="true"
          class="fixed inset-0 z-[200] flex cursor-zoom-out items-center justify-center bg-black/96 backdrop-blur-sm"
          @click="lightboxOpen = false"
        >
          <img
            :src="dish.image_url || placeholder"
            :alt="dish.name"
            class="max-h-[95vh] max-w-[95vw] rounded-xl object-contain shadow-2xl shadow-black/60"
            @click.stop
          />
          <button
            class="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full border border-white/20 bg-black/60 text-white transition-colors hover:bg-black/80"
            :aria-label="t('common.close')"
            @click="lightboxOpen = false"
          >
            <AppIcon name="close" class="h-5 w-5" />
          </button>
        </div>
      </Transition>
    </Teleport>

    <!-- ══ Mobile sticky bottom bar ══ -->
    <div
      v-if="dish"
      class="ui-dish-bar fixed bottom-[5.15rem] left-3 right-3 z-20 overflow-hidden rounded-2xl px-3.5 py-3 backdrop-blur-xl sm:hidden"
      :class="hasRequiredMissing ? 'ring-1 ring-amber-500/40' : ''"
    >
      <!-- top shimmer line — amber when options missing, secondary otherwise -->
      <div
        class="pointer-events-none absolute inset-x-0 top-0 h-px"
        :style="hasRequiredMissing
          ? 'background: linear-gradient(90deg, transparent, rgba(245,158,11,0.6), transparent)'
          : 'background: linear-gradient(90deg, transparent, rgba(var(--color-secondary-rgb,245,158,11),0.45), transparent)'"
      />

      <!-- Row 1: dish name + price -->
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold text-slate-100">{{ dish.name }}</p>
          <!-- selected options summary chips -->
          <div v-if="selectedOptionObjects.length" class="mt-1 flex flex-wrap gap-1">
            <span
              v-for="opt in selectedOptionObjects"
              :key="opt.id"
              class="inline-flex items-center gap-0.5 rounded-full border border-slate-700/60 bg-slate-800/60 px-2 py-0.5 text-[10px] text-slate-300"
            >
              {{ opt.name }}<span v-if="Number(opt.price_delta) > 0" class="text-[var(--color-secondary)]">&nbsp;+{{ formatPrice(opt.price_delta) }}</span>
            </span>
          </div>
          <!-- required-options warning -->
          <p v-if="hasRequiredMissing" class="mt-1 text-[11px] font-medium text-amber-400">
            ⚠ {{ t('dishPage.selectRequiredOptions') }}
          </p>
        </div>
        <!-- price block -->
        <div class="shrink-0 text-right">
          <p class="text-base font-bold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(totalWithOptions) }}</p>
          <p v-if="qty > 1" class="text-[11px] tabular-nums text-slate-500">{{ qty }} × {{ formatPrice(unitPriceWithOptions) }}</p>
        </div>
      </div>

      <!-- Row 2: qty stepper + share + add button -->
      <div class="mt-2.5 flex items-center gap-2">
        <span class="ui-qty-control inline-flex items-center rounded-full border p-1">
          <button class="ui-press h-8 w-8 rounded-full text-sm text-slate-200" :aria-label="t('dishPage.decreaseQuantity')" @click="decrementQty">−</button>
          <input v-model.number="qty" type="number" min="1" max="99" class="w-10 border-0 bg-transparent text-center text-sm text-slate-100 focus:outline-none" />
          <button class="ui-press h-8 w-8 rounded-full text-sm text-slate-200" :aria-label="t('dishPage.increaseQuantity')" @click="incrementQty">+</button>
        </span>
        <button
          class="ui-share-btn shrink-0 rounded-xl border p-2.5 text-slate-400 transition-colors hover:text-slate-200"
          :aria-label="t('dishPage.shareDish')"
          @click="shareDish"
        >
          <AppIcon name="share" class="h-4 w-4" />
        </button>
        <button
          class="ui-btn-primary ml-auto flex-1 py-2.5 text-sm font-semibold"
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
import { useI18n } from '../composables/useI18n';
import { useMenuStore } from '../stores/menu';
import { useCartStore } from '../stores/cart';
import { useToastStore } from '../stores/toast';
import { useTenantStore } from '../stores/tenant';
import { useVisibility } from '../composables/useVisibility';
import { trackEvent } from '../lib/analytics';
import { withImageFallback } from '../lib/images';

const props = defineProps({ category: String, dish: String });

const router = useRouter();
const menu   = useMenuStore();
const cart   = useCartStore();
const tenant = useTenantStore();
const toast  = useToastStore();
const { currentLocale, formatCurrency, formatPrice, t } = useI18n();
const similarVis = useVisibility();

const qty               = ref(1);
const selectedOptionIds = ref([]);
const groupSelections   = ref({});
const lightboxOpen      = ref(false);

const whatsappPhone = (import.meta.env.VITE_CONTACT_PHONE || '').replace(/[^\d+]/g, '');
const meta          = computed(() => tenant.resolvedMeta || null);
const dishes        = computed(() => menu.dishes[props.category] || []);
const dish          = computed(() => dishes.value.find((d) => d.slug === props.dish));
const placeholder   = 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=900&q=80';
const handleDishImageError = (event) => withImageFallback(event, placeholder);

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
    try { await navigator.share({ title, text, url }); return; } catch {}
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
