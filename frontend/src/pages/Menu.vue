<template>
  <div
    :class="[
      'relative space-y-4 px-3 py-2 sm:space-y-5 sm:px-4 sm:py-3 sm:pb-8 ui-safe-bottom',
      cart.count ? 'pb-44' : 'pb-24',
    ]"
  >
    <!-- ── Hero: restaurant identity ────────────────────────────────────── -->
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
        <div class="absolute inset-0 bg-gradient-to-t from-slate-950/95 via-slate-950/55 to-slate-950/20" />
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(20,184,166,0.10),transparent_32%),radial-gradient(circle_at_bottom_left,rgba(245,158,11,0.10),transparent_30%)]" />

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
            <span
              v-if="ratingSummary && ratingSummary.count > 0"
              class="ui-chip"
              :title="t('menu.ratingChipTitle', { count: ratingSummary.count })"
            >
              <span class="text-amber-400 text-xs">★</span>
              {{ ratingSummary.average !== null ? ratingSummary.average.toFixed(1) : '' }}
              <span class="text-slate-500 text-[10px]">({{ ratingSummary.count }})</span>
            </span>
          </div>
        </div>
      </div>
    </header>

    <!-- ── Table context banner ──────────────────────────────────────────── -->
    <div
      v-if="tableContextBanner"
      class="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100"
    >✓ {{ tableContextBanner }}</div>

    <!-- ── Search + super-category + allergen filter panel ──────────────── -->
    <div class="ui-panel space-y-3 p-3 sm:p-4">
      <!-- Search -->
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

      <!-- Super-category pills -->
      <div v-if="superCategories.length > 1" class="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <button
          v-for="group in superCategories"
          :key="group.slug"
          class="ui-pill-nav shrink-0 whitespace-nowrap px-3 py-1.5 text-xs"
          :data-active="selectedSuperCategorySlug === group.slug"
          @click="onSuperCategorySelect(group.slug)"
        >{{ group.name }}</button>
      </div>

      <!-- Allergen-free filter -->
      <div v-if="availableAllergens.length" class="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <span class="shrink-0 self-center text-[10px] font-semibold uppercase tracking-wider text-slate-500">{{ t('menu.freeFrom') }}</span>
        <button
          v-for="allergen in availableAllergens"
          :key="allergen"
          class="shrink-0 whitespace-nowrap rounded-full border px-3 py-1 text-xs transition-colors"
          :class="selectedAllergenFilter.includes(allergen)
            ? 'border-amber-400/70 bg-amber-500/20 text-amber-200'
            : 'border-slate-700 bg-slate-900/60 text-slate-400 hover:border-amber-500/40 hover:text-amber-300'"
          @click="toggleAllergenFilter(allergen)"
        >{{ t(`menu.allergen_${allergen}`) }}</button>
      </div>

      <!-- Dietary tag filter — search mode only -->
      <div v-if="isSearching && availableTags.length" class="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <button
          class="ui-pill-nav shrink-0 whitespace-nowrap px-3 py-1.5 text-xs"
          :data-active="selectedTag === ''"
          @click="selectedTag = ''"
        >{{ t('menu.allDishes') }}</button>
        <button
          v-for="tag in availableTags"
          :key="tag"
          class="ui-pill-nav shrink-0 whitespace-nowrap px-3 py-1.5 text-xs"
          :data-active="selectedTag === tag"
          @click="selectedTag = tag"
        >{{ t(`dishPage.tag_${tag}`) }}</button>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════
         STICKY CATEGORY NAV  — visible only when not in search mode
         Tracks scroll position via updateActiveCategory()
         ══════════════════════════════════════════════════════════════════ -->
    <div
      v-if="!isSearching && visibleCategories.length > 1"
      class="ui-menu-category-nav sticky top-0 z-20 -mx-3 sm:-mx-4 md:top-16"
    >
      <div
        ref="pillRowEl"
        class="flex gap-2 overflow-x-auto px-3 py-2.5 sm:px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        <button
          v-for="cat in visibleCategories"
          :key="cat.slug"
          :data-cat-pill="cat.slug"
          class="ui-pill-nav shrink-0 whitespace-nowrap px-3 py-1.5 text-xs"
          :data-active="activeCategorySlug === cat.slug"
          @click="scrollToSection(cat.slug)"
        >{{ cat.name }}</button>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════
         SEARCH MODE — flat cross-category results
         ══════════════════════════════════════════════════════════════════ -->
    <template v-if="isSearching">
      <div class="px-1 space-y-0.5">
        <p class="ui-kicker">{{ t('menu.searchResultsKicker') }}</p>
        <h2 class="ui-display text-xl font-semibold text-white sm:text-2xl">
          {{ t('menu.searchResultsTitle', { query: search.trim(), count: filteredDishes.length }) }}
        </h2>
      </div>

      <!-- Search skeleton -->
      <div v-if="menu.loading && !filteredDishes.length" :class="dishGridClass">
        <div v-for="n in 6" :key="n" class="ui-skeleton rounded-2xl" :class="cardLayout === 'card' ? 'h-80' : 'h-[7rem]'" />
      </div>

      <!-- Search results -->
      <div v-else-if="filteredDishes.length" :class="dishGridClass">
        <DishCard
          v-for="dish in filteredDishes"
          :key="dish.slug"
          :dish="dish"
          :layout="cardLayout"
          :category-slug="dishCategorySlug(dish)"
          :currency="cartCurrency"
          :is-browse-only="isBrowseOnly"
          :is-open="isRestaurantOpen"
        />
      </div>

      <div v-else-if="!menu.loading" class="ui-empty-state space-y-4 text-slate-300">
        <div class="space-y-2 text-center">
          <div class="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl border border-slate-700/80 bg-slate-950/70">
            <AppIcon name="search" class="h-5 w-5" />
          </div>
          <p class="text-xl font-semibold text-slate-100">{{ t('menu.noMatchTitle') }}</p>
          <p class="text-sm text-slate-400">{{ t('menu.noMatchText') }}</p>
        </div>
        <button class="ui-btn-outline justify-center" @click="clearSearch">
          <AppIcon name="close" class="h-3.5 w-3.5" />{{ t('common.clear') }}
        </button>
      </div>
    </template>

    <!-- ══════════════════════════════════════════════════════════════════
         SECTION MODE — continuous scroll, one section per category
         ══════════════════════════════════════════════════════════════════ -->
    <template v-else>
      <section
        v-for="cat in visibleCategories"
        :key="cat.slug"
        :id="`section-${cat.slug}`"
        :ref="el => registerSection(el, cat.slug)"
        :data-slug="cat.slug"
        class="scroll-mt-28 space-y-3 md:scroll-mt-36"
      >
        <!-- Section heading -->
        <div class="flex items-center gap-3 pt-2">
          <div class="h-px flex-1 bg-gradient-to-r from-transparent via-slate-700/40 to-transparent" />
          <h2 class="ui-display px-1 text-xl font-semibold text-white sm:text-2xl">{{ cat.name }}</h2>
          <div class="h-px flex-1 bg-gradient-to-l from-transparent via-slate-700/40 to-transparent" />
        </div>
        <p v-if="cat.description" class="px-1 text-sm text-slate-400">{{ cat.description }}</p>

        <!-- Loading skeleton -->
        <div v-if="!menu.dishes[cat.slug]" :class="dishGridClass">
          <div v-for="n in 3" :key="n" class="ui-skeleton rounded-2xl" :class="cardLayout === 'card' ? 'h-80 rounded-[1.8rem]' : 'h-[7rem]'" />
        </div>

        <!-- Dish list / grid -->
        <div v-else-if="sectionDishes(cat.slug).length" :class="dishGridClass">
          <DishCard
            v-for="dish in sectionDishes(cat.slug)"
            :key="dish.slug"
            :dish="dish"
            :layout="cardLayout"
            :category-slug="cat.slug"
            :currency="cartCurrency"
            :is-browse-only="isBrowseOnly"
            :is-open="isRestaurantOpen"
          />
        </div>

        <!-- All dishes hidden by allergen filter -->
        <p v-else-if="menu.dishes[cat.slug] && selectedAllergenFilter.length" class="px-1 text-sm text-slate-500">
          {{ t('menu.noMatchText') }}
        </p>
      </section>
    </template>

    <p v-if="menu.error" class="text-sm text-red-400">{{ menu.error }}</p>

    <!-- ── Recent orders ─────────────────────────────────────────────────── -->
    <section v-if="cart.recentOrders?.length" class="ui-panel ui-reveal p-4 space-y-3">
      <p class="text-xs font-semibold uppercase tracking-[0.15em] text-slate-400">{{ t('menu.recentOrdersTitle') }}</p>
      <ul class="space-y-2">
        <li v-for="order in cart.recentOrders.slice(0, 5)" :key="order.order_number">
          <RouterLink
            :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
            class="flex items-center justify-between rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 text-sm hover:border-slate-600 transition-colors"
          >
            <div class="min-w-0 space-y-0.5">
              <p class="font-semibold text-slate-200">{{ order.order_number }}</p>
              <p v-if="order.items?.length" class="truncate text-xs text-slate-400">
                {{ order.items.slice(0, 3).map(i => i.dish_name).join(', ') }}{{ order.items.length > 3 ? '…' : '' }}
              </p>
            </div>
            <div class="shrink-0 text-right space-y-0.5">
              <p class="text-xs font-semibold" style="color:var(--color-secondary)">{{ formatCurrency(order.total, order.currency) }}</p>
              <p class="text-[10px] text-slate-500">{{ t('menu.viewStatus') }}</p>
            </div>
          </RouterLink>
        </li>
      </ul>
    </section>

    <!-- ── Find my order ─────────────────────────────────────────────────── -->
    <div class="text-center pb-2">
      <RouterLink
        :to="{ name: 'find-my-order' }"
        class="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
      >
        <AppIcon name="search" class="h-3.5 w-3.5" />
        {{ t('menu.findMyOrder') }}
      </RouterLink>
    </div>

    <!-- ── Sticky cart bar (mobile) ──────────────────────────────────────── -->
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
        <p class="text-base font-bold" style="color:var(--color-secondary)">{{ formatCurrency(cart.total, cartCurrency) }}</p>
        <AppIcon name="cart" class="h-4 w-4" style="color:var(--color-secondary)" />
      </div>
    </RouterLink>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon   from '../components/AppIcon.vue'
import DishCard  from '../components/DishCard.vue'
import { useI18n } from '../composables/useI18n'
import { withImageFallback } from '../lib/images'
import { trackEvent } from '../lib/analytics'
import { getTodayClosingTime, getNextOpenInfo, isCurrentlyOpenBySchedule } from '../lib/businessHours'
import api from '../lib/api'
import { useCartStore }   from '../stores/cart'
import { useMenuStore }   from '../stores/menu'
import { useTenantStore } from '../stores/tenant'
import { useToastStore }  from '../stores/toast'

const menu   = useMenuStore()
const tenant = useTenantStore()
const cart   = useCartStore()
const toast  = useToastStore()
const router = useRouter()
const route  = useRoute()
const { currentLocale, formatCurrency, itemCountLabel, t } = useI18n()

// ── Table QR context ─────────────────────────────────────────────────────────
const tableContextBanner = ref('')
const resolveTableContext = async () => {
  const tableSlug = route.params?.tableSlug
  if (!tableSlug) return
  try {
    const { data } = await api.get(`/table-context/${tableSlug}/`)
    if (data?.label && data?.slug) {
      cart.setTableContext(data.label, data.slug)
      tableContextBanner.value = t('menu.tableContextSet', { table: data.label })
    }
  } catch (err) {
    if (err?.response?.status === 404) toast.show(t('menu.tableNotFound'), 'error')
  }
}

// ── Filters ──────────────────────────────────────────────────────────────────
const search                 = ref('')
const selectedTag            = ref('')
const selectedAllergenFilter = ref([])   // allergens to EXCLUDE
const selectedSuperCategorySlug = ref('')

// ── Tenant / profile data ────────────────────────────────────────────────────
const meta             = computed(() => tenant.resolvedMeta || null)
const profile          = computed(() => meta.value?.profile || null)
const menuTheme        = computed(() => profile.value?.menu_theme || 'dark')
const isBrowseOnly     = computed(() => tenant.isBrowseOnlyPlan === true)
const ratingSummary    = computed(() => meta.value?.rating_summary || null)
const tenantName       = computed(() => meta.value?.name || t('customerLayout.fallbackTenantName'))
const tenantDescription = computed(() => String(profile.value?.description || profile.value?.tagline || '').trim() || t('customerLeadPage.fallbackDescription'))
const heroImage        = computed(() => String(profile.value?.hero_url || '').trim())
const logoImage        = computed(() => String(profile.value?.logo_url || '').trim())
const locationLine     = computed(() => String(profile.value?.address || meta.value?.name || '').trim())
const cartCurrency     = computed(() => cart.items.find(i => i.currency)?.currency || meta.value?.plan?.currency || 'USD')

/** Card layout from profile: 'row' | 'card' | 'compact', defaults to 'row' */
const cardLayout = computed(() => profile.value?.menu_card_layout || 'row')

/** CSS grid/flex class applied to every dish list, adapts to the chosen layout */
const dishGridClass = computed(() => {
  if (cardLayout.value === 'card')    return 'grid gap-4 sm:grid-cols-2 xl:grid-cols-3'
  if (cardLayout.value === 'compact') return 'space-y-2'
  return 'space-y-3'   // row (default)
})

// ── Open/status ──────────────────────────────────────────────────────────────
const isRestaurantOpen = computed(() => {
  if (typeof profile.value?.is_open_now === 'boolean') return profile.value.is_open_now
  if (profile.value?.is_open === false) return false
  const schedule = profile.value?.business_hours_schedule
  if (schedule && Object.keys(schedule).length) {
    const bySchedule = isCurrentlyOpenBySchedule(schedule)
    if (bySchedule === false) return false
  }
  return true
})
const statusLabel = computed(() => {
  if (profile.value?.is_open === false) return t('customerLeadPage.closedNow')
  const schedule = profile.value?.business_hours_schedule
  if (schedule && Object.keys(schedule).length) {
    const openBySchedule = isCurrentlyOpenBySchedule(schedule)
    if (openBySchedule === true) {
      const closeTime = getTodayClosingTime(schedule)
      return closeTime ? t('menu.opensUntil', { time: closeTime }) : t('customerLeadPage.openNow')
    }
    if (openBySchedule === false) {
      const next = getNextOpenInfo(schedule, currentLocale.value)
      if (next) {
        const dayPart = next.isTomorrow ? t('menu.tomorrow') : next.dayLabel
        return t('menu.opensAt', { day: dayPart, time: next.openTime })
      }
    }
  }
  return t('customerLeadPage.openNow')
})

// ── Category data ────────────────────────────────────────────────────────────
const menuCategories     = computed(() => Array.isArray(menu.categories) ? menu.categories : [])
const storeSuperCategories = computed(() => Array.isArray(menu.superCategories) ? menu.superCategories : [])

const superCategories = computed(() => {
  if (storeSuperCategories.value.length) return [...storeSuperCategories.value].sort((a, b) => (a.position || 0) - (b.position || 0))
  const seen = new Map()
  menuCategories.value.forEach(cat => {
    const slug = String(cat.super_category_slug || 'menu').trim()
    if (!slug || seen.has(slug)) return
    seen.set(slug, { id: cat.super_category || slug, slug, name: cat.super_category_name || 'Menu', position: 0 })
  })
  return [...seen.values()]
})

const visibleCategories = computed(() => {
  const activeSlug = String(selectedSuperCategorySlug.value || '').trim()
  return [...menuCategories.value]
    .filter(cat => !activeSlug || String(cat.super_category_slug || '').trim() === activeSlug)
    .sort((a, b) => (a.position || 0) - (b.position || 0))
})

// ── Search mode ──────────────────────────────────────────────────────────────
const isSearching = computed(() => search.value.trim().length > 0)

const allLoadedDishes = computed(() => Object.values(menu.dishes || {}).flat())

const availableTags = computed(() => {
  const tags = new Set()
  allLoadedDishes.value.forEach(d => (d.tags || []).forEach(tag => tags.add(tag)))
  return [...tags].sort()
})

const availableAllergens = computed(() => {
  const allergens = new Set()
  allLoadedDishes.value.forEach(d => (d.allergens || []).forEach(a => allergens.add(a)))
  return [...allergens].sort()
})

const filteredDishes = computed(() => {
  let dishes = allLoadedDishes.value
  if (selectedTag.value) {
    dishes = dishes.filter(d => (d.tags || []).includes(selectedTag.value))
  }
  if (selectedAllergenFilter.value.length) {
    dishes = dishes.filter(d => !selectedAllergenFilter.value.some(a => (d.allergens || []).includes(a)))
  }
  const query = search.value.trim().toLowerCase()
  if (query) {
    dishes = dishes.filter(d =>
      [d.name, d.description, d.slug].filter(Boolean).some(v => String(v).toLowerCase().includes(query)) ||
      (d.tags || []).some(tag => tag.replace('_', ' ').includes(query))
    )
  }
  return dishes
})

/** Return dishes for a section, applying allergen exclusion */
const sectionDishes = (slug) => {
  let dishes = menu.dishes[slug] || []
  if (selectedAllergenFilter.value.length) {
    dishes = dishes.filter(d => !selectedAllergenFilter.value.some(a => (d.allergens || []).includes(a)))
  }
  return dishes
}

/** Find which category a dish belongs to (used in search results) */
const dishCategorySlug = (dish) => {
  for (const [slug, list] of Object.entries(menu.dishes || {})) {
    if ((list || []).some(d => d.slug === dish.slug)) return slug
  }
  return visibleCategories.value[0]?.slug || ''
}

// ── Sticky category nav ──────────────────────────────────────────────────────
const activeCategorySlug = ref('')
const pillRowEl = ref(null)

/** Auto-scroll the pill row so the active pill is always centred */
const syncPillScroll = (slug) => {
  nextTick(() => {
    const pill = pillRowEl.value?.querySelector(`[data-cat-pill="${slug}"]`)
    if (pill) pill.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  })
}

watch(activeCategorySlug, syncPillScroll)

/** Scroll listener — updates activeCategorySlug as the user scrolls */
const updateActiveCategory = () => {
  if (isSearching.value) return
  const cats = visibleCategories.value
  const OFFSET = 130  // px — approx header + sticky nav height
  for (let i = cats.length - 1; i >= 0; i--) {
    const el = document.getElementById(`section-${cats[i].slug}`)
    if (!el) continue
    if (el.getBoundingClientRect().top + window.scrollY <= window.scrollY + OFFSET + 10) {
      if (activeCategorySlug.value !== cats[i].slug) {
        activeCategorySlug.value = cats[i].slug
      }
      return
    }
  }
  if (cats.length && activeCategorySlug.value !== cats[0].slug) {
    activeCategorySlug.value = cats[0].slug
  }
}

/** Tap category pill → smooth scroll to its section */
const scrollToSection = (slug) => {
  activeCategorySlug.value = slug  // optimistic update
  nextTick(() => {
    const el = document.getElementById(`section-${slug}`)
    if (!el) return
    const OFFSET = 115
    const top = el.getBoundingClientRect().top + window.scrollY - OFFSET
    window.scrollTo({ top, behavior: 'smooth' })
  })
  try { navigator.vibrate?.(10) } catch { /* not supported */ }
}

const onSuperCategorySelect = (slug) => {
  selectedSuperCategorySlug.value = slug
  // After the DOM updates, snap to the first section in this super-category
  nextTick(() => {
    const first = visibleCategories.value[0]
    if (first) {
      activeCategorySlug.value = first.slug
      scrollToSection(first.slug)
    }
  })
}

// ── Lazy dish loading per section ────────────────────────────────────────────
const loadedSlugs = ref(new Set())
let loadObserver = null

const registerSection = (el, slug) => {
  if (!el) return
  if (loadObserver && !loadedSlugs.value.has(slug)) {
    loadObserver.observe(el)
  }
}

// ── Sync / initialise selection ──────────────────────────────────────────────
const syncSelection = () => {
  if (!superCategories.value.length) { selectedSuperCategorySlug.value = ''; return }
  if (!superCategories.value.some(g => g.slug === selectedSuperCategorySlug.value)) {
    selectedSuperCategorySlug.value = String(superCategories.value[0]?.slug || '')
  }
  if (visibleCategories.value.length && !activeCategorySlug.value) {
    activeCategorySlug.value = visibleCategories.value[0].slug
  }
}

// ── Lifecycle ────────────────────────────────────────────────────────────────
watch(menuTheme, theme => document.documentElement.setAttribute('data-menu-theme', theme), { immediate: true })
watch([superCategories, menuCategories], syncSelection, { immediate: true })

watch(() => currentLocale.value, () => menu.fetchCategories(true))

// When super-category filter changes, reset to first section
watch(selectedSuperCategorySlug, () => {
  if (visibleCategories.value.length) {
    activeCategorySlug.value = visibleCategories.value[0].slug
  }
})

onMounted(async () => {
  await resolveTableContext()
  if (!menuCategories.value.length) await menu.fetchCategories()

  syncSelection()

  // ① Pre-load first 3 categories immediately
  const cats = visibleCategories.value
  const preload = Math.min(3, cats.length)
  for (let i = 0; i < preload; i++) {
    const slug = cats[i].slug
    loadedSlugs.value.add(slug)
    if (!menu.dishes[slug]) menu.fetchDishesByCategory(slug)
  }
  if (cats.length) activeCategorySlug.value = cats[0].slug

  // ② IntersectionObserver — lazy-load remaining sections
  loadObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return
      const slug = entry.target.dataset?.slug
      if (slug && !loadedSlugs.value.has(slug)) {
        loadedSlugs.value.add(slug)
        if (!menu.dishes[slug]) menu.fetchDishesByCategory(slug)
      }
      loadObserver.unobserve(entry.target)
    })
  }, { rootMargin: '400px 0px' })

  // ③ Scroll listener for active pill tracking
  window.addEventListener('scroll', updateActiveCategory, { passive: true })

  trackEvent('menu_view', { source: 'customer_menu_browse' })
})

onUnmounted(() => {
  loadObserver?.disconnect()
  window.removeEventListener('scroll', updateActiveCategory)
  document.documentElement.removeAttribute('data-menu-theme')
})

// ── Utilities ────────────────────────────────────────────────────────────────
const clearSearch = () => {
  search.value = ''
  selectedTag.value = ''
  selectedAllergenFilter.value = []
}
const toggleAllergenFilter = (allergen) => {
  const idx = selectedAllergenFilter.value.indexOf(allergen)
  if (idx === -1) selectedAllergenFilter.value = [...selectedAllergenFilter.value, allergen]
  else selectedAllergenFilter.value = selectedAllergenFilter.value.filter(a => a !== allergen)
}

const handleHeroImageError  = e => withImageFallback(e)
const handleLogoImageError  = e => withImageFallback(e)
</script>
