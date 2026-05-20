<template>
  <div :class="['relative ui-safe-bottom', cart.count ? 'pb-44' : 'pb-28']">

    <!-- ══ Full-bleed hero ══ -->
    <header data-theme-dark class="relative overflow-hidden bg-slate-950" style="min-height:240px; height:min(72vw,420px)">
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
      <div class="absolute inset-0 bg-gradient-to-t from-slate-950/97 via-slate-950/50 to-slate-950/10" />
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(20,184,166,0.09),transparent_32%),radial-gradient(circle_at_bottom_left,rgba(245,158,11,0.09),transparent_30%)]" />

      <div class="relative flex h-full flex-col justify-end p-4 sm:p-5">
        <div class="flex items-end gap-3">
          <img
            v-if="logoImage"
            :src="logoImage"
            :alt="`${tenantName} logo`"
            class="h-14 w-14 shrink-0 rounded-2xl border-2 object-cover shadow-2xl shadow-black/50 sm:h-16 sm:w-16 transition-colors duration-500"
            :class="isRestaurantOpen ? 'border-[var(--color-secondary)]/60' : 'border-white/20'"
            loading="eager"
            decoding="async"
            @error="handleLogoImageError"
          />
          <div class="min-w-0 space-y-0.5">
            <h1 class="ui-display text-xl font-semibold tracking-tight text-white sm:text-2xl drop-shadow">{{ tenantName }}</h1>
            <p v-if="tenantDescription" class="line-clamp-1 text-xs text-slate-300/80">{{ tenantDescription }}</p>
          </div>
        </div>
        <div class="mt-2.5 flex flex-wrap gap-1.5">
          <span
            class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold backdrop-blur-sm"
            :style="isRestaurantOpen
              ? 'border-color:rgba(52,211,153,0.40);background:rgba(16,185,129,0.14);color:rgb(110,231,183)'
              : 'border-color:rgba(239,68,68,0.35);background:rgba(239,68,68,0.12);color:rgb(252,165,165)'"
          >
            <span class="relative inline-flex shrink-0">
              <span v-if="isRestaurantOpen" class="animate-ping absolute inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 opacity-60" />
              <span class="relative inline-block h-1.5 w-1.5 rounded-full" :style="isRestaurantOpen ? 'background:rgb(52,211,153)' : 'background:rgb(239,68,68)'" />
            </span>
            {{ statusLabel }}
          </span>
          <RouterLink
            v-if="superCategories.length > 1"
            :to="{ name: 'menu' }"
            class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-900/60 px-2.5 py-1 text-xs font-semibold text-slate-300 backdrop-blur-sm"
          >
            <AppIcon name="arrowLeft" class="h-3 w-3" />
            {{ t('menuSelect.backToMenus') }}
          </RouterLink>
          <span v-if="locationLine" class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-900/55 px-2.5 py-1 text-xs text-slate-300 backdrop-blur-sm">
            <AppIcon name="info" class="h-3 w-3" />{{ locationLine }}
          </span>
          <span
            v-if="ratingSummary && ratingSummary.count > 0"
            class="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs backdrop-blur-sm"
          >
            <span class="text-amber-400">★</span>
            <span class="font-semibold text-amber-200">{{ ratingSummary.average !== null ? ratingSummary.average.toFixed(1) : '' }}</span>
            <span class="text-amber-400/60 text-[10px]">({{ ratingSummary.count }})</span>
          </span>
        </div>
      </div>
    </header>

    <!-- ══ Table context banner ══ -->
    <div v-if="tableContextBanner" class="mx-3 mt-2 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
      ✓ {{ tableContextBanner }}
    </div>

    <!-- ══ Sticky categories bar ══ -->
    <div v-if="visibleCategories.length > 0" class="ui-menu-category-nav sticky top-0 z-20 md:top-16">
      <div class="relative">
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
          <span class="mx-1 w-px shrink-0 self-stretch bg-slate-700/50" />
          <button
            class="ui-pill-nav shrink-0 px-3 py-1.5 text-xs font-bold tracking-wider"
            :data-active="catSheetOpen"
            @click="catSheetOpen = !catSheetOpen"
          >···</button>
        </div>

        <!-- All-categories sheet -->
        <Transition name="cat-sheet">
          <div
            v-if="catSheetOpen"
            class="absolute left-0 right-0 top-full z-30 border-b border-slate-800/80 bg-slate-950/98 px-3 py-3 backdrop-blur-xl"
          >
            <div class="flex flex-wrap gap-2">
              <button
                v-for="cat in visibleCategories"
                :key="`sheet-${cat.slug}`"
                class="ui-pill-nav whitespace-nowrap px-3 py-1.5 text-xs"
                :data-active="activeCategorySlug === cat.slug"
                @click="scrollToSection(cat.slug); catSheetOpen = false"
              >{{ cat.name }}</button>
            </div>
          </div>
        </Transition>
      </div>

      <!-- Allergen strip -->
      <div v-if="availableAllergens.length" class="flex items-center gap-2 overflow-x-auto border-t border-slate-800/40 px-3 py-1.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <span class="shrink-0 text-[10px] font-semibold uppercase tracking-wider text-slate-500">{{ t('menu.freeFrom') }}</span>
        <button
          v-for="allergen in availableAllergens"
          :key="allergen"
          class="shrink-0 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] transition-colors"
          :class="selectedAllergenFilter.includes(allergen)
            ? 'border-amber-400/70 bg-amber-500/20 text-amber-200'
            : 'border-slate-700 bg-slate-900/60 text-slate-400'"
          @click="toggleAllergenFilter(allergen)"
        >{{ t(`menu.allergen_${allergen}`) }}</button>
      </div>
    </div>

    <!-- ══ Sections ══ -->
    <div class="px-3 sm:px-4 mt-3 space-y-4 sm:space-y-5">
      <section
        v-for="cat in visibleCategories"
        :key="cat.slug"
        :id="`section-${cat.slug}`"
        :ref="el => registerSection(el, cat.slug)"
        :data-slug="cat.slug"
        class="scroll-mt-24 space-y-3 md:scroll-mt-32"
      >
        <div class="flex items-start justify-between gap-3 border-b border-slate-800/50 pb-3">
          <div class="flex items-start gap-3 min-w-0">
            <span
              class="mt-[3px] shrink-0 block h-7 w-[3.5px] rounded-full"
              style="background:linear-gradient(180deg,var(--color-secondary) 0%,var(--color-primary) 100%)"
            />
            <div class="min-w-0">
              <h2 class="ui-display text-xl font-semibold leading-tight text-white sm:text-2xl">{{ cat.name }}</h2>
              <p v-if="cat.description" class="mt-0.5 line-clamp-1 text-xs text-slate-500">{{ cat.description }}</p>
            </div>
          </div>
          <span
            v-if="menu.dishes[cat.slug]?.length"
            class="mt-1 shrink-0 rounded-full border border-slate-800 bg-slate-900/60 px-2.5 py-0.5 text-[11px] text-slate-500 tabular-nums"
          >{{ sectionDishes(cat.slug).length }}</span>
        </div>

        <div v-if="!menu.dishes[cat.slug]" :class="dishGridClass">
          <div v-for="n in 3" :key="n" class="ui-skeleton rounded-2xl" :class="cardLayout === 'card' ? 'h-80 rounded-[1.8rem]' : 'h-[7rem]'" />
        </div>

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

        <p v-else-if="menu.dishes[cat.slug] && selectedAllergenFilter.length" class="px-1 text-sm text-slate-500">
          {{ t('menu.noMatchText') }}
        </p>
      </section>

      <p v-if="menu.error" class="text-sm text-red-400">{{ menu.error }}</p>

      <!-- Recent orders -->
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

      <div class="pb-2 text-center">
        <RouterLink
          :to="{ name: 'find-my-order' }"
          class="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          <AppIcon name="search" class="h-3.5 w-3.5" />
          {{ t('menu.findMyOrder') }}
        </RouterLink>
      </div>
    </div>

    <!-- ── Sticky cart bar (mobile) ──────────────────────────────────────── -->
    <Transition name="cart-bar">
      <RouterLink
        v-if="cart.count"
        :to="{ name: 'cart' }"
        class="ui-cart-bar fixed bottom-[5.15rem] left-3 right-3 z-20 sm:hidden flex items-center justify-between rounded-2xl px-4 py-3 backdrop-blur-xl"
      >
        <div class="flex items-center gap-2.5">
          <span class="flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-slate-950" style="background:var(--color-secondary)">{{ cart.count }}</span>
          <p class="text-sm font-semibold text-white">{{ t('common.cart') }}</p>
        </div>
        <div class="flex items-center gap-2">
          <p class="text-base font-bold" style="color:var(--color-secondary)">{{ formatCurrency(cart.total, cartCurrency) }}</p>
          <AppIcon name="cart" class="h-4 w-4" style="color:var(--color-secondary)" />
        </div>
      </RouterLink>
    </Transition>
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

// ── Route props (passed by /m/:menuSlug) ─────────────────────────────────────
const props = defineProps({
  menuSlug: { type: String, default: '' },
})

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
const selectedAllergenFilter = ref([])   // allergens to EXCLUDE
const selectedSuperCategorySlug = ref('')

// ── Categories sheet ─────────────────────────────────────────────────────────
const catSheetOpen = ref(false)

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

const allLoadedDishes = computed(() => {
  const slugs = new Set(visibleCategories.value.map(c => c.slug))
  return Object.entries(menu.dishes || {})
    .filter(([slug]) => slugs.has(slug))
    .flatMap(([, dishes]) => dishes)
})

const availableAllergens = computed(() => {
  const allergens = new Set()
  allLoadedDishes.value.forEach(d => (d.allergens || []).forEach(a => allergens.add(a)))
  return [...allergens].sort()
})

/** Return dishes for a section, applying allergen exclusion */
const sectionDishes = (slug) => {
  let dishes = menu.dishes[slug] || []
  if (selectedAllergenFilter.value.length) {
    dishes = dishes.filter(d => !selectedAllergenFilter.value.some(a => (d.allergens || []).includes(a)))
  }
  return dishes
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
  // When a menuSlug prop is provided (route /m/:menuSlug), lock to that menu
  if (props.menuSlug && superCategories.value.some(g => g.slug === props.menuSlug)) {
    selectedSuperCategorySlug.value = props.menuSlug
  } else if (!superCategories.value.some(g => g.slug === selectedSuperCategorySlug.value)) {
    selectedSuperCategorySlug.value = String(superCategories.value[0]?.slug || '')
  }
  if (visibleCategories.value.length && !activeCategorySlug.value) {
    activeCategorySlug.value = visibleCategories.value[0].slug
  }
}

// ── Lifecycle ────────────────────────────────────────────────────────────────
const applyMenuTheme = (restaurantTheme) => {
  const userPref = localStorage.getItem('ui-color-scheme') // 'dark' | 'system' | null
  if (userPref === 'dark') {
    document.documentElement.removeAttribute('data-menu-theme')
    return
  }
  if (userPref === 'system') {
    const osDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (osDark) document.documentElement.removeAttribute('data-menu-theme')
    else document.documentElement.setAttribute('data-menu-theme', restaurantTheme || 'light')
    return
  }
  // No user pref — use restaurant config
  if (restaurantTheme && restaurantTheme !== 'dark') {
    document.documentElement.setAttribute('data-menu-theme', restaurantTheme)
  } else {
    document.documentElement.removeAttribute('data-menu-theme')
  }
}

watch(menuTheme, applyMenuTheme, { immediate: true })
watch([superCategories, menuCategories], syncSelection, { immediate: true })

// React to route prop changes (e.g. navigating directly from one menu to another)
watch(() => props.menuSlug, (slug) => {
  if (slug) {
    activeCategorySlug.value = ''
    syncSelection()
  }
})

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
const toggleAllergenFilter = (allergen) => {
  const idx = selectedAllergenFilter.value.indexOf(allergen)
  if (idx === -1) selectedAllergenFilter.value = [...selectedAllergenFilter.value, allergen]
  else selectedAllergenFilter.value = selectedAllergenFilter.value.filter(a => a !== allergen)
}

const handleHeroImageError  = e => withImageFallback(e)
const handleLogoImageError  = e => withImageFallback(e)
</script>

<style scoped>
/* Categories all-sheet slide-down */
.cat-sheet-enter-active { transition: opacity 160ms ease, transform 160ms cubic-bezier(0.22,1,0.36,1); }
.cat-sheet-leave-active { transition: opacity 120ms ease, transform 120ms ease; }
.cat-sheet-enter-from   { opacity: 0; transform: translateY(-6px); }
.cat-sheet-leave-to     { opacity: 0; transform: translateY(-4px); }

/* Cart bar slide-up / fade transition */
.cart-bar-enter-active {
  transition: opacity 220ms ease, transform 220ms cubic-bezier(0.22,1,0.36,1);
}
.cart-bar-leave-active {
  transition: opacity 160ms ease, transform 160ms ease;
}
.cart-bar-enter-from {
  opacity: 0;
  transform: translateY(10px) scale(0.97);
}
.cart-bar-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}
</style>
