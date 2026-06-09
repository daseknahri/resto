<template>
  <div class="min-h-screen bg-slate-950 pb-32 ui-safe-bottom">
    <!-- Single max-width shell — all content lives inside this wrapper -->
    <div class="mx-auto max-w-3xl px-4">

    <!-- Back link -->
    <div class="pt-5">
      <router-link
        to="/order"
        class="inline-flex items-center gap-1 text-xs text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 rounded"
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" class="h-3.5 w-3.5 shrink-0 rtl:scale-x-[-1]" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10 12L6 8l4-4" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        {{ t('mktMenu.backToList') }}
      </router-link>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="py-5 space-y-5" aria-busy="true" :aria-label="t('common.loading')">
      <!-- Restaurant header skeleton -->
      <div class="ui-hero-ribbon animate-pulse flex items-start gap-4 p-4">
        <div class="h-16 w-16 shrink-0 rounded-xl bg-slate-800/70" />
        <div class="flex-1 space-y-2.5 pt-1">
          <div class="h-5 w-40 rounded-lg bg-slate-700/60" />
          <div class="h-3 w-56 rounded bg-slate-800/50" />
          <div class="flex gap-2">
            <div class="h-5 w-16 rounded-full bg-slate-800/50" />
            <div class="h-5 w-20 rounded-full bg-slate-800/40" />
          </div>
        </div>
      </div>
      <!-- Category + dish skeletons -->
      <div v-for="i in 2" :key="i" class="space-y-3">
        <div class="h-3.5 w-28 rounded bg-slate-700/50 animate-pulse" />
        <div v-for="j in 3" :key="j" class="ui-panel animate-pulse flex items-center justify-between gap-3 p-3">
          <div class="space-y-1.5">
            <div class="h-3.5 w-36 rounded bg-slate-700/60" />
            <div class="h-2.5 w-52 rounded bg-slate-800/50" />
            <div class="h-5 w-14 rounded-full bg-slate-700/40" />
          </div>
          <div class="h-14 w-14 shrink-0 rounded-xl bg-slate-800/60" />
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" role="alert" class="py-8">
      <div class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
        </svg>
        <p class="flex-1 text-sm text-red-300">{{ t('mktMenu.error') }}</p>
        <button
          class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10 ui-touch-target"
          @click="fetchMenu"
        >{{ t('common.retry') }}</button>
      </div>
    </div>

    <template v-else-if="restaurant">
      <!-- Restaurant header -->
      <div class="pt-4 pb-2">
        <header class="ui-hero-ribbon ui-reveal px-4 py-4">
          <div class="flex items-start gap-4">
            <!-- Logo -->
            <div class="h-16 w-16 shrink-0 rounded-xl overflow-hidden bg-slate-800 flex items-center justify-center">
              <img v-if="restaurant.logo_url" :src="restaurant.logo_url" :alt="restaurant.name" loading="eager" decoding="async" class="h-full w-full object-cover" @error="$event.target.style.display='none'" />
              <span v-else aria-hidden="true" class="text-2xl">🍽️</span>
            </div>
            <!-- Info -->
            <div class="flex-1 min-w-0">
              <p class="ui-kicker">{{ t('mktMenu.restaurantKicker') }}</p>
              <h1 class="ui-display text-xl font-semibold tracking-tight text-white leading-tight">{{ restaurant.name }}</h1>
              <p v-if="restaurant.tagline" class="mt-0.5 text-xs text-slate-400 line-clamp-1" :title="restaurant.tagline">{{ restaurant.tagline }}</p>
              <!-- Chips row -->
              <div class="mt-2 flex flex-wrap gap-1.5">
                <span
                  class="ui-status-pill"
                  :class="restaurant.is_open
                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                    : 'border-slate-700/60 bg-slate-800/50 text-slate-400'"
                >
                  <span
                    class="ui-live-dot"
                    :class="restaurant.is_open ? 'bg-emerald-400' : 'bg-slate-500'"
                    aria-hidden="true"
                  />
                  {{ restaurant.is_open ? t('mktMenu.open') : t('mktMenu.closed') }}
                </span>
                <!-- Rating chip -->
                <span v-if="restaurant.rating_average" class="ui-chip flex items-center gap-0.5 text-amber-400">
                  <svg viewBox="0 0 12 12" class="h-2.5 w-2.5 fill-current shrink-0" aria-hidden="true"><path d="M6 1l1.39 2.82 3.11.45-2.25 2.19.53 3.09L6 8.12 3.22 9.55l.53-3.09L1.5 4.27l3.11-.45z"/></svg>
                  <span class="tabular-nums">{{ restaurant.rating_average }}</span>
                  <span class="text-slate-500 tabular-nums">({{ restaurant.rating_count }})</span>
                </span>
                <span v-if="restaurant.cuisine_type" class="ui-chip">{{ restaurant.cuisine_type }}</span>
                <span v-if="restaurant.city" class="ui-chip">{{ restaurant.city }}</span>
                <span v-if="restaurant.delivery_enabled" class="ui-chip text-sky-300">
                  {{ t('mktMenu.deliveryFee') }}: {{ Number(restaurant.delivery_fee) > 0 ? fmtPrice(restaurant.delivery_fee) : t('mktMenu.freeDelivery') }}
                </span>
                <span
                  v-if="restaurant.delivery_enabled && Number(restaurant.delivery_minimum_order) > 0"
                  class="ui-chip"
                >
                  {{ t('mktMenu.minOrder', { amount: fmtPrice(restaurant.delivery_minimum_order) }) }}
                </span>
              </div>
            </div>
          </div>
        </header>
      </div>

      <!-- Flash sale banner -->
      <div
        v-if="restaurant.flash_sale"
        class="ui-reveal mx-4 mb-2 flex items-center justify-between gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-sm"
        :style="{ '--ui-delay': '40ms' }"
        role="status"
      >
        <p class="font-semibold text-amber-200">
          {{ t('mktMenu.flashSaleBanner', { pct: restaurant.flash_sale.discount_pct }) }}
        </p>
        <p v-if="flashSaleCountdown" class="shrink-0 font-mono text-[11px] tabular-nums text-amber-300/80">
          {{ t('mktMenu.flashSaleEnds', { time: flashSaleCountdown }) }}
        </p>
      </div>

      <!-- Loyalty points teaser — shown when signed in + loyalty enabled -->
      <div
        v-if="loyaltyConfig?.enabled && customerStore.isAuthenticated"
        class="ui-reveal mx-4 mb-2 flex items-center gap-2.5 rounded-xl border border-violet-500/25 bg-violet-500/8 px-4 py-2"
        :style="{ '--ui-delay': '70ms' }"
        role="note"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0 text-violet-400" aria-hidden="true">
          <path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z" />
        </svg>
        <div class="min-w-0 flex-1">
          <p class="text-[12px] font-semibold leading-tight text-violet-200">
            {{ loyaltyPoints > 0 ? t('mktMenu.loyaltyTeaserPts', { points: loyaltyPoints }) : t('mktMenu.loyaltyTeaserEarn') }}
          </p>
          <p v-if="loyaltyAvailable" class="text-[10px] leading-tight text-violet-400/80">{{ t('mktMenu.loyaltyTeaserRedeem') }}</p>
        </div>
        <span
          v-if="loyaltyPoints > 0"
          class="shrink-0 rounded-full border border-violet-500/20 bg-violet-500/15 px-2 py-0.5 text-[11px] font-bold tabular-nums text-violet-300"
        >{{ loyaltyPoints }}</span>
      </div>

      <!-- Customer reviews — horizontal scroll, only shown when restaurant has review comments -->
      <div
        v-if="restaurant.recent_reviews?.length"
        class="ui-reveal mb-2 space-y-2"
        :style="{ '--ui-delay': '90ms' }"
      >
        <p class="ui-kicker px-4">{{ t('mktMenu.reviewsTitle') }}</p>
        <div class="flex gap-2.5 overflow-x-auto px-4 pb-0.5 snap-x">
          <div
            v-for="(review, idx) in restaurant.recent_reviews"
            :key="idx"
            class="w-56 shrink-0 snap-start rounded-xl border border-slate-800/70 bg-slate-900/50 px-3 py-2.5 space-y-1"
          >
            <div class="flex items-center gap-0.5 text-amber-400 text-[11px]">
              <span aria-label="`${review.score} stars`">{{ '★'.repeat(review.score) }}<span class="opacity-25">{{ '★'.repeat(5 - review.score) }}</span></span>
            </div>
            <p class="line-clamp-3 text-[11px] leading-relaxed text-slate-300">{{ review.comment }}</p>
          </div>
        </div>
      </div>

      <!-- Sticky horizontal category navigation -->
      <nav
        class="sticky top-0 z-20 -mx-4 mt-1 border-b border-slate-800/50 bg-slate-950/95 backdrop-blur-md"
        :class="allCategories.length > 1 ? 'mb-2' : 'mb-1'"
        aria-label="Menu categories"
        style="scrollbar-width: none; -webkit-overflow-scrolling: touch;"
      >
        <div v-if="allCategories.length > 1" class="flex gap-1.5 overflow-x-auto px-4 py-2" style="scrollbar-width: none;">
          <button
            v-for="cat in allCategories"
            :key="cat.id"
            type="button"
            class="shrink-0 whitespace-nowrap rounded-full px-3 py-1.5 text-[11px] font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
            :class="activeCatId === cat.id
              ? 'bg-[var(--color-secondary)] text-slate-950 shadow-sm shadow-[var(--color-secondary)]/30'
              : 'border border-slate-700/70 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
            @click="scrollToCategory(cat.id)"
          >
            {{ cat.name }}
          </button>
        </div>
        <!-- Search strip -->
        <div class="border-t border-slate-800/40 px-4 py-2">
          <div class="relative flex items-center">
            <span class="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden="true">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5"><circle cx="6.5" cy="6.5" r="4"/><path d="M10.5 10.5 14 14"/></svg>
            </span>
            <input
              v-model="mktSearchQuery"
              type="search"
              :placeholder="t('mktMenu.searchPlaceholder')"
              :aria-label="t('mktMenu.search')"
              class="w-full rounded-xl border border-slate-700/60 bg-slate-900/60 py-1.5 ps-8 pe-8 text-[13px] text-slate-200 placeholder-slate-500 outline-none transition-colors focus:border-[color:var(--color-secondary)]/50 focus:ring-1 focus:ring-[color:var(--color-secondary)]/25 [&::-webkit-search-cancel-button]:hidden"
            />
            <button
              v-if="isMktSearchActive"
              type="button"
              class="absolute end-2.5 top-1/2 -translate-y-1/2 rounded-full p-0.5 text-slate-500 transition-colors hover:text-slate-300"
              :aria-label="t('mktMenu.searchClear')"
              @click="mktSearchQuery = ''"
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-3.5 w-3.5" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>
            </button>
          </div>
        </div>
      </nav>

      <!-- Menu -->
      <main class="space-y-8">

        <!-- ── Search results (query active) ─────────────────────────────── -->
        <template v-if="isMktSearchActive">
          <template v-if="mktSearchResults.length">
            <p class="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
              {{ t('mktMenu.searchResultsKicker') }}
              <span class="ms-1.5 font-normal normal-case tabular-nums text-slate-600">({{ mktTotalSearchCount }})</span>
            </p>
            <div v-for="group in mktSearchResults" :key="group.catName" class="space-y-2.5">
              <h2 class="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
                <span class="h-px w-4 shrink-0 rounded-full" style="background:var(--color-secondary)" aria-hidden="true" />
                {{ group.catName }}
              </h2>
              <article
                v-for="dish in group.dishes"
                :key="dish.slug"
                class="ui-panel ui-surface-lift group flex items-start gap-3.5 p-3.5"
                :class="{ 'opacity-50': !dish.is_available }"
              >
                <div class="h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-slate-800/50 flex items-center justify-center">
                  <img v-if="dish.image_url" :src="dish.image_url" :alt="dish.name" loading="lazy" decoding="async" class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" @error="$event.target.style.display='none'" />
                  <span v-else aria-hidden="true" class="text-2xl select-none">🍴</span>
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-semibold text-slate-100 leading-snug" :title="dish.name">{{ dish.name }}</p>
                  <p v-if="dish.description" class="mt-0.5 text-xs text-slate-500 line-clamp-2 leading-relaxed" :title="dish.description">{{ dish.description }}</p>
                  <div class="mt-2 flex items-center justify-between gap-2">
                    <span class="text-sm font-bold tabular-nums text-[var(--color-secondary)]">{{ fmtPrice(dish.price) }}</span>
                    <button
                      v-if="dish.is_available"
                      class="ui-press inline-flex items-center gap-1.5 rounded-full bg-[var(--color-secondary)] px-3.5 py-1.5 text-xs font-bold text-slate-950 transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50 ui-touch-target"
                      :aria-label="`${t('mktMenu.addToCart')} ${dish.name}`"
                      @click="addToCart(dish)"
                    >
                      <svg viewBox="0 0 12 12" class="h-3 w-3 shrink-0" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none" aria-hidden="true"><path d="M6 1v10M1 6h10"/></svg>
                      {{ t('mktMenu.addToCart') }}
                      <span v-if="cartQty(dish.slug)" class="ms-0.5 rounded-full bg-slate-950/25 px-1.5 tabular-nums text-[10px]" aria-hidden="true">{{ cartQty(dish.slug) }}</span>
                    </button>
                  </div>
                </div>
              </article>
            </div>
          </template>
          <div
            v-else
            class="flex flex-col items-center gap-3 rounded-2xl border border-slate-800/50 bg-slate-900/30 px-4 py-12 text-center"
          >
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" class="h-10 w-10 text-slate-700" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.25"/><path d="M13 13 17 17"/></svg>
            <p class="text-sm font-medium text-slate-400">{{ t('mktMenu.noMatchDish') }}</p>
            <button type="button" class="text-xs text-slate-500 underline transition-colors hover:text-slate-300" @click="mktSearchQuery = ''">{{ t('mktMenu.searchClear') }}</button>
          </div>
        </template>

        <!-- ── Normal category sections (search inactive) ─────────────────── -->
        <template v-else>
          <!-- Empty menu state -->
          <div
            v-if="!restaurant.super_categories?.length"
            class="ui-empty-state text-center space-y-1"
          >
            <p class="text-sm font-semibold text-slate-100">{{ t('mktMenu.menuEmpty') }}</p>
            <p class="text-xs text-slate-400">{{ t('mktMenu.menuEmptyBody') }}</p>
          </div>

          <div
            v-for="sc in restaurant.super_categories"
            :key="sc.id"
          >
            <p class="ui-kicker mb-2">{{ sc.name }}</p>
            <div
              v-for="cat in sc.categories"
              :id="`mkt-cat-${cat.id}`"
              :key="cat.id"
              :data-mkt-cat="cat.id"
              class="mb-6 scroll-mt-16"
            >
              <h2 class="mb-2.5 text-sm font-semibold text-slate-300">{{ cat.name }}</h2>
              <div class="space-y-2.5">
                <article
                  v-for="(dish, dishIndex) in cat.dishes"
                  :key="dish.slug"
                  class="ui-panel ui-surface-lift ui-reveal group flex items-start gap-3.5 p-3.5"
                  :class="{ 'opacity-50': !dish.is_available }"
                  :style="{ '--ui-delay': `${Math.min(dishIndex, 9) * 28}ms` }"
                >
                  <!-- Image (larger, with hover scale + emoji fallback) -->
                  <div class="h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-slate-800/50 flex items-center justify-center">
                    <img
                      v-if="dish.image_url"
                      :src="dish.image_url"
                      :alt="dish.name"
                      loading="lazy"
                      decoding="async"
                      class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                      @error="$event.target.style.display='none'"
                    />
                    <span v-else aria-hidden="true" class="text-2xl select-none">🍴</span>
                  </div>
                  <!-- Info -->
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-semibold text-slate-100 leading-snug" :title="dish.name">{{ dish.name }}</p>
                    <p v-if="dish.description" class="mt-0.5 text-xs text-slate-500 line-clamp-2 leading-relaxed" :title="dish.description">{{ dish.description }}</p>
                    <div class="mt-2 flex items-center justify-between gap-2">
                      <span class="text-sm font-bold tabular-nums text-[var(--color-secondary)]">
                        {{ fmtPrice(dish.price) }}
                      </span>
                      <button
                        v-if="dish.is_available"
                        class="ui-press inline-flex items-center gap-1.5 rounded-full bg-[var(--color-secondary)] px-3.5 py-1.5 text-xs font-bold text-slate-950 transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50 ui-touch-target"
                        :aria-label="`${t('mktMenu.addToCart')} ${dish.name}`"
                        @click="addToCart(dish)"
                      >
                        <svg viewBox="0 0 12 12" class="h-3 w-3 shrink-0" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none" aria-hidden="true"><path d="M6 1v10M1 6h10"/></svg>
                        {{ t('mktMenu.addToCart') }}
                        <span v-if="cartQty(dish.slug)" class="ms-0.5 rounded-full bg-slate-950/25 px-1.5 tabular-nums text-[10px]" aria-hidden="true">{{ cartQty(dish.slug) }}</span>
                      </button>
                    </div>
                  </div>
                </article>
              </div>
            </div>
          </div>
        </template>
      </main>
    </template>

    </div><!-- /max-w-3xl shell -->

    <!-- Cart bottom bar (visible when cart has items) -->
    <button
      v-if="cart.length && !checkoutOpen"
      ref="checkoutTriggerRef"
      class="ui-cart-bar ui-press fixed bottom-0 inset-x-3 z-30 mx-auto w-[calc(100%-1.5rem)] max-w-md rounded-2xl px-6 py-3.5 text-sm font-bold text-white flex items-center justify-between focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
      style="margin-bottom: calc(var(--safe-bottom) + 1rem)"
      :aria-label="`${t('mktMenu.checkout')} · ${fmtPrice(cartTotal)}`"
      @click="checkoutOpen = true"
    >
      <span class="rounded-full bg-[var(--color-secondary)]/20 px-2 py-0.5 text-xs tabular-nums text-[var(--color-secondary)]" aria-hidden="true">{{ cartTotalQty }}</span>
      <span>{{ t('mktMenu.checkout') }}</span>
      <span class="tabular-nums text-[var(--color-secondary)]">{{ fmtPrice(cartTotal) }}</span>
    </button>

    <!-- Checkout drawer -->
    <Transition name="slide-up">
      <div
        v-if="checkoutOpen"
        ref="checkoutDialogRef"
        role="dialog"
        aria-modal="true"
        aria-labelledby="marketplace-menu-checkout-dialog-title"
        class="fixed inset-0 z-40 flex flex-col bg-slate-950/95 backdrop-blur-sm overflow-y-auto"
        @keydown.esc="checkoutOpen = false"
      >
        <div class="mx-auto w-full max-w-md px-4 py-6 space-y-5">
          <!-- Header -->
          <div class="flex items-center justify-between">
            <h2 id="marketplace-menu-checkout-dialog-title" class="text-base font-bold text-white">{{ t('mktMenu.yourOrder') }}</h2>
            <button
              class="ui-press ui-touch-target flex items-center justify-center rounded-xl border border-slate-700/60 bg-slate-900/60 text-slate-400 transition-colors hover:border-slate-600 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
              :aria-label="t('common.close')"
              @click="checkoutOpen = false"
            >
              <svg aria-hidden="true" viewBox="0 0 16 16" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 4l8 8M12 4l-8 8" stroke-linecap="round" />
              </svg>
            </button>
          </div>

          <!-- Cart items -->
          <div class="space-y-2">
            <article
              v-for="item in cart"
              :key="item.slug"
              class="relative flex items-center gap-3 overflow-hidden rounded-xl border border-slate-800/60 bg-slate-900/60 py-2.5 ps-3.5 pe-2.5"
            >
              <!-- left accent bar -->
              <div
                class="pointer-events-none absolute inset-y-0 start-0 w-[3px] rounded-s-xl"
                style="background: linear-gradient(to bottom, rgba(245,158,11,0.55), rgba(245,158,11,0.10))"
              />
              <!-- info -->
              <div class="flex-1 min-w-0 space-y-0.5">
                <p class="truncate text-sm font-semibold leading-snug text-slate-100" :title="item.name">{{ item.name }}</p>
                <p class="text-xs tabular-nums">
                  <span class="font-semibold text-[var(--color-secondary)]">{{ fmtPrice(item.price * item.qty) }}</span>
                  <span class="text-slate-500"> · {{ fmtPrice(item.price) }} ea.</span>
                </p>
              </div>
              <!-- stepper pill -->
              <div class="inline-flex shrink-0 items-center gap-0.5 rounded-full border border-slate-700/60 bg-slate-900/70 px-0.5">
                <button
                  class="ui-press flex h-10 w-10 items-center justify-center rounded-full text-slate-400 transition hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
                  :aria-label="`${t('dishPage.decreaseQuantity')} ${item.name}`"
                  @click="removeFromCart(item.slug)"
                >
                  <svg viewBox="0 0 12 12" class="h-3 w-3 shrink-0" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none" aria-hidden="true"><path d="M2 6h8"/></svg>
                </button>
                <span class="min-w-[1.25rem] text-center text-sm font-bold tabular-nums text-white" aria-live="polite" aria-atomic="true">{{ item.qty }}</span>
                <button
                  class="ui-press flex h-10 w-10 items-center justify-center rounded-full text-slate-400 transition hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
                  :aria-label="`${t('dishPage.increaseQuantity')} ${item.name}`"
                  @click="addToCartBySlug(item.slug)"
                >
                  <svg viewBox="0 0 12 12" class="h-3 w-3 shrink-0" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none" aria-hidden="true"><path d="M6 1v10M1 6h10"/></svg>
                </button>
              </div>
            </article>
          </div>

          <!-- Fulfillment type -->
          <div>
            <p class="text-xs font-medium text-slate-400 mb-1.5">{{ t('mktMenu.fulfillmentLabel') }}</p>
            <div class="flex gap-2">
              <button
                class="flex-1 rounded-xl border py-2.5 text-xs font-medium transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
                :class="form.fulfillment_type === 'pickup'
                  ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                :aria-pressed="form.fulfillment_type === 'pickup'"
                @click="form.fulfillment_type = 'pickup'"
              >{{ t('mktMenu.fulfillmentPickup') }}</button>
              <button
                v-if="restaurant?.delivery_enabled"
                class="flex-1 rounded-xl border py-2.5 text-xs font-medium transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40"
                :class="form.fulfillment_type === 'delivery'
                  ? 'border-sky-500/60 bg-sky-500/10 text-sky-300'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500'"
                :aria-pressed="form.fulfillment_type === 'delivery'"
                @click="form.fulfillment_type = 'delivery'"
              >{{ t('mktMenu.fulfillmentDelivery') }}</button>
            </div>
          </div>

          <!-- Customer info -->
          <div class="space-y-3">
            <div>
              <label for="mkt-name" class="block text-xs font-medium text-slate-400 mb-1">
                {{ t('mktMenu.customerName') }}
              </label>
              <input
                id="mkt-name"
                v-model="form.customer_name"
                type="text"
                autocomplete="name"
                aria-required="true"
                class="ui-input"
              />
            </div>
            <div>
              <label for="mkt-phone" class="block text-xs font-medium text-slate-400 mb-1">
                {{ t('mktMenu.customerPhone') }}
              </label>
              <input
                id="mkt-phone"
                v-model="form.customer_phone"
                type="tel"
                inputmode="tel"
                autocomplete="tel"
                class="ui-input"
              />
            </div>
            <div v-if="form.fulfillment_type === 'delivery'" class="space-y-2">
              <div>
                <label for="mkt-address" class="block text-xs font-medium text-slate-400 mb-1">
                  {{ t('mktMenu.deliveryAddress') }}
                </label>
                <textarea
                  id="mkt-address"
                  v-model="form.delivery_address"
                  rows="2"
                  class="ui-textarea resize-none"
                />
              </div>
              <!-- Coordinates → distance-based fee -->
              <button
                type="button"
                class="ui-press inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-[11px] font-medium text-slate-300 transition-colors hover:border-slate-600 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
                :disabled="locatingMkt"
                :aria-busy="locatingMkt"
                @click="useMyLocation"
              >
                <svg v-if="locatingMkt" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                <AppIcon v-else name="location" class="h-3 w-3 shrink-0" aria-hidden="true" />
                {{ locatingMkt ? t('mktMenu.locating') : (form.delivery_lat ? t('mktMenu.locationSet') : t('mktMenu.useMyLocation')) }}
              </button>
              <p v-if="locateError" class="text-[11px] text-rose-300" role="alert">{{ locateError }}</p>
              <p v-if="deliveryOutOfRange" class="flex items-start gap-1.5 text-[11px] text-rose-300" role="alert">
                <AppIcon name="info" class="h-3 w-3 shrink-0 mt-px" aria-hidden="true" />
                {{ t('mktMenu.deliveryOutOfRange', { km: deliveryPricing.radiusKm }) }}
              </p>
              <p v-else-if="deliveryFeeIsDistance" class="flex items-center gap-1.5 text-[11px] text-slate-400">
                <AppIcon name="location" class="h-3 w-3 shrink-0" aria-hidden="true" />
                {{ t('mktMenu.deliveryFeeDistance', { fee: fmtPrice(deliveryFee), km: deliveryDistanceKm }) }}
              </p>
              <p v-else-if="deliveryPricing.perKm > 0" class="flex items-center gap-1.5 text-[11px] text-slate-400">
                <AppIcon name="location" class="h-3 w-3 shrink-0" aria-hidden="true" />
                {{ t('mktMenu.deliveryFeeByDistance') }}
              </p>
            </div>
            <div>
              <label for="mkt-note" class="block text-xs font-medium text-slate-400 mb-1">
                {{ t('mktMenu.note') }}
              </label>
              <input
                id="mkt-note"
                v-model="form.customer_note"
                type="text"
                class="ui-input"
              />
            </div>
            <!-- When: ASAP vs scheduled -->
            <div>
              <p class="text-xs font-medium text-slate-400 mb-1.5">{{ t('mktMenu.whenTitle') }}</p>
              <div class="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  class="rounded-xl border px-3 py-2.5 text-xs font-semibold transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
                  :class="!scheduleEnabled ? 'border-emerald-500/55 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-600'"
                  :aria-pressed="!scheduleEnabled"
                  @click="scheduleEnabled = false"
                >{{ t('mktMenu.scheduleAsap') }}</button>
                <button
                  type="button"
                  class="rounded-xl border px-3 py-2.5 text-xs font-semibold transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
                  :class="scheduleEnabled ? 'border-emerald-500/55 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-600'"
                  :aria-pressed="scheduleEnabled"
                  @click="scheduleEnabled = true"
                >{{ t('mktMenu.scheduleLater') }}</button>
              </div>
              <input
                v-if="scheduleEnabled"
                v-model="scheduledFor"
                type="datetime-local"
                :min="minScheduleDatetime"
                class="ui-input mt-2"
              />
              <p v-if="scheduleEnabled" class="mt-1 text-[11px] text-slate-500">{{ t('mktMenu.scheduleHint') }}</p>
            </div>
          </div>

          <!-- Loyalty redemption -->
          <label
            v-if="loyaltyAvailable"
            class="flex cursor-pointer items-center gap-2.5 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3"
          >
            <input v-model="useLoyalty" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-amber-500 focus:ring-amber-500/40" />
            <span class="flex-1 text-xs text-amber-200">{{ t('mktMenu.loyaltyRedeem', { points: loyaltyPoints }) }}</span>
            <span v-if="useLoyalty && loyaltyDiscount > 0" class="text-xs font-semibold tabular-nums text-amber-300">-{{ fmtPrice(loyaltyDiscount) }}</span>
          </label>

          <!-- Pay now from wallet (marketplace orders are pay-now) -->
          <div
            v-if="customerStore.isAuthenticated && orderTotal > 0"
            class="ui-panel rounded-xl border px-4 py-3"
            :class="walletCoversTotal ? 'border-emerald-500/30 bg-emerald-500/8' : 'border-amber-500/40 bg-amber-500/8'"
          >
            <p class="text-sm font-semibold" :class="walletCoversTotal ? 'text-emerald-300' : 'text-amber-300'">
              {{ t('mktMenu.payFromWalletTitle') }}
            </p>
            <p class="text-xs text-slate-400">{{ t('mktMenu.walletBalanceLine', { balance: `${customer?.wallet_balance || 0} ${restaurant?.currency}` }) }}</p>
            <p v-if="!walletCoversTotal" class="mt-1 text-xs text-amber-200">
              {{ t('mktMenu.walletShortNotice', { amount: fmtPrice(orderTotal - walletBalanceNum) }) }}
            </p>
          </div>

          <!-- Totals -->
          <div class="ui-panel px-4 py-3 space-y-1.5 text-sm">
            <div class="flex justify-between text-slate-400">
              <span>{{ t('mktMenu.subtotal') }}</span>
              <span class="tabular-nums">{{ fmtPrice(cartTotal) }}</span>
            </div>
            <div v-if="form.fulfillment_type === 'delivery'" class="flex justify-between text-slate-400">
              <span>
                {{ t('mktMenu.deliveryFeeLabel') }}
                <span v-if="deliveryFeeIsDistance" class="text-[11px] text-slate-500 tabular-nums">· {{ deliveryDistanceKm }} km</span>
              </span>
              <span class="tabular-nums">{{ deliveryIsFree ? t('mktMenu.freeDelivery') : fmtPrice(deliveryFee) }}</span>
            </div>
            <div v-if="flashSaleDiscount > 0" class="flex justify-between text-amber-300">
              <span>{{ t('mktMenu.flashDiscount', { pct: restaurant.flash_sale.discount_pct }) }}</span>
              <span class="tabular-nums">-{{ fmtPrice(flashSaleDiscount) }}</span>
            </div>
            <div v-if="loyaltyDiscount > 0" class="flex justify-between text-amber-300">
              <span>{{ t('mktMenu.loyaltyDiscount') }}</span>
              <span class="tabular-nums">-{{ fmtPrice(loyaltyDiscount) }}</span>
            </div>
            <div class="flex justify-between font-bold text-white border-t border-slate-800 pt-1.5 mt-1.5">
              <span>{{ t('mktMenu.total') }}</span>
              <span class="tabular-nums">{{ fmtPrice(orderTotal) }}</span>
            </div>
          </div>

          <!-- Error -->
          <div v-if="checkoutError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
            <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-sm text-red-300">{{ checkoutError }}</p>
          </div>

          <!-- Submit -->
          <button
            class="ui-press inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-[var(--color-secondary)] py-3.5 text-sm font-bold text-slate-950 transition-opacity hover:opacity-90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
            :disabled="placing || prepayShortfall || deliveryBlocked"
            :aria-busy="placing"
            @click="placeOrder"
          >
            <svg v-if="placing" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ placing ? t('mktMenu.placing') : (deliveryBlocked ? t('mktMenu.deliveryOutOfRangeShort') : (prepayShortfall ? t('mktMenu.walletTopUpRequiredShort') : t('mktMenu.placeOrder'))) }}
          </button>
        </div>
      </div>
    </Transition>

    <!-- Inline sign-in modal — triggered when a delivery order requires auth -->
    <CustomerAuthModal
      v-if="showAuthModal"
      @close="showAuthModal = false"
      @authenticated="onAuthenticated"
    />

  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from '../composables/useI18n';
import { useCustomerStore } from '../stores/customer';
import CustomerAuthModal from '../components/CustomerAuthModal.vue';
import api from '../lib/api';

const { t, currentLocale } = useI18n();
const route = useRoute();
const router = useRouter();
const customerStore = useCustomerStore();

const slug = route.params.slug;

// ── State ─────────────────────────────────────────────────────────────────────
const loading = ref(true);
const fetchError = ref(false);
const restaurant = ref(null);

// ── Flash sale countdown ───────────────────────────────────────────────────────
const flashSaleCountdown = ref('');
let _flashSaleTimer = null;
const updateFlashSaleCountdown = () => {
  if (!restaurant.value?.flash_sale?.active_until) { flashSaleCountdown.value = ''; return; }
  const until = new Date(restaurant.value.flash_sale.active_until);
  const diff = until - Date.now();
  if (diff <= 0) {
    flashSaleCountdown.value = '';
    restaurant.value = { ...restaurant.value, flash_sale: null };
    return;
  }
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  if (h >= 24) { flashSaleCountdown.value = ''; return; }
  flashSaleCountdown.value = h > 0
    ? `${h}h ${String(m).padStart(2, '0')}m`
    : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
};
watch(
  () => restaurant.value?.flash_sale,
  (sale) => {
    clearInterval(_flashSaleTimer);
    if (sale?.active_until) {
      updateFlashSaleCountdown();
      _flashSaleTimer = setInterval(updateFlashSaleCountdown, 1000);
    }
  },
  { immediate: true },
);

const checkoutOpen = ref(false);
const checkoutDialogRef = ref(null);
// Ref to the element that opened the checkout drawer — used to restore focus on close.
const checkoutTriggerRef = ref(null);

const FOCUSABLE_CO = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapCheckoutFocus = (e) => {
  if (!checkoutDialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(checkoutDialogRef.value.querySelectorAll(FOCUSABLE_CO));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

watch(checkoutOpen, async (open) => {
  if (open) {
    await nextTick();
    checkoutDialogRef.value?.querySelector(FOCUSABLE_CO)?.focus();
    document.addEventListener('keydown', trapCheckoutFocus);
  } else {
    document.removeEventListener('keydown', trapCheckoutFocus);
    // Restore focus to the trigger element so keyboard users are not stranded on <body>.
    await nextTick();
    checkoutTriggerRef.value?.focus();
  }
});
onBeforeUnmount(() => {
  document.removeEventListener('keydown', trapCheckoutFocus);
  if (_catObserver) { _catObserver.disconnect(); _catObserver = null; }
  clearInterval(_flashSaleTimer);
});
const placing = ref(false);
const checkoutError = ref('');
const showAuthModal = ref(false); // opens when delivery order requires sign-in

// After the customer signs in mid-checkout, retry placing the order automatically.
const onAuthenticated = async () => {
  showAuthModal.value = false;
  checkoutError.value = '';
  await customerStore.fetchCustomer(true);
  placeOrder(); // retry with the newly established session
};

// Cart: [{slug, name, price, qty}]
const cart = ref([]);

const form = reactive({
  fulfillment_type: 'pickup',
  customer_name: '',
  customer_phone: '',
  delivery_address: '',
  delivery_lat: null,
  delivery_lng: null,
  customer_note: '',
});

// Capture the customer's coordinates so the delivery fee can be priced by distance.
const locatingMkt = ref(false);
const locateError = ref('');
const useMyLocation = () => {
  locateError.value = '';
  if (!navigator.geolocation) {
    locateError.value = t('mktMenu.locateUnsupported');
    return;
  }
  locatingMkt.value = true;
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      form.delivery_lat = Number(pos.coords.latitude.toFixed(6));
      form.delivery_lng = Number(pos.coords.longitude.toFixed(6));
      locatingMkt.value = false;
    },
    () => {
      locateError.value = t('mktMenu.locateFailed');
      locatingMkt.value = false;
    },
    { enableHighAccuracy: true, timeout: 10000 },
  );
};

// Advance/scheduled order + loyalty redemption (parity with the direct checkout).
const scheduleEnabled = ref(false);
const scheduledFor = ref(''); // <input type="datetime-local"> value (local wall-clock)
const loyaltyConfig = ref(null);
const useLoyalty = ref(false);
const minScheduleDatetime = computed(() => {
  const d = new Date(Date.now() + 30 * 60 * 1000);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
});

// ── Customer ─────────────────────────────────────────────────────────────────
const customer = computed(() => customerStore.customer);

// ── Cart helpers ──────────────────────────────────────────────────────────────
const cartQty = (dishSlug) => {
  const item = cart.value.find((i) => i.slug === dishSlug);
  return item ? item.qty : 0;
};

const addToCart = (dish) => {
  const existing = cart.value.find((i) => i.slug === dish.slug);
  if (existing) {
    existing.qty++;
  } else {
    cart.value.push({ slug: dish.slug, name: dish.name, price: dish.price, qty: 1 });
  }
};

const addToCartBySlug = (dishSlug) => {
  const existing = cart.value.find((i) => i.slug === dishSlug);
  if (existing) existing.qty++;
};

const removeFromCart = (dishSlug) => {
  const idx = cart.value.findIndex((i) => i.slug === dishSlug);
  if (idx < 0) return;
  if (cart.value[idx].qty > 1) {
    cart.value[idx].qty--;
  } else {
    cart.value.splice(idx, 1);
  }
};

const cartTotalQty = computed(() => cart.value.reduce((s, i) => s + i.qty, 0));

const cartTotal = computed(() =>
  cart.value.reduce((s, i) => s + Number(i.price) * i.qty, 0)
);

// Flash sale discount — mirrors backend: pct applied to food subtotal only
const flashSaleDiscount = computed(() => {
  if (!restaurant.value?.flash_sale) return 0;
  const pct = Number(restaurant.value.flash_sale.discount_pct);
  return pct > 0 ? Math.round(cartTotal.value * pct) / 100 : 0;
});

// ── Distance-based delivery pricing (mirrors backend compute_delivery_fee) ────
// Straight-line→road multiplier, mirrors backend tenancy/routing road factor
// (DELIVERY_ROAD_FACTOR, default 1.3). Server figure is authoritative.
const ROAD_FACTOR = 1.3;
function haversineKm(lat1, lng1, lat2, lng2) {
  const toNum = (v) => (v === null || v === undefined || v === '' ? NaN : Number(v));
  const a1 = toNum(lat1), o1 = toNum(lng1), a2 = toNum(lat2), o2 = toNum(lng2);
  if (![a1, o1, a2, o2].every((n) => Number.isFinite(n))) return null;
  const R = 6371.0088;
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(a2 - a1), dLng = rad(o2 - o1);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a1)) * Math.cos(rad(a2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.asin(Math.min(1, Math.sqrt(s)));
}
const deliveryPricing = computed(() => {
  const p = restaurant.value || {};
  return {
    flat: Number(p.delivery_fee) || 0,
    base: Number(p.delivery_base_fee) || 0,
    perKm: Number(p.delivery_per_km) || 0,
    freeOver: Number(p.delivery_free_over) || 0,
    radiusKm: p.delivery_radius_km == null ? null : Number(p.delivery_radius_km),
    lat: p.lat,
    lng: p.lng,
  };
});
// A coordinate is usable only if it's in range AND not the null-island (0,0)
// default a failed locate/geocode leaves behind — mirrors backend valid_coord.
const validCoord = (lat, lng) => {
  const a = Number(lat), o = Number(lng);
  if (!Number.isFinite(a) || !Number.isFinite(o)) return false;
  if (a < -90 || a > 90 || o < -180 || o > 180) return false;
  return !(Math.abs(a) < 1e-6 && Math.abs(o) < 1e-6);
};
const deliveryDistanceKm = computed(() => {
  const p = deliveryPricing.value;
  // Only compute distance when BOTH the restaurant and the chosen address are real
  // points; a bogus/unset restaurant coordinate must NOT read as "outside delivery
  // area" — fall back to flat pricing instead.
  if (!validCoord(p.lat, p.lng) || !validCoord(form.delivery_lat, form.delivery_lng)) return null;
  const d = haversineKm(p.lat, p.lng, form.delivery_lat, form.delivery_lng);
  // Approximate the road distance the driver drives (× road factor), matching
  // backend tenancy/routing.road_distance_km so the previewed fee lines up.
  return d == null ? null : Math.round(d * ROAD_FACTOR * 10) / 10;
});
const deliveryOutOfRange = computed(() => {
  const p = deliveryPricing.value, d = deliveryDistanceKm.value;
  return d != null && p.radiusKm != null && p.radiusKm > 0 && d > p.radiusKm;
});
const deliveryFeeIsDistance = computed(
  () => deliveryPricing.value.perKm > 0 && deliveryDistanceKm.value != null,
);
const deliveryIsFree = computed(() => {
  const p = deliveryPricing.value;
  return p.freeOver > 0 && cartTotal.value >= p.freeOver && !deliveryOutOfRange.value;
});
const deliveryFee = computed(() => {
  const p = deliveryPricing.value;
  if (form.fulfillment_type !== 'delivery') return 0;
  if (deliveryOutOfRange.value) return 0;
  if (p.freeOver > 0 && cartTotal.value >= p.freeOver) return 0;
  if (deliveryFeeIsDistance.value) {
    return Math.max(0, Math.round((p.base + p.perKm * deliveryDistanceKm.value) * 100) / 100);
  }
  return p.flat > 0 ? p.flat : 0;
});
const deliveryBlocked = computed(
  () => form.fulfillment_type === 'delivery' && deliveryOutOfRange.value,
);

// ── Loyalty redemption ───────────────────────────────────────────────────────
const loyaltyPoints = computed(() => Number(customerStore.customer?.loyalty_points) || 0);
const loyaltyAvailable = computed(() =>
  customerStore.isAuthenticated &&
  !!loyaltyConfig.value?.enabled &&
  loyaltyPoints.value >= (Number(loyaltyConfig.value?.redeem_threshold) || 0) &&
  (Number(loyaltyConfig.value?.points_value) || 0) > 0
);
const orderBaseTotal = computed(() => {
  let total = cartTotal.value;
  if (form.fulfillment_type === 'delivery') {
    total += deliveryFee.value;
  }
  return total;
});
const loyaltyDiscount = computed(() => {
  if (!useLoyalty.value || !loyaltyAvailable.value) return 0;
  const ptsValue = Number(loyaltyConfig.value.points_value) || 0;
  // Cap redeemable amount against the post-flash-sale total (mirrors backend)
  const maxRedeemable = Math.max(0, orderBaseTotal.value - flashSaleDiscount.value);
  return Math.max(0, Math.min(loyaltyPoints.value * ptsValue, maxRedeemable));
});

const orderTotal = computed(() =>
  Math.max(0, orderBaseTotal.value - flashSaleDiscount.value - loyaltyDiscount.value)
);

// Marketplace orders are pay-now: settled in full from the wallet at checkout.
const walletBalanceNum = computed(() => {
  const n = Number(customer.value?.wallet_balance);
  return Number.isFinite(n) && n > 0 ? n : 0;
});
const walletCoversTotal = computed(() => walletBalanceNum.value >= orderTotal.value);
const prepayShortfall = computed(
  () => customerStore.isAuthenticated && orderTotal.value > 0 && !walletCoversTotal.value
);

const fmtPrice = (amount) => {
  const cur = restaurant.value?.currency;
  if (!cur) return Number(amount || 0).toFixed(2);
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency: cur,
      maximumFractionDigits: 2,
    }).format(amount || 0);
  } catch {
    return `${Number(amount || 0).toFixed(2)} ${cur}`;
  }
};

// ── API ───────────────────────────────────────────────────────────────────────
const fetchMenu = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const res = await api.get(`/marketplace/menu/${slug}/`);
    restaurant.value = res.data;
    loyaltyConfig.value = res.data?.loyalty?.enabled ? res.data.loyalty : null;
    // Track visit for "Continue browsing" on the marketplace landing page
    // Format: [{slug, ts}] — ts is unix-ms; entries older than 30 days are pruned on load.
    try {
      const raw = JSON.parse(localStorage.getItem('marketplace:recent') || '[]');
      // Normalise legacy plain-string entries (no ts → treat as expired, drop them)
      const existing = raw
        .filter(e => e && typeof e === 'object' && e.slug && e.slug !== slug);
      localStorage.setItem('marketplace:recent', JSON.stringify(
        [{ slug, ts: Date.now() }, ...existing].slice(0, 8)
      ));
    } catch { /* storage unavailable */ }
    // Pre-fill customer info if signed in
    if (customer.value) {
      form.customer_name = customer.value.name || '';
      form.customer_phone = customer.value.phone || '';
    }
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};


const placeOrder = async () => {
  checkoutError.value = '';
  if (!form.customer_name.trim()) {
    checkoutError.value = t('mktMenu.nameRequired');
    return;
  }
  if (scheduleEnabled.value && !scheduledFor.value) {
    checkoutError.value = t('mktMenu.scheduleRequired');
    return;
  }
  // Pay-now: a signed-in customer's wallet must cover the full total.
  if (customerStore.isAuthenticated && orderTotal.value > 0 && walletBalanceNum.value < orderTotal.value) {
    checkoutError.value = t('mktMenu.walletTopUpRequired', {
      balance: fmtPrice(walletBalanceNum.value),
      total: fmtPrice(orderTotal.value),
    });
    return;
  }
  placing.value = true;
  try {
    const items = cart.value.map((i) => ({ slug: i.slug, qty: i.qty }));
    const payload = {
      restaurant: slug,
      items,
      fulfillment_type: form.fulfillment_type,
      customer_name: form.customer_name,
      customer_phone: form.customer_phone,
      customer_note: form.customer_note,
      delivery_address: form.delivery_address,
      delivery_lat: form.delivery_lat,
      delivery_lng: form.delivery_lng,
      use_wallet: true,
    };
    if (scheduleEnabled.value && scheduledFor.value) {
      const dt = new Date(scheduledFor.value);
      if (!Number.isNaN(dt.getTime())) payload.scheduled_for = dt.toISOString();
    }
    if (useLoyalty.value && loyaltyAvailable.value && loyaltyPoints.value > 0) {
      payload.redeem_points = loyaltyPoints.value;
    }
    const res = await api.post('/marketplace/order/', payload);
    // Stamp localStorage so MarketplaceOrderStatus can show a "just placed" banner
    try {
      localStorage.setItem('mktLastOrderNumber', String(res.data.order_number));
      localStorage.setItem('mktLastOrderAt', String(Date.now()));
      localStorage.setItem('mktLastOrderSlug', String(slug));
    } catch { /* storage unavailable */ }
    // Navigate to order status page
    router.push({ name: 'marketplace-order-status', params: { slug, orderNumber: res.data.order_number } });
  } catch (err) {
    const code = err?.response?.data?.code;
    if (code === 'auth_required') {
      // Don't leave the customer stuck with an error — open the sign-in modal so
      // they can sign in inline and retry without losing their cart.
      showAuthModal.value = true;
    } else if (code === 'wallet_insufficient') {
      checkoutError.value = t('mktMenu.walletInsufficientError');
    } else if (code === 'restaurant_closed') {
      checkoutError.value = t('mktMenu.restaurantClosed');
    } else if (code === 'items_unavailable') {
      checkoutError.value = t('mktMenu.itemsUnavailable');
    } else if (typeof code === 'string' && code.startsWith('loyalty_')) {
      customerStore.fetchCustomer(true);
      useLoyalty.value = false;
      checkoutError.value = err?.response?.data?.detail || t('mktMenu.orderError');
    } else if (typeof code === 'string' && code.startsWith('schedule_')) {
      checkoutError.value = err?.response?.data?.detail || t('mktMenu.orderError');
    } else {
      checkoutError.value = t('mktMenu.orderError');
    }
  } finally {
    placing.value = false;
  }
};

// ── Category navigation (sticky nav + IntersectionObserver) ──────────────────
const activeCatId = ref(null);

const allCategories = computed(() => {
  const cats = [];
  for (const sc of restaurant.value?.super_categories || []) {
    for (const cat of sc.categories || []) {
      if (cat.dishes?.length) cats.push({ id: cat.id, name: cat.name });
    }
  }
  return cats;
});

const scrollToCategory = (catId) => {
  mktSearchQuery.value = '';  // clear search so normal sections are visible
  activeCatId.value = catId;
  const el = document.getElementById(`mkt-cat-${catId}`);
  if (!el) return;
  // 56px: sticky nav height + a bit of breathing room
  const offset = 56;
  const top = el.getBoundingClientRect().top + window.scrollY - offset;
  window.scrollTo({ top, behavior: 'smooth' });
};

// ── Menu text search ──────────────────────────────────────────────────────────
const mktSearchQuery = ref('');
const isMktSearchActive = computed(() => mktSearchQuery.value.trim().length > 0);

/** Search results grouped by category across all super-categories */
const mktSearchResults = computed(() => {
  const q = mktSearchQuery.value.trim().toLowerCase();
  if (!q) return [];
  const groups = [];
  for (const sc of restaurant.value?.super_categories || []) {
    for (const cat of sc.categories || []) {
      const matched = (cat.dishes || []).filter(d =>
        (d.name || '').toLowerCase().includes(q) ||
        (d.description || '').toLowerCase().includes(q)
      );
      if (matched.length) groups.push({ catName: cat.name, dishes: matched });
    }
  }
  return groups;
});

const mktTotalSearchCount = computed(() =>
  mktSearchResults.value.reduce((n, g) => n + g.dishes.length, 0)
);

let _catObserver = null;
const _setupCatObserver = () => {
  if (_catObserver) { _catObserver.disconnect(); _catObserver = null; }
  const sections = document.querySelectorAll('[data-mkt-cat]');
  if (!sections.length) return;
  _catObserver = new IntersectionObserver(
    (entries) => {
      // Pick the topmost intersecting section
      const visible = entries.filter((e) => e.isIntersecting);
      if (!visible.length) return;
      visible.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      activeCatId.value = Number(visible[0].target.dataset.mktCat);
    },
    { rootMargin: '-15% 0px -70% 0px', threshold: 0 },
  );
  sections.forEach((el) => _catObserver.observe(el));
};

// Pre-fill the cart from a re-order navigation (items_snapshot from CustomerOrderRef).
const applyReorderItems = () => {
  const items = history.state?.reorderItems;
  if (!Array.isArray(items) || !items.length) return;
  cart.value = [];
  for (const item of items) {
    if (!item.slug) continue;
    cart.value.push({
      slug: item.slug,
      name: item.name || item.slug,
      price: Number(item.price) || 0,
      qty: Math.max(1, Math.floor(Number(item.qty) || 1)),
    });
  }
};

onMounted(async () => {
  await customerStore.fetchCustomer();
  applyReorderItems(); // pre-fill cart before menu loads so the badge is ready
  await fetchMenu();
  // Set up category observer after the menu DOM is rendered
  await nextTick();
  _setupCatObserver();
  // Highlight the first category by default
  if (allCategories.value.length) activeCatId.value = allCategories.value[0].id;
});
</script>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}
.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .slide-up-enter-active,
  .slide-up-leave-active {
    transition: opacity 0.15s ease;
  }
  .slide-up-enter-from,
  .slide-up-leave-to {
    transform: none;
    opacity: 0;
  }
}
</style>
