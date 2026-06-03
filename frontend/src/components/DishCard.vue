<template>
  <!-- ══════════════════════════════════════════════════════
       ROW layout  —  Wolt / Deliveroo mobile-first style
       Text left  ·  Square image right  ·  Add/qty overlay
       ══════════════════════════════════════════════════════ -->
  <article
    v-if="layout === 'row'"
    class="ui-dish-row group relative flex overflow-hidden rounded-2xl border bg-slate-950/80 transition-all duration-200 active:scale-[0.99] cursor-pointer select-none"
    :class="[
      isSoldOut || isScheduleUnavailable ? 'opacity-55' : '',
      qtyInCart > 0
        ? 'border-[var(--color-secondary)]/40 shadow-[0_0_0_1px_rgba(245,158,11,0.07)_inset]'
        : 'border-slate-800/70',
    ]"
    role="button"
    tabindex="0"
    :aria-label="dish.name"
    @click="handleOpen"
    @keydown.enter.space.prevent="handleOpen"
  >
    <!-- In-cart top accent line -->
    <div
      v-if="qtyInCart > 0"
      class="pointer-events-none absolute inset-x-0 top-0 h-[2px] z-10"
      style="background: linear-gradient(90deg, transparent, var(--color-secondary), transparent)"
    />

    <!-- Left: text -->
    <div class="flex min-w-0 flex-1 flex-col justify-between gap-2 py-3 pl-3.5 pr-2.5">
      <div class="space-y-1">
        <h3 class="line-clamp-2 text-sm font-semibold leading-snug text-white">{{ dish.name }}</h3>
        <p v-if="dish.description" class="line-clamp-2 text-[12px] leading-relaxed text-slate-400/90">{{ dish.description }}</p>
      </div>
      <div class="flex flex-wrap items-center gap-1.5">
        <!-- Price pill -->
        <span
          class="inline-flex items-center rounded-full px-2 py-[3px] text-[13px] font-bold"
          style="color:var(--color-secondary); background: rgba(245,158,11,0.10)"
        >{{ formatPrice(dish.price) }}</span>
        <span
          v-for="tag in (dish.tags || []).slice(0, 2)"
          :key="tag"
          class="rounded-full border border-slate-700/50 bg-slate-900/60 px-1.5 py-0.5 text-[10px] text-slate-400"
        >{{ t(`dishPage.tag_${tag}`) }}</span>
        <span v-if="isSoldOut"         class="rounded-full border border-red-500/40 bg-red-500/10 px-1.5 py-0.5 text-[10px] text-red-300">{{ t('menu.soldOut') }}</span>
        <span v-else-if="isScheduleUnavailable" class="rounded-full border border-slate-700/50 px-1.5 py-0.5 text-[10px] text-slate-500">{{ t('menu.notAvailableNow') }}</span>
        <!-- Customisable indicator -->
        <span
          v-if="needsDetailPage && canOrder"
          class="rounded-full border border-slate-700/40 px-1.5 py-0.5 text-[10px] text-slate-500"
        >{{ t('dishPage.customisable') }}</span>
      </div>
    </div>

    <!-- Right: square image + add controls -->
    <div class="relative h-[6.5rem] w-[6.5rem] shrink-0 sm:h-32 sm:w-32">
      <img
        v-if="dish.image_url"
        :src="dish.image_url"
        :alt="dish.name"
        class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
        loading="lazy"
        decoding="async"
        @error="onImgError"
      />
      <div
        v-else
        class="ui-menu-dish-placeholder relative flex h-full w-full items-center justify-center overflow-hidden"
        style="background: linear-gradient(145deg, rgba(245,158,11,0.13) 0%, rgba(15,118,110,0.09) 100%)"
      >
        <div class="pointer-events-none absolute inset-0" style="background-image: radial-gradient(rgba(245,158,11,0.22) 1px, transparent 1px); background-size: 10px 10px;" />
        <span class="relative text-2xl font-black select-none" style="color: rgba(245,158,11,0.30)">
          {{ (dish.name || '?')[0].toUpperCase() }}
        </span>
      </div>
      <!-- left-edge blend from card background -->
      <div class="pointer-events-none absolute inset-0 bg-gradient-to-r from-slate-950/40 via-transparent to-transparent" />

      <!-- Add / qty controls overlaid at bottom-right -->
      <div v-if="canOrder" class="absolute bottom-2 right-2 z-10" @click.stop>
        <!-- qty stepper when already in cart -->
        <div
          v-if="qtyInCart > 0"
          class="flex items-center gap-0.5 rounded-full border bg-slate-950/95 px-1.5 py-0.5 shadow-xl backdrop-blur-md"
          style="border-color: rgba(245,158,11,0.50); box-shadow: 0 4px 12px rgba(0,0,0,0.5), 0 0 0 1px rgba(245,158,11,0.08) inset"
        >
          <button
            class="flex h-6 w-6 items-center justify-center rounded-full transition hover:bg-amber-500/15 active:scale-90"
            style="color:var(--color-secondary)"
            :aria-label="t('dishPage.decreaseQuantity')"
            @click.stop="handleDecrement"
          ><AppIcon name="minus" class="h-3 w-3" /></button>
          <span class="min-w-[1.1rem] text-center text-xs font-bold tabular-nums" style="color:var(--color-secondary)">{{ qtyInCart }}</span>
          <button
            class="flex h-6 w-6 items-center justify-center rounded-full transition hover:bg-amber-500/15 active:scale-90"
            style="color:var(--color-secondary)"
            :aria-label="t('dishPage.increaseQuantity')"
            @click.stop="handleAdd"
          ><AppIcon name="plus" class="h-3 w-3" /></button>
        </div>
        <!-- plain + button -->
        <button
          v-else
          class="flex h-8 w-8 items-center justify-center rounded-full shadow-xl ring-[3px] ring-[var(--color-secondary)]/15 transition hover:brightness-110 hover:ring-[var(--color-secondary)]/28 active:scale-90"
          style="background-color:var(--color-secondary)"
          :aria-label="t('dishPage.addToCart')"
          @click.stop="handleAdd"
        ><AppIcon name="plus" class="h-4 w-4 text-slate-950" /></button>
      </div>
    </div>
  </article>

  <!-- ══════════════════════════════════════════════════════
       CARD layout  —  image-top grid card
       ══════════════════════════════════════════════════════ -->
  <article
    v-else-if="layout === 'card'"
    class="group ui-menu-dish-card overflow-hidden rounded-[1.8rem] border bg-slate-950/82 transition-all duration-300 cursor-pointer"
    :class="[
      isSoldOut || isScheduleUnavailable ? 'opacity-60' : '',
      qtyInCart > 0
        ? 'border-[var(--color-secondary)]/40 shadow-[0_20px_50px_rgba(2,6,23,0.42),0_0_0_1px_rgba(245,158,11,0.06)_inset]'
        : 'border-slate-800/80 shadow-[0_20px_50px_rgba(2,6,23,0.36)] hover:border-slate-700/70 hover:shadow-[0_24px_60px_rgba(2,6,23,0.48)]',
    ]"
    role="button"
    tabindex="0"
    :aria-label="dish.name"
    @click="handleOpen"
    @keydown.enter.space.prevent="handleOpen"
  >
    <!-- In-cart top accent -->
    <div
      v-if="qtyInCart > 0"
      class="pointer-events-none absolute inset-x-0 top-0 h-[2px] z-10 rounded-t-[1.8rem]"
      style="background: linear-gradient(90deg, transparent, var(--color-secondary), transparent)"
    />
    <!-- Image -->
    <div class="relative aspect-[4/3] overflow-hidden bg-slate-900">
      <img
        v-if="dish.image_url"
        :src="dish.image_url"
        :alt="dish.name"
        class="h-full w-full object-cover transition duration-500 group-hover:scale-[1.05]"
        loading="lazy"
        decoding="async"
        @error="onImgError"
      />
      <div
        v-else
        class="ui-menu-dish-placeholder absolute inset-0 flex items-center justify-center overflow-hidden"
        style="background: linear-gradient(145deg, rgba(245,158,11,0.13) 0%, rgba(15,118,110,0.09) 100%)"
      >
        <div class="pointer-events-none absolute inset-0" style="background-image: radial-gradient(rgba(245,158,11,0.22) 1px, transparent 1px); background-size: 12px 12px;" />
        <span class="relative text-4xl font-black select-none" style="color: rgba(245,158,11,0.25)">
          {{ (dish.name || '?')[0].toUpperCase() }}
        </span>
      </div>
      <div class="pointer-events-none absolute inset-0 bg-gradient-to-t from-slate-950/88 via-slate-950/15 to-transparent" />
      <!-- Price badge — repositioned bottom-left for visual harmony -->
      <div class="absolute left-3 bottom-3">
        <span class="rounded-full px-3 py-1 text-xs font-bold shadow-lg" style="background-color:var(--color-secondary); color: #0f172a">
          {{ formatPrice(dish.price) }}
        </span>
      </div>
      <!-- Tags top-left -->
      <div v-if="dish.tags?.length" class="absolute left-3 top-3 flex flex-wrap gap-1">
        <span
          v-for="tag in dish.tags.slice(0,2)"
          :key="tag"
          class="rounded-full border border-slate-700/50 bg-slate-950/70 px-2 py-0.5 text-[10px] text-slate-300 backdrop-blur-sm"
        >{{ t(`dishPage.tag_${tag}`) }}</span>
      </div>
      <!-- Sold-out overlay -->
      <div v-if="isSoldOut" class="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-950/60 backdrop-blur-[1px]">
        <span class="rounded-full border border-red-500/60 bg-slate-950/80 px-3 py-1 text-xs font-bold text-red-300">{{ t('menu.soldOut') }}</span>
      </div>
    </div>

    <!-- Info + action -->
    <div class="space-y-3 p-4" @click.stop>
      <div class="space-y-1">
        <h3 class="text-base font-semibold leading-snug text-white">{{ dish.name }}</h3>
        <p v-if="dish.description" class="line-clamp-2 text-[13px] text-slate-400">{{ dish.description }}</p>
      </div>
      <!-- Qty stepper or Add -->
      <template v-if="canOrder">
        <div
          v-if="qtyInCart > 0"
          class="flex items-center justify-between rounded-full border px-3 py-1.5"
          style="border-color: rgba(245,158,11,0.40); background: rgba(245,158,11,0.06)"
          @click.stop
        >
          <button class="flex h-6 w-6 items-center justify-center transition active:scale-90" style="color:var(--color-secondary)" :aria-label="t('common.decreaseQty')" @click.stop="handleDecrement">
            <AppIcon name="minus" class="h-3.5 w-3.5" />
          </button>
          <span class="text-sm font-bold tabular-nums" style="color:var(--color-secondary)">{{ qtyInCart }}</span>
          <button class="flex h-6 w-6 items-center justify-center transition active:scale-90" style="color:var(--color-secondary)" :aria-label="t('common.increaseQty')" @click.stop="handleAdd">
            <AppIcon name="plus" class="h-3.5 w-3.5" />
          </button>
        </div>
        <button v-else class="ui-btn-primary w-full justify-center gap-2 py-2 text-sm" @click.stop="handleAdd">
          <AppIcon name="plus" class="h-4 w-4" />
          {{ t('dishPage.add') }}
        </button>
      </template>
      <div v-else-if="isSoldOut" class="rounded-full border border-red-500/30 py-2 text-center text-sm font-medium text-red-400/80">
        {{ t('menu.soldOut') }}
      </div>
      <div v-else-if="isScheduleUnavailable" class="rounded-full border border-slate-700/50 py-2 text-center text-sm font-medium text-slate-500">
        {{ t('menu.notAvailableNow') }}
      </div>
    </div>
  </article>

  <!-- ══════════════════════════════════════════════════════
       COMPACT layout  —  single-line: name · price · add
       Great for drinks, sides, simple items
       ══════════════════════════════════════════════════════ -->
  <div
    v-else
    class="group flex cursor-pointer items-center gap-3 rounded-xl border border-slate-800/60 bg-slate-950/70 px-3 py-2.5 transition-colors duration-150 hover:border-slate-700/60 active:scale-[0.99] select-none"
    role="button"
    tabindex="0"
    :aria-label="dish.name"
    :class="{ 'opacity-60': isSoldOut || isScheduleUnavailable }"
    @click="handleOpen"
    @keydown.enter.space.prevent="handleOpen"
  >
    <!-- Tiny thumb -->
    <div v-if="dish.image_url" class="h-9 w-9 shrink-0 overflow-hidden rounded-lg">
      <img :src="dish.image_url" :alt="dish.name" class="h-full w-full object-cover" loading="lazy" decoding="async" @error="onImgError" />
    </div>
    <!-- Text -->
    <div class="min-w-0 flex-1">
      <div class="flex items-baseline gap-2">
        <h3 class="truncate text-sm font-medium text-white">{{ dish.name }}</h3>
        <span v-if="isSoldOut" class="shrink-0 text-[10px] text-red-400">{{ t('menu.soldOut') }}</span>
        <span v-else-if="isScheduleUnavailable" class="shrink-0 text-[10px] text-slate-500">{{ t('menu.notAvailableNow') }}</span>
      </div>
      <span class="text-xs font-semibold" style="color:var(--color-secondary)">{{ formatPrice(dish.price) }}</span>
    </div>
    <!-- Compact qty controls -->
    <div class="shrink-0" @click.stop>
      <div v-if="canOrder && qtyInCart > 0" class="flex items-center gap-1">
        <button
          class="flex h-6 w-6 items-center justify-center rounded-full border border-slate-700 text-slate-300 transition hover:border-amber-500/50 hover:text-amber-400 active:scale-90"
          :aria-label="t('common.decreaseQty')"
          @click.stop="handleDecrement"
        ><AppIcon name="minus" class="h-3 w-3" /></button>
        <span class="min-w-[1.25rem] text-center text-sm font-bold tabular-nums text-white">{{ qtyInCart }}</span>
        <button
          class="flex h-6 w-6 items-center justify-center rounded-full border border-amber-500/50 text-amber-400 transition hover:bg-amber-500/10 active:scale-90"
          :aria-label="t('common.increaseQty')"
          @click.stop="handleAdd"
        ><AppIcon name="plus" class="h-3 w-3" /></button>
      </div>
      <button
        v-else-if="canOrder"
        class="flex h-7 w-7 items-center justify-center rounded-full shadow-sm transition hover:brightness-110 active:scale-90"
        style="background-color:var(--color-secondary)"
        :aria-label="t('dishPage.add')"
        @click.stop="handleAdd"
      ><AppIcon name="plus" class="h-3.5 w-3.5 text-slate-950" /></button>
    </div>
  </div>

  <!-- Quick-add sheet for items that need a required choice (skips the full detail page) -->
  <Teleport to="body">
    <QuickAddSheet v-if="showQuickAdd" :dish="dish" :currency="currency" @close="showQuickAdd = false" />
  </Teleport>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from './AppIcon.vue'
import QuickAddSheet from './QuickAddSheet.vue'
import { useI18n } from '../composables/useI18n'
import { withImageFallback } from '../lib/images'
import { useCartStore } from '../stores/cart'
import { useToastStore } from '../stores/toast'

const props = defineProps({
  dish:         { type: Object,  required: true },
  /** 'row' (default) | 'card' | 'compact' */
  layout:       { type: String,  default: 'row' },
  categorySlug: { type: String,  required: true },
  currency:     { type: String,  default: 'MAD' },
  isBrowseOnly: { type: Boolean, default: false },
  isOpen:       { type: Boolean, default: true },
})

const router = useRouter()
const cart   = useCartStore()
const toast  = useToastStore()
const { t, formatPrice } = useI18n()

// ── Availability states ─────────────────────────────────────────────────────
const isSoldOut          = computed(() => props.dish.is_available === false)
const isScheduleUnavailable = computed(() => props.dish.is_schedule_available === false)

/** True when the customer can actually add this item */
const canOrder = computed(
  () => !props.isBrowseOnly && props.isOpen && !isSoldOut.value && !isScheduleUnavailable.value
)

/** True when navigating to detail page is mandatory (has required option groups/options) */
const needsDetailPage = computed(() => {
  const hasRequiredGroups  = (props.dish.option_groups || []).some(g => g.min_select > 0)
  const hasRequiredOptions = (props.dish.options       || []).some(o => o.is_required)
  return hasRequiredGroups || hasRequiredOptions
})

// Quick-add sheet handles the common case (a few option groups); complex dishes
// (more than 3 groups) still get the full detail page.
const showQuickAdd = ref(false)
const useQuickAdd = computed(() => needsDetailPage.value && (props.dish.option_groups || []).length <= 3)

// ── Cart integration ────────────────────────────────────────────────────────
/** Stable line key for a simple (no-option) cart entry */
const lineKey = computed(() => `${props.dish.slug}::`)

const qtyInCart = computed(() => {
  const item = cart.items.find(i => i.key === lineKey.value)
  return item ? item.qty : 0
})

// ── Handlers ────────────────────────────────────────────────────────────────
const handleOpen = () => {
  router.push({ name: 'dish', params: { category: props.categorySlug, dish: props.dish.slug } })
}

const handleAdd = () => {
  if (needsDetailPage.value) {
    if (useQuickAdd.value) { showQuickAdd.value = true } else { handleOpen() }
    return
  }
  cart.add({
    key:           lineKey.value,
    slug:          props.dish.slug,
    name:          props.dish.name,
    price:         Number(props.dish.price || 0),
    currency:      props.dish.currency || props.currency,
    qty:           1,
    note:          '',
    option_ids:    [],
    option_labels: [],
  })
  try { navigator.vibrate?.(12) } catch { /* not supported */ }
  toast.show(t('dishPage.addedToCart'), 'success')
}

const handleDecrement = () => {
  if (qtyInCart.value <= 0) return
  cart.decrement(lineKey.value)
}

const onImgError = (e) => withImageFallback(e)
</script>
