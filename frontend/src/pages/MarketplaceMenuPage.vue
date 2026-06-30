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
              <span v-else aria-hidden="true" class="text-2xl">{{ businessIcon(restaurant) }}</span>
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
                <!-- Pre-order prep ETA chip ('Ready in ~X–Y min') -->
                <span v-if="prepEta" class="ui-chip flex items-center gap-1 text-sky-300" :title="t('common.estimate')">
                  <AppIcon name="clock" class="h-3 w-3 shrink-0" aria-hidden="true" />
                  {{ t('menu.etaReadyIn', { min: prepEta.min, max: prepEta.max }) }}
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
          <!-- Opening hours (today + expandable week) -->
          <div v-if="todayHours" class="mt-2 pl-px">
            <button
              type="button"
              class="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 focus-visible:outline-none transition-colors"
              :aria-expanded="hoursExpanded"
              @click="hoursExpanded = !hoursExpanded"
            >
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3 shrink-0" aria-hidden="true"><circle cx="6" cy="6" r="4.5"/><path d="M6 3.5V6l1.5 1.5"/></svg>
              <span v-if="todayHours.closed" class="text-rose-400/80">{{ t('mktMenu.hoursClosedToday') }}</span>
              <span v-else>{{ t('mktMenu.hoursToday', { open: todayHours.open, close: todayHours.close }) }}</span>
              <span class="transition-transform" :class="hoursExpanded ? 'rotate-180' : ''" aria-hidden="true">▾</span>
            </button>
            <div v-if="hoursExpanded && weeklyHours" class="mt-1.5 overflow-hidden rounded-lg border border-slate-700/50 bg-slate-800/40 divide-y divide-slate-700/30">
              <div
                v-for="day in weeklyHours"
                :key="day.key"
                class="flex justify-between items-center px-2.5 py-1.5 text-[11px]"
                :class="day.isToday ? 'bg-slate-700/40 font-semibold text-slate-200' : 'text-slate-400'"
              >
                <span>{{ day.label }}</span>
                <span v-if="day.open" class="tabular-nums">{{ day.open }} – {{ day.close }}</span>
                <span v-else class="text-slate-500">–</span>
              </div>
            </div>
          </div>
          <!-- Share restaurant link -->
          <div class="mt-3 flex justify-end">
            <button
              class="ui-press inline-flex items-center gap-1.5 rounded-full border border-slate-700/60 bg-slate-900/50 px-3 py-1 text-xs font-medium text-slate-400 transition-colors hover:border-slate-500 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500/50"
              :aria-label="t('mktMenu.shareRestaurant')"
              @click="shareRestaurant"
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><circle cx="12" cy="3" r="1.5"/><circle cx="4" cy="8" r="1.5"/><circle cx="12" cy="13" r="1.5"/><path d="M5.5 8.9l5 2.7M10.5 4.1l-5 2.7"/></svg>
              {{ menuLinkCopied ? t('mktMenu.linkCopied') : t('mktMenu.share') }}
            </button>
          </div>
        </header>
      </div>

      <!-- Fulfillment type quick-switch (shown when restaurant supports delivery) -->
      <div
        v-if="restaurant?.delivery_enabled"
        class="ui-reveal mx-4 mb-2 flex items-center gap-2 rounded-xl border border-slate-700/60 bg-slate-900/50 p-1"
        :style="{ '--ui-delay': '20ms' }"
        role="group"
        :aria-label="t('mktMenu.fulfillmentLabel')"
      >
        <button
          class="flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors"
          :class="form.fulfillment_type === 'pickup' ? 'bg-[var(--color-secondary)] text-white' : 'text-slate-400 hover:text-slate-200'"
          :aria-pressed="form.fulfillment_type === 'pickup'"
          @click="form.fulfillment_type = 'pickup'"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><path d="M8 2a4 4 0 1 0 0 8A4 4 0 0 0 8 2z"/><path d="M3.5 14c0-2.485 2.015-4.5 4.5-4.5s4.5 2.015 4.5 4.5"/></svg>
          {{ t('mktMenu.fulfillmentPickup') }}
        </button>
        <button
          class="flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors"
          :class="form.fulfillment_type === 'delivery' ? 'bg-[var(--color-secondary)] text-white' : 'text-slate-400 hover:text-slate-200'"
          :aria-pressed="form.fulfillment_type === 'delivery'"
          @click="form.fulfillment_type = 'delivery'"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><path d="M1.5 10.5h9m-9 0V6.5l2-4h6l2 4v4m-9 0a1.5 1.5 0 1 0 3 0m6-4.5h2.5l.5 4.5H13m0 0a1.5 1.5 0 1 0-3 0"/></svg>
          {{ t('mktMenu.fulfillmentDelivery') }}
        </button>
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
          <p v-if="loyaltyEarnProjection > 0" class="text-[10px] leading-tight text-violet-400/80">{{ t('mktMenu.loyaltyEarnProjection', { points: loyaltyEarnProjection }) }}</p>
          <p v-else-if="loyaltyAvailable" class="text-[10px] leading-tight text-violet-400/80">{{ t('mktMenu.loyaltyTeaserRedeem') }}</p>
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
              <span :aria-label="`${review.score} stars`">{{ '★'.repeat(review.score) }}<span class="opacity-25">{{ '★'.repeat(5 - review.score) }}</span></span>
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
        <!-- Allergen "Free from" strip — only shown when at least one dish has allergen data -->
        <div
          v-if="availableAllergens.length"
          role="group"
          :aria-label="t('mktMenu.allergenFilter')"
          class="flex items-center gap-2 overflow-x-auto border-t border-slate-800/40 px-4 py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          <span class="shrink-0 text-[10px] font-semibold uppercase tracking-widest text-slate-500">{{ t('mktMenu.freeFrom') }}</span>
          <button
            v-for="allergen in availableAllergens"
            :key="allergen"
            type="button"
            :aria-pressed="selectedAllergenFilter.includes(allergen)"
            class="ui-touch-target shrink-0 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
            :class="selectedAllergenFilter.includes(allergen)
              ? 'border-amber-400/70 bg-amber-500/20 text-amber-200'
              : 'border-slate-700 bg-slate-900/60 text-slate-400 hover:border-slate-600 hover:text-slate-300'"
            @click="toggleAllergenFilter(allergen)"
          >{{ t(`mktMenu.allergen_${allergen}`) }}</button>
          <!-- Hidden items counter shown when filter is active -->
          <Transition name="ui-fade">
            <span
              v-if="allergenHiddenCount > 0"
              class="ms-auto shrink-0 whitespace-nowrap rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-300"
            >{{ t('mktMenu.allergenHidden', { n: allergenHiddenCount }) }}</span>
          </Transition>
        </div>
      </nav>

      <!-- Menu -->
      <section class="space-y-8">

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
                <div
                  class="relative h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-slate-800/50 flex items-center justify-center cursor-pointer"
                  role="button"
                  :aria-label="dish.name"
                  tabindex="0"
                  @click="openOptionPanel(dish)"
                  @keydown.enter="openOptionPanel(dish)"
                  @keydown.space.prevent="openOptionPanel(dish)"
                >
                  <img v-if="dish.image_url" :src="dish.image_url" :alt="dish.name" loading="lazy" decoding="async" class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" @error="$event.target.style.display='none'" />
                  <span v-else aria-hidden="true" class="text-2xl select-none">🍴</span>
                  <!-- Sold-out frosted overlay on thumbnail -->
                  <div
                    v-if="!dish.is_available"
                    class="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-slate-950/60 backdrop-blur-[2px]"
                    aria-hidden="true"
                  >
                    <span class="rounded-full border border-slate-600/40 bg-slate-900/80 px-1.5 py-px text-[8px] font-bold uppercase tracking-widest text-slate-400">
                      {{ t('mktMenu.soldOut') }}
                    </span>
                  </div>
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-semibold text-slate-100 leading-snug cursor-pointer hover:text-white transition-colors" :title="dish.name" @click="openOptionPanel(dish)">{{ dish.name }}</p>
                  <p v-if="dish.description" class="mt-0.5 text-xs text-slate-500 line-clamp-2 leading-relaxed" :title="dish.description">{{ dish.description }}</p>
                  <!-- Dietary tags -->
                  <div v-if="dish.tags?.length" class="mt-1.5 flex flex-wrap gap-1">
                    <span
                      v-for="tag in dish.tags.slice(0, 3)"
                      :key="tag"
                      class="rounded-full border px-1.5 py-0.5 text-[10px] font-medium"
                      :class="tagBadgeClass(tag)"
                    >{{ tag }}</span>
                  </div>
                  <div class="mt-2 flex items-center justify-between gap-2">
                    <!-- Price: happy-hour > flash-sale > regular -->
                    <span v-if="dish.happy_hour && Number(dish.effective_price) < Number(dish.price)" class="flex flex-col items-start gap-0.5">
                      <span class="flex items-baseline gap-1.5">
                        <span class="text-sm font-bold tabular-nums text-[var(--color-secondary)]">{{ fmtPrice(dish.effective_price) }}</span>
                        <span class="text-[11px] tabular-nums text-slate-500 line-through">{{ fmtPrice(dish.price) }}</span>
                      </span>
                      <span class="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">-{{ dish.happy_hour.percent_off }}% <template v-if="hhMinutesLeft(dish.happy_hour.ends_at) !== null">{{ t('happyHour.endsIn', { min: hhMinutesLeft(dish.happy_hour.ends_at) }) }}</template><template v-else>{{ t('happyHour.until', { time: dish.happy_hour.ends_at }) }}</template></span>
                    </span>
                    <span v-else-if="flashSalePct" class="flex flex-col items-start gap-0.5">
                      <span class="flex items-baseline gap-1.5">
                        <span class="text-[11px] tabular-nums text-amber-200/50 line-through">{{ fmtPrice(dish.price) }}</span>
                        <span class="text-sm font-bold tabular-nums text-amber-400">{{ fmtPrice(dishSalePrice(dish.price)) }}</span>
                      </span>
                      <span class="rounded-full border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">-{{ flashSalePct }}%</span>
                    </span>
                    <span v-else class="text-sm font-bold tabular-nums text-[var(--color-secondary)]">{{ fmtPrice(dish.price) }}</span>
                    <!-- Share dish icon -->
                    <button
                      class="ui-press ms-auto me-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-slate-500 transition hover:text-slate-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-500/50"
                      :aria-label="`${t('mktMenu.shareDish')} ${dish.name}`"
                      @click.stop="shareDish(dish)"
                    >
                      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><circle cx="12" cy="3" r="1.5"/><circle cx="4" cy="8" r="1.5"/><circle cx="12" cy="13" r="1.5"/><path d="M5.5 8.9l5 2.7M10.5 4.1l-5 2.7"/></svg>
                    </button>
                    <!-- Inline qty stepper once in cart, plain add button otherwise -->
                    <div v-if="cartQty(dish.slug)" class="inline-flex shrink-0 items-center gap-0.5 rounded-full border border-slate-700/60 bg-slate-900/70 px-0.5">
                      <button
                        class="ui-press flex h-7 w-7 items-center justify-center rounded-full text-slate-400 transition hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
                        :aria-label="`${t('dishPage.decreaseQuantity')} ${dish.name}`"
                        @click="removeFromCart(dish.slug)"
                      >
                        <svg viewBox="0 0 12 12" class="h-3 w-3 shrink-0" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none" aria-hidden="true"><path d="M2 6h8"/></svg>
                      </button>
                      <span class="min-w-[1.25rem] text-center text-sm font-bold tabular-nums text-white" aria-live="polite" aria-atomic="true">{{ cartQty(dish.slug) }}</span>
                      <button
                        class="ui-press flex h-7 w-7 items-center justify-center rounded-full text-[var(--color-secondary)] transition hover:opacity-80 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
                        :aria-label="`${t('dishPage.increaseQuantity')} ${dish.name}`"
                        @click="addToCart(dish)"
                      >
                        <svg viewBox="0 0 12 12" class="h-3 w-3 shrink-0" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none" aria-hidden="true"><path d="M6 1v10M1 6h10"/></svg>
                      </button>
                    </div>
                    <button
                      v-else-if="dish.is_available && restaurant?.is_open"
                      class="ui-press inline-flex items-center gap-1.5 rounded-full bg-[var(--color-secondary)] px-3.5 py-1.5 text-xs font-bold text-slate-950 transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50 ui-touch-target"
                      :aria-label="`${t('mktMenu.addToCart')} ${dish.name}`"
                      @click="addToCart(dish)"
                    >
                      <svg viewBox="0 0 12 12" class="h-3 w-3 shrink-0" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none" aria-hidden="true"><path d="M6 1v10M1 6h10"/></svg>
                      {{ t('mktMenu.addToCart') }}
                    </button>
                    <span
                      v-else-if="dish.is_available && !restaurant?.is_open"
                      class="inline-flex items-center rounded-full border border-slate-600/40 bg-slate-800/50 px-2.5 py-1 text-[10px] font-semibold text-slate-500"
                    >{{ t('mktMenu.closed') }}</span>
                    <span
                      v-else
                      class="inline-flex items-center rounded-full border border-slate-700/50 bg-slate-800/60 px-2.5 py-1 text-[10px] font-semibold text-slate-500"
                    >{{ t('mktMenu.soldOut') }}</span>
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
            <div>
              <p class="text-sm font-medium text-slate-300">{{ t('mktMenu.noMatchDish') }}</p>
              <p class="mt-0.5 text-xs text-slate-600">{{ t('mktMenu.noMatchHint', { q: mktSearchQuery }) }}</p>
            </div>
            <button type="button" class="rounded-full border border-slate-700/60 bg-slate-800/40 px-4 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-slate-600 hover:text-white" @click="mktSearchQuery = ''">{{ t('mktMenu.browseAll') }}</button>
          </div>
        </template>

        <!-- ── Normal category sections (search inactive) ─────────────────── -->
        <template v-else>
          <!-- Empty menu state (no dishes at all) -->
          <div
            v-if="!restaurant.super_categories?.length"
            class="ui-empty-state text-center space-y-1"
          >
            <p class="text-sm font-semibold text-slate-100">{{ t('mktMenu.menuEmpty', { catalog }) }}</p>
            <p class="text-xs text-slate-400">{{ t('mktMenu.menuEmptyBody') }}</p>
          </div>
          <!-- No dishes pass the active allergen filter -->
          <div
            v-else-if="selectedAllergenFilter.length && !filteredSuperCategories.length"
            class="flex flex-col items-center gap-3 rounded-2xl border border-slate-800/50 bg-slate-900/30 px-4 py-12 text-center"
          >
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" class="h-10 w-10 text-slate-700" aria-hidden="true"><circle cx="10" cy="10" r="7.5"/><path d="M7 10h6M10 7v6"/><path d="M14 6 6 14" stroke-width="1.8"/></svg>
            <p class="text-sm font-medium text-slate-400">{{ t('mktMenu.noMatchDish') }}</p>
            <button
              type="button"
              class="text-xs text-slate-500 underline transition-colors hover:text-slate-300"
              @click="selectedAllergenFilter = []; try { localStorage.removeItem(ALLERGEN_KEY) } catch {}"
            >{{ t('mktMenu.searchClear') }}</button>
          </div>

          <!-- Favourites horizontal rail -->
          <div v-if="favoriteDishes.length" class="space-y-2">
            <p class="ui-kicker">{{ t('mktMenu.favourites') }}</p>
            <div class="flex gap-2.5 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              <button
                v-for="fd in favoriteDishes"
                :key="fd.slug"
                type="button"
                class="ui-press flex shrink-0 flex-col items-start gap-1.5 rounded-2xl border border-rose-500/20 bg-rose-500/5 p-2.5 text-start transition hover:bg-rose-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500/40"
                style="min-width: 110px; max-width: 140px"
                @click="openOptionPanel(fd)"
              >
                <div
                  v-if="fd.image_url"
                  class="h-12 w-full rounded-xl bg-cover bg-center"
                  :style="{ backgroundImage: `url(${fd.image_url})` }"
                  aria-hidden="true"
                />
                <div v-else class="flex h-12 w-full items-center justify-center rounded-xl bg-rose-500/10 text-xl" aria-hidden="true">❤️</div>
                <p class="line-clamp-2 text-[11px] font-semibold leading-snug text-slate-100">{{ fd.name }}</p>
                <p class="text-[10px] font-bold tabular-nums text-[var(--color-secondary)]">{{ fmtPrice(fd.effective_price || fd.price) }}</p>
              </button>
            </div>
          </div>

          <!-- Recently viewed horizontal rail -->
          <div v-if="recentlyViewed.length" class="space-y-2">
            <p class="ui-kicker">{{ t('mktMenu.recentlyViewed') }}</p>
            <div class="flex gap-2.5 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              <button
                v-for="rd in recentlyViewed"
                :key="rd.slug"
                type="button"
                class="ui-press flex shrink-0 flex-col items-start gap-1.5 rounded-2xl border border-slate-700/40 bg-slate-800/50 p-2.5 text-start transition hover:bg-slate-700/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
                style="min-width: 110px; max-width: 140px"
                @click="openOptionPanel(rd)"
              >
                <div
                  v-if="rd.image_url"
                  class="h-12 w-full rounded-xl bg-cover bg-center"
                  :style="{ backgroundImage: `url(${rd.image_url})` }"
                  aria-hidden="true"
                />
                <div v-else class="flex h-12 w-full items-center justify-center rounded-xl bg-slate-700/50 text-xl" aria-hidden="true">🍽</div>
                <p class="line-clamp-2 text-[11px] font-semibold leading-snug text-slate-100">{{ rd.name }}</p>
                <p class="text-[10px] font-bold tabular-nums text-[var(--color-secondary)]">{{ fmtPrice(rd.effective_price || rd.price) }}</p>
              </button>
            </div>
          </div>

          <div
            v-for="sc in filteredSuperCategories"
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
                  <!-- Image (clickable → detail/option sheet) -->
                  <div
                    class="relative h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-slate-800/50 flex items-center justify-center cursor-pointer"
                    role="button"
                    :aria-label="dish.name"
                    tabindex="0"
                    @click="openOptionPanel(dish)"
                    @keydown.enter="openOptionPanel(dish)"
                    @keydown.space.prevent="openOptionPanel(dish)"
                  >
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
                    <!-- Sold-out frosted overlay on thumbnail -->
                    <div
                      v-if="!dish.is_available"
                      class="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-slate-950/60 backdrop-blur-[2px]"
                      aria-hidden="true"
                    >
                      <span class="rounded-full border border-slate-600/40 bg-slate-900/80 px-1.5 py-px text-[8px] font-bold uppercase tracking-widest text-slate-400">
                        {{ t('mktMenu.soldOut') }}
                      </span>
                    </div>
                  </div>
                  <!-- Info -->
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-semibold text-slate-100 leading-snug cursor-pointer hover:text-white transition-colors" :title="dish.name" @click="openOptionPanel(dish)">{{ dish.name }}</p>
                    <p v-if="dish.description" class="mt-0.5 text-xs text-slate-500 line-clamp-2 leading-relaxed" :title="dish.description">{{ dish.description }}</p>
                    <!-- Dietary tags -->
                    <div v-if="dish.tags?.length" class="mt-1.5 flex flex-wrap gap-1">
                      <span
                        v-for="tag in dish.tags.slice(0, 3)"
                        :key="tag"
                        class="rounded-full border px-1.5 py-0.5 text-[10px] font-medium"
                        :class="tagBadgeClass(tag)"
                      >{{ tag }}</span>
                    </div>
                    <div class="mt-2 flex items-center justify-between gap-2">
                      <!-- Price: happy-hour > flash-sale > regular -->
                      <span v-if="dish.happy_hour && Number(dish.effective_price) < Number(dish.price)" class="flex flex-col items-start gap-0.5">
                        <span class="flex items-baseline gap-1.5">
                          <span class="text-sm font-bold tabular-nums text-[var(--color-secondary)]">{{ fmtPrice(dish.effective_price) }}</span>
                          <span class="text-[11px] tabular-nums text-slate-500 line-through">{{ fmtPrice(dish.price) }}</span>
                        </span>
                        <span class="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">-{{ dish.happy_hour.percent_off }}% <template v-if="hhMinutesLeft(dish.happy_hour.ends_at) !== null">{{ t('happyHour.endsIn', { min: hhMinutesLeft(dish.happy_hour.ends_at) }) }}</template><template v-else>{{ t('happyHour.until', { time: dish.happy_hour.ends_at }) }}</template></span>
                      </span>
                      <span v-else-if="flashSalePct" class="flex flex-col items-start gap-0.5">
                        <span class="flex items-baseline gap-1.5">
                          <span class="text-[11px] tabular-nums text-amber-200/50 line-through">{{ fmtPrice(dish.price) }}</span>
                          <span class="text-sm font-bold tabular-nums text-amber-400">{{ fmtPrice(dishSalePrice(dish.price)) }}</span>
                        </span>
                        <span class="rounded-full border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">-{{ flashSalePct }}%</span>
                      </span>
                      <span v-else class="text-sm font-bold tabular-nums text-[var(--color-secondary)]">{{ fmtPrice(dish.price) }}</span>
                      <!-- Favorite (heart) button -->
                      <button
                        class="ui-press ms-auto flex h-7 w-7 shrink-0 items-center justify-center rounded-full transition focus-visible:outline-none focus-visible:ring-1"
                        :class="isFavorite(dish.slug)
                          ? 'text-rose-400 focus-visible:ring-rose-500/40'
                          : 'text-slate-500 hover:text-slate-300 focus-visible:ring-slate-500/50'"
                        :aria-label="`${isFavorite(dish.slug) ? t('mktMenu.unfavorite') : t('mktMenu.favorite')} ${dish.name}`"
                        :aria-pressed="isFavorite(dish.slug)"
                        @click.stop="toggleFavorite(dish)"
                      >
                        <svg viewBox="0 0 16 16" :fill="isFavorite(dish.slug) ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><path d="M8 13.5S2 9.5 2 5.5A3 3 0 0 1 8 4a3 3 0 0 1 6 1.5c0 4-6 8-6 8z"/></svg>
                      </button>
                      <!-- Share dish icon -->
                      <button
                        class="ui-press me-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-slate-500 transition hover:text-slate-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-500/50"
                        :aria-label="`${t('mktMenu.shareDish')} ${dish.name}`"
                        @click.stop="shareDish(dish)"
                      >
                        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><circle cx="12" cy="3" r="1.5"/><circle cx="4" cy="8" r="1.5"/><circle cx="12" cy="13" r="1.5"/><path d="M5.5 8.9l5 2.7M10.5 4.1l-5 2.7"/></svg>
                      </button>
                      <!-- Inline qty stepper once in cart, plain add button otherwise -->
                      <div v-if="cartQty(dish.slug)" class="inline-flex shrink-0 items-center gap-0.5 rounded-full border border-slate-700/60 bg-slate-900/70 px-0.5">
                        <button
                          class="ui-press flex h-7 w-7 items-center justify-center rounded-full text-slate-400 transition hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
                          :aria-label="`${t('dishPage.decreaseQuantity')} ${dish.name}`"
                          @click="removeFromCart(dish.slug)"
                        >
                          <svg viewBox="0 0 12 12" class="h-3 w-3 shrink-0" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none" aria-hidden="true"><path d="M2 6h8"/></svg>
                        </button>
                        <span class="min-w-[1.25rem] text-center text-sm font-bold tabular-nums text-white" aria-live="polite" aria-atomic="true">{{ cartQty(dish.slug) }}</span>
                        <button
                          class="ui-press flex h-7 w-7 items-center justify-center rounded-full text-[var(--color-secondary)] transition hover:opacity-80 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
                          :aria-label="`${t('dishPage.increaseQuantity')} ${dish.name}`"
                          @click="addToCart(dish)"
                        >
                          <svg viewBox="0 0 12 12" class="h-3 w-3 shrink-0" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none" aria-hidden="true"><path d="M6 1v10M1 6h10"/></svg>
                        </button>
                      </div>
                      <button
                        v-else-if="dish.is_available"
                        class="ui-press inline-flex items-center gap-1.5 rounded-full bg-[var(--color-secondary)] px-3.5 py-1.5 text-xs font-bold text-slate-950 transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50 ui-touch-target"
                        :aria-label="`${t('mktMenu.addToCart')} ${dish.name}`"
                        @click="addToCart(dish)"
                      >
                        <svg viewBox="0 0 12 12" class="h-3 w-3 shrink-0" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none" aria-hidden="true"><path d="M6 1v10M1 6h10"/></svg>
                        {{ t('mktMenu.addToCart') }}
                      </button>
                      <span
                        v-else
                        class="inline-flex items-center rounded-full border border-slate-700/50 bg-slate-800/60 px-2.5 py-1 text-[10px] font-semibold text-slate-500"
                      >{{ t('mktMenu.soldOut') }}</span>
                    </div>
                  </div>
                </article>
              </div>
            </div>
          </div>
        </template>
      </section>
    </template>

    </div><!-- /max-w-3xl shell -->

    <!-- Delivery minimum progress strip (shown before checkout opens) -->
    <Transition name="ui-fade">
      <div
        v-if="cart.length && !checkoutOpen && form.fulfillment_type === 'delivery' && deliveryMinGap > 0"
        class="fixed inset-x-3 z-30 mx-auto w-[calc(100%-1.5rem)] max-w-md rounded-t-xl border border-slate-700/60 bg-slate-900/95 px-4 py-2.5 backdrop-blur-sm"
        style="bottom: calc(var(--safe-bottom) + 4.5rem)"
      >
        <div class="flex items-center justify-between gap-2 text-[11px] text-slate-400">
          <span>{{ t('mktMenu.deliveryMinProgress') }}</span>
          <span class="font-semibold text-amber-300">{{ t('mktMenu.deliveryMinAddMore', { amount: fmtPrice(deliveryMinGap) }) }}</span>
        </div>
        <div class="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-700/60">
          <div
            class="h-full rounded-full bg-[var(--color-secondary)] transition-all duration-300"
            :style="{ width: `${Math.min(100, Math.round((cartTotal / deliveryMinOrder) * 100))}%` }"
          />
        </div>
      </div>
    </Transition>

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
            <div class="flex items-center gap-2">
              <button
                v-if="cart.length > 1"
                class="ui-press rounded-lg px-2 py-1 text-[11px] font-medium text-slate-500 hover:text-rose-400 focus-visible:outline-none"
                :aria-label="t('mktMenu.clearCart')"
                @click="cart.splice(0); checkoutOpen = false"
              >
                {{ t('mktMenu.clearCart') }}
              </button>
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
          </div>

          <!-- Unavailable items warning banner -->
          <div
            v-if="unavailableSlugs.size > 0"
            class="rounded-xl border border-red-500/30 bg-red-900/15 px-3 py-2.5 text-[11px] font-semibold text-red-300"
            role="alert"
          >
            {{ t('mktMenu.cartHasUnavailableItems') }}
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
                <p class="truncate text-sm font-semibold leading-snug" :class="unavailableSlugs.has(item.slug) ? 'text-slate-400 line-through' : 'text-slate-100'" :title="item.name">{{ item.name }}</p>
                <p v-if="unavailableSlugs.has(item.slug)" class="text-[10px] font-semibold text-red-400">{{ t('mktMenu.cartItemUnavailable') }}</p>
                <p v-if="item.options?.length" class="truncate text-[11px] text-slate-500 leading-snug">{{ item.options.map(o => o.name).join(', ') }}</p>
                <p class="text-xs tabular-nums">
                  <span class="font-semibold text-[var(--color-secondary)]">{{ fmtPrice((item.unitPrice ?? item.price) * item.qty) }}</span>
                  <span class="text-slate-500"> · {{ fmtPrice(item.unitPrice ?? item.price) }} ea.</span>
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
              <!-- Saved addresses — shown when customer is signed in and has saved addresses -->
              <div v-if="customerStore.isAuthenticated && mktSavedAddresses.length" class="space-y-1.5">
                <p class="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{{ t('mktMenu.savedAddresses') }}</p>
                <div class="space-y-1">
                  <div
                    v-for="addr in mktSavedAddresses"
                    :key="addr.id"
                    class="flex min-w-0 w-full items-center gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2 transition-colors hover:border-indigo-500/40 hover:bg-indigo-500/5"
                  >
                    <button
                      type="button"
                      class="min-w-0 flex-1 text-start text-xs focus-visible:outline-none"
                      @click="applyMktSavedAddress(addr)"
                    >
                      <span v-if="addr.label" class="font-medium text-slate-200 me-0.5">{{ addr.label }} —</span>
                      <span class="truncate text-slate-400">{{ addr.address }}</span>
                    </button>
                    <button
                      type="button"
                      class="shrink-0 text-slate-600 transition-colors hover:text-red-400 focus-visible:outline-none"
                      :aria-label="t('mktMenu.deleteSavedAddress')"
                      @click="deleteMktSavedAddress(addr.id)"
                    >
                      <svg viewBox="0 0 16 16" fill="currentColor" class="h-3 w-3" aria-hidden="true"><path d="M6 2h4a1 1 0 0 1 1 1v1H5V3a1 1 0 0 1 1-1ZM4 4H2v1h1l.8 8.1A1 1 0 0 0 4.8 14h6.4a1 1 0 0 0 1-.9L13 5h1V4H4Zm7 1H5l.7 7h4.6L12 5Z"/></svg>
                    </button>
                  </div>
                </div>
              </div>
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
              <!-- Save address checkbox (authenticated customers only) -->
              <div v-if="customerStore.isAuthenticated && form.delivery_address" class="space-y-1.5">
                <label class="flex items-center gap-2 cursor-pointer">
                  <input v-model="saveAddressAfterOrder" type="checkbox" class="rounded" />
                  <span class="text-xs text-slate-400">{{ t('mktMenu.saveAddress') }}</span>
                </label>
                <input
                  v-if="saveAddressAfterOrder"
                  v-model.trim="saveAddressLabel"
                  type="text"
                  class="ui-input text-xs"
                  :placeholder="t('mktMenu.saveAddressLabelPlaceholder')"
                  :aria-label="t('mktMenu.saveAddressLabelPlaceholder')"
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
              <p v-else-if="deliveryPricing.perKm > 0" class="flex items-center gap-1.5 text-[11px] text-amber-400" role="alert">
                <AppIcon name="location" class="h-3 w-3 shrink-0" aria-hidden="true" />
                {{ t('mktMenu.deliveryNeedsLocation') }}
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
          <!-- ── Loyalty earn projection ── -->
          <p
            v-if="loyaltyConfig?.enabled && loyaltyEarnProjection > 0"
            class="text-[11px] text-violet-400/80 ps-1"
          >{{ t('mktMenu.loyaltyEarnProjection', { points: loyaltyEarnProjection }) }}</p>

          <!-- Pay now (marketplace orders are pay-now) -->
          <div v-if="customerStore.isAuthenticated && orderTotal > 0" class="space-y-2">
            <!-- Trusted customers: choose wallet or cash on handover -->
            <div v-if="codEligible" class="grid grid-cols-2 gap-2">
              <button
                type="button"
                class="rounded-xl border px-3 py-2.5 text-xs font-semibold transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
                :class="paymentMethod === 'wallet' ? 'border-emerald-500/55 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-600'"
                :aria-pressed="paymentMethod === 'wallet'"
                @click="paymentMethod = 'wallet'"
              >{{ t('mktMenu.payMethodWallet') }}</button>
              <button
                type="button"
                class="rounded-xl border px-3 py-2.5 text-xs font-semibold transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
                :class="paymentMethod === 'cash' ? 'border-emerald-500/55 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-600'"
                :aria-pressed="paymentMethod === 'cash'"
                @click="paymentMethod = 'cash'"
              >{{ t('mktMenu.payMethodCash') }}</button>
            </div>

            <!-- Cash on handover panel -->
            <div v-if="codChosen" class="ui-panel rounded-xl border border-emerald-500/30 bg-emerald-500/8 px-4 py-3">
              <p class="text-sm font-semibold text-emerald-300">{{ t('mktMenu.payCashOnHandoverTitle') }}</p>
              <p class="mt-0.5 text-xs text-slate-400">{{ t('mktMenu.payCashOnHandoverNote') }}</p>
            </div>

            <!-- Pay now from wallet -->
            <div
              v-else
              class="ui-panel rounded-xl border px-4 py-3"
              :class="walletCoversTotal ? 'border-emerald-500/30 bg-emerald-500/8' : 'border-amber-500/40 bg-amber-500/8'"
            >
              <p class="text-sm font-semibold" :class="walletCoversTotal ? 'text-emerald-300' : 'text-amber-300'">
                {{ t('mktMenu.payFromWalletTitle') }}
              </p>
              <p class="text-xs text-slate-400">{{ t('mktMenu.walletBalanceLine', { balance: `${customer?.wallet_balance || 0} ${restaurant?.currency}` }) }}</p>
              <p v-if="!walletCoversTotal" class="mt-1 text-xs text-amber-200">
                {{ t('mktMenu.walletShortNotice', { amount: fmtPrice(orderTotal - walletBalanceNum) }) }}
                <RouterLink
                  :to="{ name: 'customer-account', query: { tab: 'wallet' } }"
                  class="ms-1.5 underline hover:no-underline text-amber-300"
                >{{ t('mktMenu.topUpWallet') }}</RouterLink>
              </p>
            </div>
          </div>

          <!-- Totals -->
          <div class="ui-panel px-4 py-3 space-y-1.5 text-sm">
            <!-- ETA chip — shown above totals when available -->
            <div v-if="prepEta" class="flex items-center gap-1.5 text-[11px] text-emerald-400/80 pb-0.5">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><circle cx="8" cy="8" r="6.25"/><path d="M8 4.75V8l2.25 2"/></svg>
              {{ t('menu.etaReadyIn', { min: prepEta.min, max: prepEta.max }) }}
            </div>
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

          <!-- Minimum order warning panel -->
          <div
            v-if="form.fulfillment_type === 'delivery' && deliveryMinGap > 0"
            class="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2.5"
            role="alert"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4 shrink-0 text-amber-400" aria-hidden="true"><path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-xs font-medium text-amber-200">{{ t('mktMenu.deliveryMinAddMore', { amount: fmtPrice(deliveryMinGap) }) }}</p>
          </div>

          <!-- Restaurant closed warning panel -->
          <div
            v-if="restaurant && !restaurant.is_open"
            class="flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/8 px-3 py-2.5"
            role="alert"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4 shrink-0 text-rose-400" aria-hidden="true"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-xs font-medium text-rose-300">{{ t('mktMenu.restaurantClosed') }}</p>
          </div>

          <!-- Guest + delivery warning — shown before submit so customer knows to sign in -->
          <div
            v-if="form.fulfillment_type === 'delivery' && !customerStore.isAuthenticated"
            class="flex items-center gap-2 rounded-xl border border-sky-500/30 bg-sky-500/8 px-3 py-2.5"
            role="status"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4 shrink-0 text-sky-400" aria-hidden="true"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z" clip-rule="evenodd"/></svg>
            <p class="flex-1 text-xs font-medium text-sky-200">{{ t('mktMenu.authRequired') }}</p>
          </div>

          <!-- Submit -->
          <button
            class="ui-press inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-[var(--color-secondary)] py-3.5 text-sm font-bold text-slate-950 transition-opacity hover:opacity-90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
            :disabled="placing || prepayShortfall || deliveryBlocked || needsLocation || deliveryMinGap > 0 || (restaurant && !restaurant.is_open) || unavailableSlugs.size > 0"
            :aria-busy="placing"
            @click="placeOrder"
          >
            <svg v-if="placing" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ placing ? t('mktMenu.placing') : unavailableSlugs.size > 0 ? t('mktMenu.cartHasUnavailableShort') : !restaurant?.is_open ? t('mktMenu.closed') : deliveryBlocked ? t('mktMenu.deliveryOutOfRangeShort') : prepayShortfall ? t('mktMenu.walletTopUpRequiredShort') : needsLocation ? t('mktMenu.needsLocationShort') : deliveryMinGap > 0 ? t('mktMenu.deliveryMinAddMore', { amount: fmtPrice(deliveryMinGap) }) : t('mktMenu.placeOrder') }}
          </button>
        </div>
      </div>
    </Transition>

    <!-- Option group selection panel (bottom sheet) -->
    <Transition name="slide-up">
      <div
        v-if="activeOptionDish"
        ref="optionPanelRef"
        role="dialog"
        aria-modal="true"
        :aria-label="activeOptionDish.name"
        class="fixed inset-0 z-50 flex flex-col"
        @keydown.esc="closeOptionPanel"
      >
        <!-- Backdrop -->
        <div
          class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
          aria-hidden="true"
          @click="closeOptionPanel"
        />
        <!-- Sheet (slides up from bottom, max ~88 vh) -->
        <div
          class="relative mt-auto mx-auto w-full max-w-md overflow-hidden rounded-t-3xl border-t border-slate-800/60 bg-[#0b0d13] shadow-2xl flex flex-col"
          style="max-height: 88vh"
        >
          <!-- Handle bar -->
          <div class="flex justify-center pt-3 pb-1 shrink-0" aria-hidden="true">
            <div class="h-1 w-10 rounded-full bg-slate-700" />
          </div>
          <!-- Dish header -->
          <div class="flex items-start gap-3 px-5 py-3.5 border-b border-slate-800/50 shrink-0">
            <!-- Larger image when available -->
            <div
              v-if="activeOptionDish.image_url"
              class="h-16 w-16 shrink-0 rounded-xl overflow-hidden bg-slate-800"
            >
              <img :src="activeOptionDish.image_url" :alt="activeOptionDish.name" loading="lazy" class="h-full w-full object-cover" />
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-base font-bold text-white leading-snug">{{ activeOptionDish.name }}</p>
              <!-- Base price + optional flash-sale strikethrough -->
              <div class="mt-0.5 flex items-baseline gap-1.5">
                <span v-if="flashSalePct" class="text-[11px] tabular-nums text-amber-200/50 line-through">{{ fmtPrice(activeOptionDish.price) }}</span>
                <span
                  class="text-sm font-bold tabular-nums"
                  :class="flashSalePct ? 'text-amber-400' : 'text-[var(--color-secondary)]'"
                >{{ fmtPrice(flashSalePct ? dishSalePrice(activeOptionDish.price) : activeOptionDish.price) }}</span>
              </div>
              <!-- Dietary tags -->
              <div v-if="activeOptionDish.tags?.length" class="mt-1.5 flex flex-wrap gap-1">
                <span
                  v-for="tag in activeOptionDish.tags"
                  :key="tag"
                  class="rounded-full border px-1.5 py-0.5 text-[10px] font-medium"
                  :class="tagBadgeClass(tag)"
                >{{ tag }}</span>
              </div>
            </div>
            <button
              type="button"
              class="ui-press flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-slate-700/60 text-slate-400 transition hover:border-slate-600 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
              :aria-label="t('common.close')"
              @click="closeOptionPanel"
            >
              <svg viewBox="0 0 16 16" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>
            </button>
          </div>

          <!-- Scrollable body: description + allergens + option groups -->
          <div class="flex-1 overflow-y-auto overscroll-contain px-5 py-4 space-y-5">
            <!-- Full description -->
            <p v-if="activeOptionDish.description" class="text-sm leading-relaxed text-slate-300">{{ activeOptionDish.description }}</p>
            <!-- Allergen list -->
            <div v-if="activeOptionDish.allergens?.length" class="flex flex-wrap gap-1.5">
              <span class="text-[10px] font-semibold uppercase tracking-widest text-slate-500 self-center shrink-0">{{ t('mktMenu.freeFrom') }}:</span>
              <span
                v-for="a in activeOptionDish.allergens"
                :key="a"
                class="rounded-full border border-amber-500/30 bg-amber-500/8 px-2 py-0.5 text-[11px] font-medium text-amber-300"
              >{{ t(`mktMenu.allergen_${a}`) }}</span>
            </div>
            <!-- Divider between info and option groups (only shown when both exist) -->
            <hr v-if="(activeOptionDish.description || activeOptionDish.allergens?.length) && activeOptionDish.option_groups?.length" class="border-slate-800/60" />
            <!-- Option groups (one per group) -->
            <div
              v-for="grp in activeOptionDish.option_groups"
              :key="grp.id"
              role="group"
              :aria-labelledby="`opt-grp-${grp.id}`"
            >
              <!-- Group label + badges -->
              <div class="flex items-start justify-between gap-2 mb-3">
                <p :id="`opt-grp-${grp.id}`" class="text-sm font-semibold text-white leading-snug">{{ grp.name }}</p>
                <div class="flex items-center gap-1.5 shrink-0">
                  <span
                    class="rounded-full border px-2 py-0.5 text-[10px] font-semibold"
                    :class="grp.min_select > 0
                      ? 'border-rose-500/40 bg-rose-500/10 text-rose-300'
                      : 'border-slate-700/60 bg-slate-900/60 text-slate-400'"
                  >{{ grp.min_select > 0 ? t('mktMenu.optionRequired') : t('mktMenu.optionOptional') }}</span>
                  <span class="text-[10px] text-slate-500 whitespace-nowrap">{{ grp.max_select === 1 ? t('mktMenu.optionChooseOne') : t('mktMenu.optionChooseUp', { max: grp.max_select }) }}</span>
                </div>
              </div>
              <!-- Option buttons -->
              <div class="space-y-2">
                <button
                  v-for="opt in grp.options"
                  :key="opt.id"
                  type="button"
                  :disabled="!opt.is_available || (!isOptionSelected(grp.id, opt.id) && isGroupAtMax(grp))"
                  class="w-full flex items-center gap-3 rounded-xl border px-3.5 py-3 text-start transition-colors ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 disabled:pointer-events-none disabled:opacity-40"
                  :class="isOptionSelected(grp.id, opt.id)
                    ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-white'
                    : 'border-slate-700/60 bg-slate-900/40 text-slate-300 hover:border-slate-600 hover:bg-slate-900/60'"
                  :aria-pressed="isOptionSelected(grp.id, opt.id)"
                  @click="toggleOption(grp, opt.id)"
                >
                  <!-- Indicator: filled dot for radio (single), checkmark for multi -->
                  <span
                    class="flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full border-2 transition-all"
                    :class="isOptionSelected(grp.id, opt.id)
                      ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]'
                      : 'border-slate-600'"
                    aria-hidden="true"
                  >
                    <svg v-if="isOptionSelected(grp.id, opt.id) && grp.max_select > 1" viewBox="0 0 10 10" class="h-2.5 w-2.5 text-slate-950" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 5l2.5 2.5 3.5-4"/></svg>
                    <span v-else-if="isOptionSelected(grp.id, opt.id)" class="h-2 w-2 rounded-full bg-slate-950" aria-hidden="true" />
                  </span>
                  <span class="flex-1 text-sm font-medium">{{ opt.name }}</span>
                  <span
                    v-if="Number(opt.price_delta)"
                    class="shrink-0 text-xs tabular-nums"
                    :class="isOptionSelected(grp.id, opt.id) ? 'text-[var(--color-secondary)]' : 'text-slate-400'"
                  >{{ Number(opt.price_delta) > 0 ? '+' : '' }}{{ fmtPrice(opt.price_delta) }}</span>
                </button>
              </div>
            </div>
          </div>

          <!-- Validation error shown after attempted confirm -->
          <div
            v-if="panelShowErrors && !optionPanelValid"
            class="mx-5 mb-2 flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/8 px-3 py-2"
            role="alert"
          >
            <svg aria-hidden="true" viewBox="0 0 16 16" class="h-3.5 w-3.5 shrink-0 text-rose-400" fill="currentColor">
              <path fill-rule="evenodd" d="M8 15A7 7 0 108 1a7 7 0 000 14zm-.75-9.5a.75.75 0 011.5 0v4a.75.75 0 01-1.5 0v-4zm.75 6a.875.875 0 100-1.75.875.875 0 000 1.75z" clip-rule="evenodd"/>
            </svg>
            <p class="text-xs text-rose-300">{{ t('mktMenu.optionInvalid') }}</p>
          </div>

          <!-- Footer: running unit price + Add CTA -->
          <div class="px-5 pt-3 pb-6 shrink-0 border-t border-slate-800/50">
            <button
              type="button"
              class="ui-press w-full rounded-2xl bg-[var(--color-secondary)] py-3.5 text-sm font-bold text-slate-950 transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
              @click="confirmOptionSelection"
            >
              {{ t('mktMenu.optionConfirm', { price: fmtPrice(optionPanelUnitPrice) }) }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Inline sign-in modal — triggered when a delivery order requires auth -->
    <CustomerAuthModal
      v-if="showAuthModal"
      @close="showAuthModal = false"
      @authenticated="onAuthenticated"
    />

    <!-- Floating back-to-top button -->
    <Transition name="ui-fade">
      <button
        v-if="showBackToTop"
        type="button"
        class="ui-press fixed bottom-24 end-4 z-[1200] flex h-10 w-10 items-center justify-center rounded-full border border-slate-700/60 bg-slate-900/90 shadow-lg backdrop-blur-sm text-slate-300 transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
        :aria-label="t('mktMenu.backToTop')"
        @click="() => window.scrollTo({ top: 0, behavior: 'smooth' })"
      >
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4" aria-hidden="true"><path d="M4 10l4-4 4 4"/></svg>
      </button>
    </Transition>

  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from '../composables/useI18n';
import { useVocabulary } from '../composables/useVocabulary';
import { useCustomerStore } from '../stores/customer';
import CustomerAuthModal from '../components/CustomerAuthModal.vue';
import api from '../lib/api';
import { useToastStore } from '../stores/toast';

const { t, formatCurrency } = useI18n();
const route = useRoute();
const router = useRouter();
const customerStore = useCustomerStore();
const toastStore = useToastStore();

const slug = route.params.slug;

// ── State ─────────────────────────────────────────────────────────────────────
const loading = ref(true);
const fetchError = ref(false);
const restaurant = ref(null);

const { catalog } = useVocabulary(() => restaurant.value?.business_type);

// Returns an emoji placeholder icon appropriate for the restaurant's business_type.
const businessIcon = (r) => {
  const type = r?.business_type || 'restaurant';
  if (type === 'cafe') return '☕';
  if (type === 'bakery') return '🥖';
  if (type === 'pharmacy') return '💊';
  if (type === 'retail' || type === 'grocery') return '🛍️';
  return '🍽️';
};

// ── Happy-hour minutes-left helper (minute resolution) ────────────────────────
const _nowHHMM = ref(new Date().toTimeString().slice(0, 5));
let _hhTick = setInterval(() => { _nowHHMM.value = new Date().toTimeString().slice(0, 5); }, 30_000);
const hhMinutesLeft = (endsAt) => {
  if (!endsAt) return null;
  const [eh, em] = endsAt.split(':').map(Number);
  const [nh, nm] = _nowHHMM.value.split(':').map(Number);
  let diff = (eh * 60 + em) - (nh * 60 + nm);
  if (diff < 0) diff += 1440; // next-day wrap
  return diff <= 120 ? diff : null; // only show when ≤ 2 h left
};
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
    if (!cart.value.length) { checkoutOpen.value = false; return; }
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
  clearInterval(_hhTick);
  window.removeEventListener('scroll', _onPageScroll);
});
// ── Share restaurant link ─────────────────────────────────────────────────────
const menuLinkCopied = ref(false);
let _menuLinkCopyTimer = null;
const shareRestaurant = async () => {
  const url = window.location.href;
  const title = restaurant.value?.name || '';
  try {
    if (navigator.share) {
      await navigator.share({ title, url });
    } else {
      await navigator.clipboard.writeText(url);
      menuLinkCopied.value = true;
      if (_menuLinkCopyTimer) clearTimeout(_menuLinkCopyTimer);
      _menuLinkCopyTimer = setTimeout(() => { menuLinkCopied.value = false; }, 1800);
    }
  } catch { /* user cancelled share or clipboard denied */ }
};

const shareDish = async (dish) => {
  const url = `${window.location.origin}${window.location.pathname}#dish-${dish.slug}`;
  try {
    if (navigator.share) {
      await navigator.share({ title: dish.name, text: dish.description || dish.name, url });
    } else {
      await navigator.clipboard.writeText(url);
      toastStore.show(t('mktMenu.linkCopied'), 'success', 1600);
    }
  } catch { /* user cancelled or clipboard denied */ }
};

const placing = ref(false);
const checkoutError = ref('');
const showAuthModal = ref(false); // opens when delivery order requires sign-in

// After the customer signs in mid-checkout, retry placing the order automatically.
const onAuthenticated = async () => {
  showAuthModal.value = false;
  checkoutError.value = '';
  await customerStore.fetchCustomer(true);
  fetchMktSavedAddresses(); // load addresses now that the customer is signed in
  placeOrder(); // retry with the newly established session
};

// Fulfillment preference — saved to localStorage per restaurant so returning
// delivery customers don't have to re-select every visit.
const MKT_FULFILLMENT_KEY = `mkt:fulfillment:${slug}`;
const _savedFulfillment = (() => {
  try { return localStorage.getItem(MKT_FULFILLMENT_KEY); } catch { return null; }
})();

// Cart: [{slug, name, price, qty}] — persisted to localStorage so items survive
// tab close / crash and navigation back from the marketplace listing page.
const MKT_CART_KEY = `mkt:cart:${slug}`;
const _savedCart = (() => {
  try { return JSON.parse(localStorage.getItem(MKT_CART_KEY) || 'null'); } catch { return null; }
})();
const cart = ref(Array.isArray(_savedCart) ? _savedCart : []);
watch(cart, (v) => {
  try { localStorage.setItem(MKT_CART_KEY, JSON.stringify(v)); } catch { /* quota */ }
}, { deep: true });
watch(() => form.fulfillment_type, (v) => {
  try { localStorage.setItem(MKT_FULFILLMENT_KEY, v); } catch { /* quota */ }
});

const form = reactive({
  fulfillment_type: 'pickup',
  customer_name: '',
  customer_phone: '',
  delivery_address: '',
  delivery_lat: null,
  delivery_lng: null,
  customer_note: '',
});

// Keep the checkout contact fields pre-filled from the signed-in customer so a
// daily customer never retypes name/phone. The menu-fetch pre-fill (below) only
// runs once and only if the session is already resolved; this watcher also covers
// an async session resolve and a mid-checkout sign-in. Only fills EMPTY fields, so
// it never clobbers something the customer typed.
watch(() => customerStore.customer, (c) => {
  if (!c) return;
  if (!form.customer_name) form.customer_name = c.name || '';
  if (!form.customer_phone) form.customer_phone = c.phone || '';
}, { immediate: true });

// ── Saved addresses (signed-in customers) ────────────────────────────────────
const mktSavedAddresses = ref([]);

const fetchMktSavedAddresses = async () => {
  if (!customerStore.isAuthenticated) return;
  try {
    const res = await api.get('/customer/addresses/');
    mktSavedAddresses.value = Array.isArray(res.data) ? res.data : [];
    // Auto-select the most recent saved address for a delivery order so a repeat
    // customer doesn't have to tap to pick it (they can still choose another).
    if (form.fulfillment_type === 'delivery' && !form.delivery_address && mktSavedAddresses.value.length) {
      applyMktSavedAddress(mktSavedAddresses.value[0]);
    }
  } catch {
    // silent — address picker degrades gracefully to manual entry
  }
};

const applyMktSavedAddress = (addr) => {
  form.delivery_address = addr.address || '';
  if (addr.lat != null) form.delivery_lat = addr.lat;
  if (addr.lng != null) form.delivery_lng = addr.lng;
};

const saveAddressAfterOrder = ref(false);
const saveAddressLabel = ref('');

const deleteMktSavedAddress = async (id) => {
  try {
    await api.delete(`/customer/addresses/${id}/`);
    mktSavedAddresses.value = mktSavedAddresses.value.filter((a) => a.id !== id);
  } catch { /* non-critical */ }
};

// When the customer switches to delivery, auto-fill their most recent saved
// address if they haven't picked one yet — one less tap for a daily delivery order.
watch(() => form.fulfillment_type, (ft) => {
  if (ft === 'delivery' && !form.delivery_address && mktSavedAddresses.value.length) {
    applyMktSavedAddress(mktSavedAddresses.value[0]);
  }
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
  // Dishes with option groups open the selection panel on the first add
  if (dish.option_groups?.length && !cartQty(dish.slug)) {
    openOptionPanel(dish);
    return;
  }
  const effectivePrice = (dish.happy_hour && Number(dish.effective_price) < Number(dish.price))
    ? Number(dish.effective_price)
    : Number(dish.price);
  const existing = cart.value.find((i) => i.slug === dish.slug);
  if (existing) {
    if (existing.qty < 99) existing.qty++;
    // refresh happy_hour_ends_at / happy_hour_starts_at in case window changed
    existing.happy_hour_ends_at = dish.happy_hour?.ends_at ?? null;
    existing.happy_hour_starts_at = dish.happy_hour?.starts_at ?? null;
  } else {
    cart.value.push({
      slug: dish.slug,
      name: dish.name,
      price: dish.price,
      unitPrice: effectivePrice,
      qty: 1,
      options: [],
      happy_hour_ends_at: dish.happy_hour?.ends_at ?? null,
      happy_hour_starts_at: dish.happy_hour?.starts_at ?? null,
    });
    toastStore.show(t('mktMenu.addedToCart', { name: dish.name }), 'success', 2000);
  }
};

const addToCartBySlug = (dishSlug) => {
  const existing = cart.value.find((i) => i.slug === dishSlug);
  if (existing && existing.qty < 99) existing.qty++;
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
  cart.value.reduce((s, i) => s + Number(i.unitPrice ?? i.price) * i.qty, 0)
);

// Flash sale discount — mirrors backend: pct applied to food subtotal only
const flashSaleDiscount = computed(() => {
  if (!restaurant.value?.flash_sale) return 0;
  const pct = Number(restaurant.value.flash_sale.discount_pct);
  return pct > 0 ? Math.round(cartTotal.value * pct) / 100 : 0;
});

// Per-dish flash-sale helpers
const flashSalePct = computed(() => Number(restaurant.value?.flash_sale?.discount_pct) || 0);
const dishSalePrice = (price) => {
  const pct = flashSalePct.value;
  if (!pct) return null;
  return Math.round(Number(price) * (100 - pct)) / 100;
};

// Dietary tag badge colours (mirrors DishCard.vue)
const TAG_COLOURS = {
  vegan:       'border-green-500/40 bg-green-500/10 text-green-300',
  vegetarian:  'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
  spicy:       'border-red-500/40 bg-red-500/10 text-red-300',
  gluten_free: 'border-sky-500/40 bg-sky-500/10 text-sky-300',
  halal:       'border-teal-500/40 bg-teal-500/10 text-teal-300',
  kosher:      'border-violet-500/40 bg-violet-500/10 text-violet-300',
  nuts:        'border-amber-500/40 bg-amber-500/10 text-amber-300',
};
const tagBadgeClass = (tag) => TAG_COLOURS[tag] ?? 'border-slate-700/50 bg-slate-900/60 text-slate-400';

// ── Allergen "Free from" filter ───────────────────────────────────────────────
const ALLERGEN_KEY = `mkt-allergens-${slug}`;
const FAVORITES_KEY = `mkt-favs-${slug}`;
const favorites = ref((() => {
  try { return new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]')); } catch { return new Set(); }
})());
const isFavorite = (dishSlug) => favorites.value.has(dishSlug);
const toggleFavorite = (dish) => {
  const next = new Set(favorites.value);
  if (next.has(dish.slug)) { next.delete(dish.slug); } else { next.add(dish.slug); }
  favorites.value = next;
  try { localStorage.setItem(FAVORITES_KEY, JSON.stringify([...next])); } catch { /* quota */ }
};

const RECENTLY_VIEWED_KEY = `mkt-recent-${slug}`;
const RECENTLY_VIEWED_MAX = 6;
const recentlyViewed = ref((() => {
  try { return JSON.parse(localStorage.getItem(RECENTLY_VIEWED_KEY) || '[]'); } catch { return []; }
})());
const trackRecentlyViewed = (dish) => {
  const list = recentlyViewed.value.filter((d) => d.slug !== dish.slug);
  list.unshift({ slug: dish.slug, name: dish.name, price: dish.price, effective_price: dish.effective_price, image_url: dish.image_url || '', is_available: dish.is_available });
  recentlyViewed.value = list.slice(0, RECENTLY_VIEWED_MAX);
  try { localStorage.setItem(RECENTLY_VIEWED_KEY, JSON.stringify(recentlyViewed.value)); } catch { /* quota */ }
};
const selectedAllergenFilter = ref((() => {
  try { return JSON.parse(localStorage.getItem(ALLERGEN_KEY) || '[]'); } catch { return []; }
})());

const favoriteDishes = computed(() => {
  if (!favorites.value.size) return [];
  const all = [];
  for (const sc of (restaurant.value?.super_categories || [])) {
    for (const cat of (sc.categories || [])) {
      for (const d of (cat.dishes || [])) {
        if (favorites.value.has(d.slug)) all.push(d);
      }
    }
  }
  return all;
});

const availableAllergens = computed(() => {
  const seen = new Set();
  for (const sc of restaurant.value?.super_categories || []) {
    for (const cat of sc.categories || []) {
      for (const dish of cat.dishes || []) {
        for (const a of dish.allergens || []) seen.add(a);
      }
    }
  }
  return [...seen].sort();
});

const toggleAllergenFilter = (allergen) => {
  const idx = selectedAllergenFilter.value.indexOf(allergen);
  if (idx >= 0) selectedAllergenFilter.value.splice(idx, 1);
  else selectedAllergenFilter.value.push(allergen);
  try { localStorage.setItem(ALLERGEN_KEY, JSON.stringify(selectedAllergenFilter.value)); } catch { /* quota */ }
};

/** Returns true when the dish is safe for the active allergen exclusions. */
const dishPassesAllergenFilter = (dish) => {
  if (!selectedAllergenFilter.value.length) return true;
  return !selectedAllergenFilter.value.some(a => (dish.allergens || []).includes(a));
};

/** Super-categories with allergen-filtered dish lists (empty cats/SCs hidden). */
const filteredSuperCategories = computed(() => {
  if (!selectedAllergenFilter.value.length) return restaurant.value?.super_categories || [];
  return (restaurant.value?.super_categories || []).map(sc => ({
    ...sc,
    categories: (sc.categories || []).map(cat => ({
      ...cat,
      dishes: (cat.dishes || []).filter(dishPassesAllergenFilter),
    })).filter(cat => cat.dishes.length > 0),
  })).filter(sc => sc.categories.length > 0);
});

/** How many dishes are hidden by the active allergen filter. */
const allergenHiddenCount = computed(() => {
  if (!selectedAllergenFilter.value.length) return 0;
  let total = 0;
  for (const sc of (restaurant.value?.super_categories || [])) {
    for (const cat of (sc.categories || [])) {
      for (const d of (cat.dishes || [])) {
        if (!dishPassesAllergenFilter(d)) total += 1;
      }
    }
  }
  return total;
});

// ── Option group selection panel ─────────────────────────────────────────────
const activeOptionDish = ref(null);   // dish object when panel is open, null = closed
const optionPanelRef = ref(null);
const panelSelections = ref({});      // groupId → [selectedOptionId, ...]
const panelShowErrors = ref(false);

const openOptionPanel = (dish) => {
  trackRecentlyViewed(dish);
  const sel = {};
  for (const grp of dish.option_groups || []) sel[grp.id] = [];
  panelSelections.value = sel;
  panelShowErrors.value = false;
  activeOptionDish.value = dish;
  nextTick(() => optionPanelRef.value?.querySelector('button:not([disabled])')?.focus());
};

const closeOptionPanel = () => { activeOptionDish.value = null; };

const isOptionSelected = (groupId, optionId) =>
  (panelSelections.value[groupId] || []).includes(optionId);

const isGroupAtMax = (grp) =>
  (panelSelections.value[grp.id] || []).length >= grp.max_select;

const toggleOption = (grp, optionId) => {
  const sel = panelSelections.value[grp.id] || [];
  const idx = sel.indexOf(optionId);
  if (grp.max_select === 1) {
    // Single-select: toggle (selecting the same option deselects it)
    panelSelections.value[grp.id] = idx >= 0 ? [] : [optionId];
  } else {
    // Multi-select: add up to max_select
    if (idx >= 0) {
      panelSelections.value[grp.id] = sel.filter(id => id !== optionId);
    } else if (sel.length < grp.max_select) {
      panelSelections.value[grp.id] = [...sel, optionId];
    }
  }
};

const optionPanelValid = computed(() => {
  if (!activeOptionDish.value) return false;
  return (activeOptionDish.value.option_groups || []).every(
    grp => (panelSelections.value[grp.id] || []).length >= grp.min_select
  );
});

const optionPanelUnitPrice = computed(() => {
  if (!activeOptionDish.value) return 0;
  const d = activeOptionDish.value;
  // Use happy-hour effective price as base; option deltas are never discounted.
  let price = (d.happy_hour && Number(d.effective_price) < Number(d.price))
    ? Number(d.effective_price)
    : Number(d.price) || 0;
  for (const grp of d.option_groups || []) {
    for (const opt of grp.options || []) {
      if (isOptionSelected(grp.id, opt.id)) price += Number(opt.price_delta) || 0;
    }
  }
  return price;
});

const confirmOptionSelection = () => {
  const dish = activeOptionDish.value;
  if (!dish) return;
  // Validate only when the dish actually has option groups
  if (dish.option_groups?.length && !optionPanelValid.value) {
    panelShowErrors.value = true;
    return;
  }
  const selectedOptions = [];
  for (const grp of dish.option_groups || []) {
    for (const opt of grp.options || []) {
      if (isOptionSelected(grp.id, opt.id)) {
        selectedOptions.push({ id: opt.id, name: opt.name, price_delta: opt.price_delta });
      }
    }
  }
  const dishEffectiveBase = (dish.happy_hour && Number(dish.effective_price) < Number(dish.price))
    ? Number(dish.effective_price)
    : Number(dish.price);
  const unitPrice = dish.option_groups?.length ? optionPanelUnitPrice.value : dishEffectiveBase;
  const existing = cart.value.find((i) => i.slug === dish.slug);
  if (existing) {
    if (existing.qty < 99) existing.qty++;
    existing.unitPrice = unitPrice;
    existing.options = selectedOptions;
    existing.happy_hour_ends_at = dish.happy_hour?.ends_at ?? null;
    existing.happy_hour_starts_at = dish.happy_hour?.starts_at ?? null;
  } else {
    cart.value.push({
      slug: dish.slug,
      name: dish.name,
      price: dish.price,
      unitPrice,
      qty: 1,
      options: selectedOptions,
      happy_hour_ends_at: dish.happy_hour?.ends_at ?? null,
      happy_hour_starts_at: dish.happy_hour?.starts_at ?? null,
    });
  }
  closeOptionPanel();
};

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
const needsLocation = computed(
  () => form.fulfillment_type === 'delivery'
    && deliveryPricing.value.perKm > 0
    && (form.delivery_lat == null || form.delivery_lng == null),
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
const deliveryMinOrder = computed(() => {
  const raw = restaurant.value?.delivery_minimum_order;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 0;
});
const deliveryMinGap = computed(() =>
  form.fulfillment_type === 'delivery'
    ? Math.max(0, deliveryMinOrder.value - cartTotal.value)
    : 0
);
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

// Projected points earned on this order (mirrors backend: floor(subtotal * points_per_unit))
const loyaltyEarnProjection = computed(() => {
  if (!loyaltyConfig.value?.enabled) return 0;
  const ppu = Number(loyaltyConfig.value.points_per_unit) || 0;
  if (ppu <= 0) return 0;
  const subtotal = Number(orderBaseTotal.value) || 0;
  if (subtotal <= 0) return 0;
  return Math.floor(subtotal * ppu);
});

// Marketplace orders are pay-now: settled in full from the wallet at checkout.
const walletBalanceNum = computed(() => {
  const n = Number(customer.value?.wallet_balance);
  return Number.isFinite(n) && n > 0 ? n : 0;
});
const walletCoversTotal = computed(() => walletBalanceNum.value >= orderTotal.value);
// Trusted-customer cash-on-handover (COD): eligibility comes from the marketplace
// menu payload (backend reports cod_eligible for the signed-in customer).
const codEligible = computed(() => restaurant.value?.cod_eligible === true);
const paymentMethod = ref('wallet'); // 'wallet' | 'cash' (cash only when codEligible)
const codChosen = computed(
  () => codEligible.value && paymentMethod.value === 'cash'
);
// If eligibility drops (e.g. a different restaurant), fall back to wallet.
watch(codEligible, (ok) => {
  if (!ok && paymentMethod.value === 'cash') paymentMethod.value = 'wallet';
});
const prepayShortfall = computed(
  () => customerStore.isAuthenticated && orderTotal.value > 0 && !walletCoversTotal.value && !codChosen.value
);

// ── Pre-order prep ETA ('Ready in ~X–Y min') for the menu header ─────────────
// Kitchen prep estimate shown BEFORE ordering (Uber Eats / Deliveroo pattern).
// prep_eta_min/max come from the marketplace menu payload.
const prepEta = computed(() => {
  const lo = restaurant.value?.prep_eta_min;
  const hi = restaurant.value?.prep_eta_max;
  if (lo == null || hi == null) return null;
  return { min: lo, max: hi };
});

// ── Opening hours ─────────────────────────────────────────────────────────────
const _JS_DAY_KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
const _SCHEDULE_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
// Reference Mondays for Intl.DateTimeFormat day-name generation (avoids 21 i18n keys).
// 2023-01-02 is a Monday; index 0=Mon...index 6=Sun.
const _scheduleRefDates = _SCHEDULE_KEYS.map((_, i) => new Date(2023, 0, 2 + i));

const todayHours = computed(() => {
  const sched = restaurant.value?.business_hours_schedule;
  if (!sched || typeof sched !== 'object') return null;
  const key = _JS_DAY_KEYS[new Date().getDay()];
  const entry = sched[key];
  if (!entry || typeof entry !== 'object') return { closed: true };
  if (!entry.enabled) return { closed: true };
  return { closed: false, open: entry.open, close: entry.close };
});

const hoursExpanded = ref(false);

const weeklyHours = computed(() => {
  const sched = restaurant.value?.business_hours_schedule;
  if (!sched || typeof sched !== 'object') return null;
  const todayKey = _JS_DAY_KEYS[new Date().getDay()];
  return _SCHEDULE_KEYS.map((key, idx) => {
    const entry = sched[key];
    const enabled = entry?.enabled;
    const label = _scheduleRefDates[idx].toLocaleDateString(undefined, { weekday: 'short' });
    return {
      key,
      label,
      isToday: key === todayKey,
      open: enabled ? entry.open : null,
      close: enabled ? entry.close : null,
    };
  });
});

const fmtPrice = (amount) => {
  const cur = restaurant.value?.currency || 'MAD';
  try {
    return formatCurrency(Number(amount || 0), cur);
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
    // Restore fulfillment preference — only if that type is available here
    if (_savedFulfillment === 'delivery' && res.data?.delivery_enabled) {
      form.fulfillment_type = 'delivery';
    }
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
  if (!form.customer_phone.trim()) {
    checkoutError.value = t('mktMenu.phoneRequired');
    return;
  }
  if (form.customer_phone.replace(/\D/g, '').length < 7) {
    checkoutError.value = t('mktMenu.phoneInvalid');
    return;
  }
  if (form.fulfillment_type === 'delivery' && !form.delivery_address.trim()) {
    checkoutError.value = t('mktMenu.addressRequired');
    return;
  }
  if (scheduleEnabled.value) {
    if (!scheduledFor.value) {
      checkoutError.value = t('mktMenu.scheduleRequired');
      return;
    }
    if (scheduledFor.value < minScheduleDatetime.value) {
      checkoutError.value = t('mktMenu.scheduleInPast');
      return;
    }
  }
  // Pay-now: a signed-in customer's wallet must cover the full total
  // (unless they chose trusted cash-on-handover).
  if (customerStore.isAuthenticated && orderTotal.value > 0 && !codChosen.value && walletBalanceNum.value < orderTotal.value) {
    checkoutError.value = t('mktMenu.walletTopUpRequired', {
      balance: fmtPrice(walletBalanceNum.value),
      total: fmtPrice(orderTotal.value),
    });
    return;
  }

  // Stale happy-hour guard: if any cart line was priced during a happy-hour window
  // that has since ended, refetch prices and let the user re-confirm.
  // Overnight windows (starts_at > ends_at, e.g. 22:00–02:00) are handled
  // correctly: ends_at='02:00' at 23:30 is NOT stale — the inactive gap is 02:00–22:00.
  const nowHHMM = new Date().toTimeString().slice(0, 5); // "HH:MM"
  const hasStaleHH = cart.value.some((i) => {
    const endsAt = i.happy_hour_ends_at;
    if (typeof endsAt !== 'string') return false;
    const startsAt = i.happy_hour_starts_at;
    const isOvernight = typeof startsAt === 'string' && startsAt > endsAt;
    // Overnight: stale only in the gap between end and next start (daytime).
    if (isOvernight) return nowHHMM >= endsAt && nowHHMM < startsAt;
    // Normal window: stale when current time has passed ends_at.
    return nowHHMM >= endsAt;
  });
  if (hasStaleHH) {
    await fetchMenu();
    // Re-sync prices: for each cart line find the current effective_price
    const allDishes = (restaurant.value?.super_categories || [])
      .flatMap((sc) => sc.categories || [])
      .flatMap((c) => c.dishes || []);
    const dishMap = new Map(allDishes.map((d) => [d.slug, d]));
    for (const line of cart.value) {
      const live = dishMap.get(line.slug);
      if (!live) continue;
      const liveEffective = (live.happy_hour && Number(live.effective_price) < Number(live.price))
        ? Number(live.effective_price)
        : Number(live.price);
      line.unitPrice = liveEffective;
      line.happy_hour_ends_at = live.happy_hour?.ends_at ?? null;
      line.happy_hour_starts_at = live.happy_hour?.starts_at ?? null;
    }
    toastStore.show(t('happyHour.ended'), 'info');
    return; // let user re-confirm
  }

  placing.value = true;
  try {
    const items = cart.value.map((i) => ({
      slug: i.slug,
      qty: i.qty,
      ...(i.options?.length ? { option_ids: i.options.map(o => o.id) } : {}),
    }));
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
    };
    if (codChosen.value) {
      payload.payment_method = 'cash';
    } else {
      payload.use_wallet = true;
    }
    if (scheduleEnabled.value && scheduledFor.value) {
      const dt = new Date(scheduledFor.value);
      if (!Number.isNaN(dt.getTime())) payload.scheduled_for = dt.toISOString();
    }
    if (useLoyalty.value && loyaltyAvailable.value && loyaltyPoints.value > 0) {
      payload.redeem_points = loyaltyPoints.value;
    }
    const res = await api.post('/marketplace/order/', payload);
    // Optionally persist the delivery address for future orders.
    if (form.fulfillment_type === 'delivery' && saveAddressAfterOrder.value && form.delivery_address) {
      try {
        const saved = await api.post('/customer/addresses/', {
          label: saveAddressLabel.value.trim() || '',
          address: form.delivery_address,
          location_url: '',
          lat: form.delivery_lat || null,
          lng: form.delivery_lng || null,
        });
        // Prepend so it becomes the auto-selected address next time.
        mktSavedAddresses.value = [saved.data, ...mktSavedAddresses.value].slice(0, 10);
      } catch { /* non-critical */ }
    }
    // Stamp localStorage so MarketplaceOrderStatus can show a "just placed" banner
    try {
      localStorage.setItem('mktLastOrderNumber', String(res.data.order_number));
      localStorage.setItem('mktLastOrderAt', String(Date.now()));
      localStorage.setItem('mktLastOrderSlug', String(slug));
    } catch { /* storage unavailable */ }
    // Clear the persisted cart now that the order is placed
    try { localStorage.removeItem(MKT_CART_KEY); } catch { /* ignore */ }
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
    } else if (code === 'stale_options') {
      checkoutError.value = t('cartPage.staleOptions');
      toastStore.show(t('cartPage.staleOptions'), 'error');
    } else if (code === 'restaurant_closed') {
      checkoutError.value = t('mktMenu.restaurantClosed');
    } else if (code === 'items_unavailable') {
      checkoutError.value = t('mktMenu.itemsUnavailable');
    } else if (code === 'below_delivery_minimum') {
      const minimum = err?.response?.data?.minimum ? fmtPrice(Number(err.response.data.minimum)) : '';
      checkoutError.value = minimum
        ? t('mktMenu.deliveryMinOrderNotMet', { amount: minimum })
        : t('mktMenu.orderError');
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
  for (const sc of filteredSuperCategories.value) {
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

/** Search results grouped by category across all super-categories (also respects allergen filter). */
const mktSearchResults = computed(() => {
  const q = mktSearchQuery.value.trim().toLowerCase();
  if (!q) return [];
  const groups = [];
  for (const sc of restaurant.value?.super_categories || []) {
    for (const cat of sc.categories || []) {
      const matched = (cat.dishes || []).filter(d =>
        dishPassesAllergenFilter(d) && (
          (d.name || '').toLowerCase().includes(q) ||
          (d.description || '').toLowerCase().includes(q)
        )
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

// Build a slug → live dish map from the loaded menu for price resolution.
const _buildDishMap = () => {
  const map = new Map();
  for (const sc of restaurant.value?.super_categories || []) {
    for (const cat of sc.categories || []) {
      for (const dish of cat.dishes || []) {
        if (dish.slug) map.set(dish.slug, dish);
      }
    }
  }
  return map;
};

// Reactive set of cart slugs whose live dish is currently marked unavailable.
// Updates whenever the restaurant menu refreshes or the cart changes.
const unavailableSlugs = computed(() => {
  const map = _buildDishMap();
  const slugs = new Set();
  for (const item of cart.value) {
    const live = map.get(item.slug);
    if (live && live.is_available === false) slugs.add(item.slug);
  }
  return slugs;
});

// Pre-fill the cart from a re-order navigation (items_snapshot from CustomerOrderRef).
// Called after fetchMenu so live prices are available. Silently drops items no longer
// on the menu and shows a toast only when at least one price changed or an item was dropped.
const applyReorderItems = () => {
  const items = history.state?.reorderItems;
  if (!Array.isArray(items) || !items.length) return;
  const dishMap = _buildDishMap();
  const newCart = [];
  let priceChanged = false;
  let dropped = false;
  for (const item of items) {
    if (!item.slug) continue;
    const live = dishMap.get(item.slug);
    if (!live) { dropped = true; continue; }
    const snapshotPrice = Number(item.price) || 0;
    const livePrice = Number(live.price) || 0;
    if (snapshotPrice !== livePrice) priceChanged = true;
    newCart.push({
      slug: live.slug,
      name: live.name || item.name || live.slug,
      price: livePrice,
      unitPrice: livePrice,
      qty: Math.max(1, Math.floor(Number(item.qty) || 1)),
      options: [],
    });
  }
  if (!newCart.length) return;
  cart.value = newCart;
  if (priceChanged || dropped) {
    toastStore.show(t('cartPage.reorderPriceNote'), 'info');
  }
};

const showBackToTop = ref(false);
const _onPageScroll = () => { showBackToTop.value = window.scrollY > 400; };

onMounted(async () => {
  window.addEventListener('scroll', _onPageScroll, { passive: true });
  await customerStore.fetchCustomer();
  fetchMktSavedAddresses(); // non-blocking — degrades gracefully if unauthenticated
  await fetchMenu();
  applyReorderItems(); // resolve live prices after menu is loaded
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
