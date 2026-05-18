<template>
  <!-- ══════════════════════════════════════════════════════
       ROW layout  —  Wolt / Deliveroo mobile-first style
       Text left  ·  Square image right  ·  Add/qty overlay
       ══════════════════════════════════════════════════════ -->
  <article
    v-if="layout === 'row'"
    class="ui-dish-row group relative flex overflow-hidden rounded-2xl border border-slate-800/70 bg-slate-950/80 transition-colors duration-200 active:scale-[0.99] cursor-pointer select-none"
    :class="{ 'opacity-60': isSoldOut || isScheduleUnavailable }"
    role="button"
    :aria-label="dish.name"
    @click="handleOpen"
  >
    <!-- Left: text -->
    <div class="flex min-w-0 flex-1 flex-col justify-between gap-2 py-3 pl-3 pr-2">
      <div class="space-y-1">
        <h3 class="line-clamp-2 text-sm font-semibold leading-snug text-white">{{ dish.name }}</h3>
        <p v-if="dish.description" class="line-clamp-2 text-[12px] leading-relaxed text-slate-400">{{ dish.description }}</p>
      </div>
      <div class="flex flex-wrap items-center gap-1.5">
        <span class="text-sm font-bold" style="color:var(--color-secondary)">{{ formatCurrency(dish.price, currency) }}</span>
        <span
          v-for="tag in (dish.tags || []).slice(0, 2)"
          :key="tag"
          class="rounded-full border border-slate-700/60 px-1.5 py-0.5 text-[10px] text-slate-400"
        >{{ t(`dishPage.tag_${tag}`) }}</span>
        <span v-if="isSoldOut"         class="rounded-full border border-red-500/40 bg-red-500/10 px-1.5 py-0.5 text-[10px] text-red-300">{{ t('menu.soldOut') }}</span>
        <span v-else-if="isScheduleUnavailable" class="rounded-full border border-slate-700/50 px-1.5 py-0.5 text-[10px] text-slate-500">{{ t('menu.notAvailableNow') }}</span>
      </div>
    </div>

    <!-- Right: square image + add controls -->
    <div class="relative h-28 w-28 shrink-0 sm:h-32 sm:w-32">
      <img
        v-if="dish.image_url"
        :src="dish.image_url"
        :alt="dish.name"
        class="h-full w-full object-cover"
        loading="lazy"
        decoding="async"
        @error="onImgError"
      />
      <div v-else class="ui-menu-dish-placeholder flex h-full w-full items-center justify-center bg-slate-900/80">
        <AppIcon name="menu" class="h-8 w-8 text-slate-700" />
      </div>
      <!-- subtle left-edge blend -->
      <div class="pointer-events-none absolute inset-0 bg-gradient-to-r from-slate-950/30 to-transparent" />

      <!-- Add / qty controls overlaid at bottom-right -->
      <div v-if="canOrder" class="absolute bottom-2 right-2 z-10" @click.stop>
        <!-- qty stepper when already in cart -->
        <div
          v-if="qtyInCart > 0"
          class="flex items-center gap-0.5 rounded-full border border-amber-500/40 bg-slate-950/92 px-1 py-0.5 shadow-xl backdrop-blur"
        >
          <button
            class="flex h-6 w-6 items-center justify-center rounded-full text-amber-400 transition hover:bg-amber-500/10 active:scale-90"
            aria-label="Decrease"
            @click.stop="handleDecrement"
          ><AppIcon name="minus" class="h-3 w-3" /></button>
          <span class="min-w-[1rem] text-center text-xs font-bold text-white tabular-nums">{{ qtyInCart }}</span>
          <button
            class="flex h-6 w-6 items-center justify-center rounded-full text-amber-400 transition hover:bg-amber-500/10 active:scale-90"
            aria-label="Increase"
            @click.stop="handleAdd"
          ><AppIcon name="plus" class="h-3 w-3" /></button>
        </div>
        <!-- plain + button -->
        <button
          v-else
          class="flex h-7 w-7 items-center justify-center rounded-full shadow-xl transition hover:brightness-110 active:scale-90"
          style="background-color:var(--color-secondary)"
          aria-label="Add to cart"
          @click.stop="handleAdd"
        ><AppIcon name="plus" class="h-4 w-4 text-slate-950" /></button>
      </div>
    </div>
  </article>

  <!-- ══════════════════════════════════════════════════════
       CARD layout  —  image-top grid card (current style)
       ══════════════════════════════════════════════════════ -->
  <article
    v-else-if="layout === 'card'"
    class="group ui-menu-dish-card overflow-hidden rounded-[1.8rem] border border-slate-800/80 bg-slate-950/82 shadow-[0_20px_50px_rgba(2,6,23,0.36)] transition-all duration-300 hover:border-slate-700/80 cursor-pointer"
    role="button"
    :aria-label="dish.name"
    @click="handleOpen"
  >
    <!-- Image -->
    <div class="relative aspect-[4/3] overflow-hidden bg-slate-900">
      <img
        v-if="dish.image_url"
        :src="dish.image_url"
        :alt="dish.name"
        class="h-full w-full object-cover transition duration-500 group-hover:scale-[1.04]"
        loading="lazy"
        decoding="async"
        @error="onImgError"
      />
      <div v-else class="ui-menu-dish-placeholder absolute inset-0 flex items-center justify-center bg-slate-900">
        <AppIcon name="menu" class="h-12 w-12 text-slate-700" />
      </div>
      <div class="pointer-events-none absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/20 to-transparent" />
      <!-- Price badge top-right -->
      <div class="absolute right-3 top-3">
        <span class="rounded-full px-3 py-1 text-xs font-bold text-slate-950 shadow-lg" style="background-color:var(--color-secondary)">
          {{ formatCurrency(dish.price, currency) }}
        </span>
      </div>
      <!-- Sold-out overlay -->
      <div v-if="isSoldOut" class="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-950/60">
        <span class="rounded-full border border-red-500/60 bg-slate-950/80 px-3 py-1 text-xs font-bold text-red-300">{{ t('menu.soldOut') }}</span>
      </div>
    </div>

    <!-- Info + action -->
    <div class="space-y-3 p-4" @click.stop>
      <div class="space-y-1">
        <h3 class="text-base font-semibold leading-snug text-white">{{ dish.name }}</h3>
        <p v-if="dish.description" class="line-clamp-2 text-sm text-slate-400">{{ dish.description }}</p>
      </div>
      <div v-if="dish.tags?.length" class="flex flex-wrap gap-1">
        <span v-for="tag in dish.tags" :key="tag" class="rounded-full border border-slate-700/60 px-2 py-0.5 text-[10px] text-slate-400">{{ t(`dishPage.tag_${tag}`) }}</span>
      </div>
      <!-- Qty stepper or Add -->
      <template v-if="canOrder">
        <div
          v-if="qtyInCart > 0"
          class="flex items-center justify-between rounded-full border border-amber-500/30 bg-slate-900/60 px-3 py-1.5"
          @click.stop
        >
          <button class="flex h-6 w-6 items-center justify-center text-amber-400 transition active:scale-90" @click.stop="handleDecrement">
            <AppIcon name="minus" class="h-3.5 w-3.5" />
          </button>
          <span class="text-sm font-bold tabular-nums text-white">{{ qtyInCart }}</span>
          <button class="flex h-6 w-6 items-center justify-center text-amber-400 transition active:scale-90" @click.stop="handleAdd">
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
    :aria-label="dish.name"
    :class="{ 'opacity-60': isSoldOut || isScheduleUnavailable }"
    @click="handleOpen"
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
      <span class="text-xs font-semibold" style="color:var(--color-secondary)">{{ formatCurrency(dish.price, currency) }}</span>
    </div>
    <!-- Compact qty controls -->
    <div class="shrink-0" @click.stop>
      <div v-if="canOrder && qtyInCart > 0" class="flex items-center gap-1">
        <button
          class="flex h-6 w-6 items-center justify-center rounded-full border border-slate-700 text-slate-300 transition hover:border-amber-500/50 hover:text-amber-400 active:scale-90"
          @click.stop="handleDecrement"
        ><AppIcon name="minus" class="h-3 w-3" /></button>
        <span class="min-w-[1.25rem] text-center text-sm font-bold tabular-nums text-white">{{ qtyInCart }}</span>
        <button
          class="flex h-6 w-6 items-center justify-center rounded-full border border-amber-500/50 text-amber-400 transition hover:bg-amber-500/10 active:scale-90"
          @click.stop="handleAdd"
        ><AppIcon name="plus" class="h-3 w-3" /></button>
      </div>
      <button
        v-else-if="canOrder"
        class="flex h-7 w-7 items-center justify-center rounded-full shadow-sm transition hover:brightness-110 active:scale-90"
        style="background-color:var(--color-secondary)"
        @click.stop="handleAdd"
      ><AppIcon name="plus" class="h-3.5 w-3.5 text-slate-950" /></button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from './AppIcon.vue'
import { useI18n } from '../composables/useI18n'
import { withImageFallback } from '../lib/images'
import { useCartStore } from '../stores/cart'
import { useToastStore } from '../stores/toast'

const props = defineProps({
  dish:         { type: Object,  required: true },
  /** 'row' (default) | 'card' | 'compact' */
  layout:       { type: String,  default: 'row' },
  categorySlug: { type: String,  required: true },
  currency:     { type: String,  default: 'USD' },
  isBrowseOnly: { type: Boolean, default: false },
  isOpen:       { type: Boolean, default: true },
})

const router = useRouter()
const cart   = useCartStore()
const toast  = useToastStore()
const { t, formatCurrency } = useI18n()

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
  if (needsDetailPage.value) { handleOpen(); return }
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
