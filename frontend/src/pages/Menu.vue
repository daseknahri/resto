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
      <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/60 to-slate-950/10" />
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(20,184,166,0.10),transparent_32%),radial-gradient(circle_at_bottom_left,rgba(245,158,11,0.10),transparent_30%)]" />

      <div class="relative flex h-full flex-col justify-end p-4 pb-5 sm:p-6 sm:pb-6">
        <div class="flex items-end gap-3.5">
          <img
            v-if="logoImage"
            :src="logoImage"
            :alt="`${tenantName} logo`"
            class="h-16 w-16 shrink-0 rounded-2xl border-2 object-cover shadow-2xl shadow-black/60 sm:h-[4.5rem] sm:w-[4.5rem] transition-colors duration-500"
            :class="isRestaurantOpen ? 'border-[var(--color-secondary)]/60' : 'border-white/20'"
            loading="eager"
            decoding="async"
            @error="handleLogoImageError"
          />
          <div class="min-w-0 space-y-1">
            <h1 class="ui-display text-2xl font-semibold tracking-tight text-white sm:text-3xl drop-shadow-lg">{{ tenantName }}</h1>
            <p v-if="tenantDescription" class="line-clamp-1 text-xs text-slate-300/75 leading-relaxed" :title="tenantDescription">{{ tenantDescription }}</p>
          </div>
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <span
            class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold backdrop-blur-sm"
            :style="isRestaurantOpen
              ? 'border-color:rgba(52,211,153,0.40);background:rgba(16,185,129,0.14);color:rgb(110,231,183)'
              : 'border-color:rgba(239,68,68,0.35);background:rgba(239,68,68,0.12);color:rgb(252,165,165)'"
            :aria-label="statusLabel || (isRestaurantOpen ? t('customerLeadPage.openNow') : t('customerLeadPage.closedNow'))"
          >
            <span class="relative inline-flex shrink-0" aria-hidden="true">
              <span v-if="isRestaurantOpen" class="animate-ping absolute inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 opacity-60" />
              <span class="relative inline-block h-1.5 w-1.5 rounded-full" :style="isRestaurantOpen ? 'background:rgb(52,211,153)' : 'background:rgb(239,68,68)'" />
            </span>
            {{ statusLabel }}
          </span>
          <RouterLink
            v-if="superCategories.length > 1"
            :to="{ name: 'menu' }"
            class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-900/60 px-2.5 py-1 text-xs font-semibold text-slate-300 backdrop-blur-sm hover:border-slate-500/80 hover:text-white transition-colors"
          >
            <AppIcon name="arrowLeft" class="h-3 w-3 rtl:scale-x-[-1]" aria-hidden="true" />
            {{ t('menuSelect.backToMenus') }}
          </RouterLink>
          <span v-if="locationLine" class="inline-flex items-center gap-1 rounded-full border border-slate-700/60 bg-slate-900/55 px-2.5 py-1 text-xs text-slate-300 backdrop-blur-sm">
            <AppIcon name="info" class="h-3 w-3 shrink-0 text-slate-400" aria-hidden="true" />{{ locationLine }}
          </span>
          <span
            v-if="ratingSummary && ratingSummary.count > 0"
            class="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs backdrop-blur-sm"
            :aria-label="t('menu.ratingLabel', { avg: ratingSummary.average?.toFixed(1), count: ratingSummary.count })"
          >
            <span class="text-amber-400 text-[11px]" aria-hidden="true">★</span>
            <span class="font-semibold text-amber-200">{{ ratingSummary.average !== null ? ratingSummary.average.toFixed(1) : '' }}</span>
            <span class="text-amber-400/60 text-[10px]">({{ ratingSummary.count }})</span>
          </span>
        </div>
      </div>
    </header>

    <!-- ══ Table context banner ══ -->
    <div v-if="tableContextBanner" class="mx-3 mt-3 flex items-center justify-between gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/8 px-4 py-3 text-sm text-emerald-100 shadow-sm shadow-black/20">
      <span class="flex min-w-0 items-center gap-2 truncate font-medium" :title="tableContextBanner">
        <AppIcon name="check" class="h-4 w-4 shrink-0 text-emerald-400" aria-hidden="true" />
        {{ tableContextBanner }}
      </span>
      <button
        type="button"
        class="ui-touch-target shrink-0 rounded-xl border px-3.5 text-xs font-semibold transition active:scale-95 disabled:opacity-50"
        :class="waiterCooldown > 0
          ? 'border-emerald-500/40 bg-emerald-500/12 text-emerald-300 hover:bg-emerald-500/20'
          : 'border-amber-400/50 bg-amber-500/15 text-amber-200 hover:bg-amber-500/25'"
        :disabled="callingWaiter || waiterCooldown > 0"
        @click="callWaiter"
      >
        <!-- spinner while calling -->
        <svg v-if="callingWaiter" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="inline-block h-3.5 w-3.5 animate-spin"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
        <!-- check icon after success -->
        <svg v-else-if="waiterCooldown > 0" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="inline-block h-3.5 w-3.5"><path d="M2.5 8.5 6 12 13.5 4"/></svg>
        <!-- bell icon default -->
        <svg v-else aria-hidden="true" viewBox="0 0 16 16" fill="currentColor" class="inline-block h-3.5 w-3.5"><path d="M8 16a2 2 0 0 0 2-2H6a2 2 0 0 0 2 2ZM8 1.918l-.797.161A4.002 4.002 0 0 0 4 6c0 .628-.134 2.197-.459 3.742-.16.767-.376 1.566-.663 2.258h10.244c-.287-.692-.502-1.49-.663-2.258C12.134 8.197 12 6.628 12 6a4.002 4.002 0 0 0-3.203-3.92L8 1.917Z"/></svg>
        {{ callingWaiter ? t('menu.callingWaiter') : (waiterCooldown > 0 ? t('menu.waiterNotifiedCooldown', { sec: waiterCooldown }) : t('menu.callWaiter')) }}
      </button>
    </div>

    <!-- ══ Sticky categories bar ══ -->
    <nav v-if="visibleCategories.length > 0" :aria-label="t('menu.categoryNav')" class="ui-menu-category-nav sticky z-20" :style="{ top: headerOffset + 'px' }">
      <div class="relative">
        <div
          ref="pillRowEl"
          class="flex gap-1.5 overflow-x-auto px-3 py-2.5 sm:px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          <button
            v-for="cat in visibleCategories"
            :key="cat.slug"
            :data-cat-pill="cat.slug"
            class="ui-pill-nav shrink-0 whitespace-nowrap px-3.5 py-1.5 text-xs font-medium"
            :data-active="activeCategorySlug === cat.slug"
            :aria-current="activeCategorySlug === cat.slug ? 'page' : undefined"
            @click="scrollToSection(cat.slug)"
          >{{ cat.name }}</button>
          <template v-if="isOverflowing">
            <span class="mx-1 w-px shrink-0 self-stretch bg-slate-700/50" aria-hidden="true" />
            <button
              ref="catSheetTriggerEl"
              class="ui-pill-nav shrink-0 px-3 py-1.5 text-xs font-bold tracking-widest"
              :data-active="catSheetOpen"
              :aria-expanded="catSheetOpen"
              :aria-label="t('menu.allCategories')"
              @click="catSheetOpen = !catSheetOpen"
            >···</button>
          </template>
        </div>

        <!-- All-categories sheet -->
        <Transition name="cat-sheet">
          <div
            v-if="catSheetOpen"
            ref="catSheetEl"
            class="absolute left-0 right-0 top-full z-30 border-b border-slate-800/60 bg-slate-950/98 px-4 py-4 backdrop-blur-xl"
            @keydown.escape="catSheetOpen = false; $nextTick(() => catSheetTriggerEl?.focus())"
          >
            <div class="flex flex-wrap gap-2">
              <button
                v-for="cat in visibleCategories"
                :key="`sheet-${cat.slug}`"
                class="ui-pill-nav whitespace-nowrap px-3.5 py-1.5 text-xs font-medium"
                :data-active="activeCategorySlug === cat.slug"
                @click="scrollToSection(cat.slug); catSheetOpen = false"
              >{{ cat.name }}</button>
            </div>
          </div>
        </Transition>
      </div>

      <!-- Allergen strip -->
      <div v-if="availableAllergens.length" role="group" :aria-label="t('menu.allergenFilter')" class="flex items-center gap-2 overflow-x-auto border-t border-slate-800/40 px-3 py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <span class="shrink-0 text-[10px] font-semibold uppercase tracking-widest text-slate-500">{{ t('menu.freeFrom') }}</span>
        <button
          v-for="allergen in availableAllergens"
          :key="allergen"
          :aria-pressed="selectedAllergenFilter.includes(allergen)"
          class="ui-touch-target shrink-0 whitespace-nowrap rounded-full border px-2.5 text-[11px] font-medium transition-colors"
          :class="selectedAllergenFilter.includes(allergen)
            ? 'border-amber-400/70 bg-amber-500/20 text-amber-200'
            : 'border-slate-700 bg-slate-900/60 text-slate-400 hover:border-slate-600 hover:text-slate-300'"
          @click="toggleAllergenFilter(allergen)"
        >{{ t(`menu.allergen_${allergen}`) }}</button>
      </div>

      <!-- Search strip -->
      <div class="border-t border-slate-800/40 px-3 py-2">
        <div class="relative flex items-center">
          <span class="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden="true">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5"><circle cx="6.5" cy="6.5" r="4"/><path d="M10.5 10.5 14 14"/></svg>
          </span>
          <input
            v-model="menuSearchQuery"
            type="search"
            :placeholder="t('menu.dishSearchPlaceholder')"
            :aria-label="t('menu.search')"
            class="w-full rounded-xl border border-slate-700/60 bg-slate-900/60 py-1.5 ps-8 pe-8 text-[13px] text-slate-200 placeholder-slate-500 outline-none transition-colors focus:border-[color:var(--color-secondary)]/50 focus:ring-1 focus:ring-[color:var(--color-secondary)]/25 [&::-webkit-search-cancel-button]:hidden"
          />
          <button
            v-if="isSearchActive"
            type="button"
            class="absolute end-2.5 top-1/2 -translate-y-1/2 rounded-full p-0.5 text-slate-500 transition-colors hover:text-slate-300"
            :aria-label="t('menu.searchClear')"
            @click="menuSearchQuery = ''"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-3.5 w-3.5" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>
          </button>
        </div>
      </div>
    </nav>

    <!-- ══ Loyalty programme teaser ══ -->
    <div
      v-if="loyaltyConfig?.enabled && !isBrowseOnly"
      class="ui-reveal mx-3 mt-3 flex items-center gap-2.5 rounded-xl border border-violet-500/25 bg-violet-500/8 px-4 py-2 sm:mx-4"
      :style="{ '--ui-delay': '50ms' }"
      role="note"
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0 text-violet-400" aria-hidden="true">
        <path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z" />
      </svg>
      <div class="min-w-0 flex-1">
        <p class="text-[12px] font-semibold leading-tight text-violet-200">
          {{ customerStore.isAuthenticated && loyaltyPoints > 0
              ? t('menu.loyaltyTeaserPts', { points: loyaltyPoints })
              : t('menu.loyaltyTeaserEarn') }}
        </p>
        <p v-if="loyaltyAvailable" class="mt-0.5 text-[10px] leading-tight text-violet-400/80">{{ t('menu.loyaltyTeaserRedeem') }}</p>
        <RouterLink
          v-else-if="!customerStore.isAuthenticated"
          :to="{ name: 'customer-account' }"
          class="mt-0.5 block text-[10px] leading-tight text-violet-400/80 underline hover:text-violet-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-400/40 rounded"
        >{{ t('menu.loyaltySignIn') }}</RouterLink>
      </div>
      <span
        v-if="customerStore.isAuthenticated && loyaltyPoints > 0"
        class="shrink-0 rounded-full border border-violet-500/20 bg-violet-500/15 px-2 py-0.5 text-[11px] font-bold tabular-nums text-violet-300"
        :aria-label="`${loyaltyPoints} ${t('menu.loyaltyTeaserPts', { points: '' }).trim()}`"
      >{{ loyaltyPoints }}</span>
    </div>

    <!-- ══ Recent customer reviews ══ -->
    <div
      v-if="recentReviews.length"
      class="ui-reveal mt-3 space-y-2"
      :style="{ '--ui-delay': '80ms' }"
    >
      <p class="ui-kicker px-3 sm:px-4">{{ t('mktMenu.reviewsTitle') }}</p>
      <div class="flex gap-2.5 overflow-x-auto px-3 pb-1 sm:px-4 snap-x" style="scrollbar-width: none; -webkit-overflow-scrolling: touch;">
        <div
          v-for="(review, idx) in recentReviews"
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

    <!-- ══ Sections ══ -->
    <div class="px-3 sm:px-4 mt-4 space-y-6 sm:space-y-7">

      <!-- ── Search results (query active) ────────────────────────────────── -->
      <template v-if="isSearchActive">
        <!-- Has results -->
        <template v-if="menuSearchResults.length">
          <p class="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
            {{ t('menu.searchResultsKicker') }}
            <span class="ms-1.5 font-normal normal-case tabular-nums text-slate-600">({{ totalSearchCount }})</span>
          </p>
          <section
            v-for="group in menuSearchResults"
            :key="group.category.slug"
            class="space-y-3"
          >
            <h2 class="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
              <span class="h-px w-4 shrink-0 rounded-full" style="background:var(--color-secondary)" aria-hidden="true" />
              {{ group.category.name }}
            </h2>
            <div :class="dishGridClass">
              <DishCard
                v-for="dish in group.dishes"
                :key="dish.slug"
                :dish="dish"
                :layout="cardLayout"
                :category-slug="group.category.slug"
                :currency="cartCurrency"
                :is-browse-only="isBrowseOnly"
                :is-open="isRestaurantOpen"
              />
            </div>
          </section>
        </template>

        <!-- No results -->
        <div
          v-else
          class="flex flex-col items-center gap-3 rounded-2xl border border-slate-800/50 bg-slate-900/30 px-4 py-12 text-center"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" class="h-10 w-10 text-slate-700" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.25"/><path d="M13 13 17 17"/></svg>
          <p class="text-sm font-medium text-slate-400">{{ t('menu.noMatchDish') }}</p>
          <button type="button" class="text-xs text-slate-500 underline transition-colors hover:text-slate-300" @click="menuSearchQuery = ''">{{ t('menu.searchClear') }}</button>
        </div>
      </template>

      <!-- ── Normal category sections (search inactive) ──────────────────── -->
      <template v-else>
        <section
          v-for="(cat, index) in visibleCategories"
          :id="`section-${cat.slug}`"
          :key="cat.slug"
          :ref="el => registerSection(el, cat.slug)"
          :data-slug="cat.slug"
          class="ui-reveal scroll-mt-24 space-y-3 md:scroll-mt-32"
          :style="{ '--ui-delay': `${Math.min(index, 6) * 40}ms` }"
        >
          <!-- Section header -->
          <div class="flex items-center justify-between gap-3 border-b border-slate-800/60 pb-3">
            <div class="flex items-center gap-3 min-w-0">
              <span
                class="shrink-0 block h-7 w-1 rounded-full"
                style="background:linear-gradient(180deg,var(--color-secondary) 0%,var(--color-primary) 100%)"
                aria-hidden="true"
              />
              <div class="min-w-0">
                <h2 class="ui-display text-xl font-semibold leading-tight text-white sm:text-[1.35rem] tracking-tight">{{ cat.name }}</h2>
                <p v-if="cat.description" class="mt-0.5 line-clamp-1 text-[11px] text-slate-500 leading-relaxed" :title="cat.description">{{ cat.description }}</p>
              </div>
            </div>
            <span
              v-if="menu.dishes[cat.slug]?.length"
              class="shrink-0 rounded-full border border-slate-800/80 bg-slate-900/70 px-2.5 py-0.5 text-[11px] font-medium text-slate-500 tabular-nums"
              :aria-label="`${sectionDishes(cat.slug).length} items`"
            >{{ sectionDishes(cat.slug).length }}</span>
          </div>

          <!-- Loading skeletons -->
          <div v-if="!menu.dishes[cat.slug]" :class="dishGridClass" aria-busy="true" aria-label="Loading dishes">
            <div v-for="n in 3" :key="n" class="ui-skeleton" :class="cardLayout === 'card' ? 'h-80 rounded-[1.8rem]' : 'h-[7rem] rounded-2xl'" />
          </div>

          <!-- Dish list -->
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

          <!-- Empty state after allergen filter -->
          <div
            v-else-if="menu.dishes[cat.slug] && selectedAllergenFilter.length"
            class="flex flex-col items-center gap-2 rounded-2xl border border-slate-800/50 bg-slate-900/30 px-4 py-8 text-center"
          >
            <p class="text-sm font-medium text-slate-400">{{ t('menu.noMatchText') }}</p>
          </div>
        </section>
      </template>

      <!-- Error state -->
      <div v-if="menu.error" class="flex items-start gap-3 rounded-2xl border border-red-500/25 bg-red-500/8 px-4 py-3.5 shadow-sm shadow-black/20" role="alert">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-sm text-red-300">{{ menu.error }}</p>
        <button class="shrink-0 text-xs font-medium text-slate-400 underline hover:text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400" @click="menu.fetchCategories(true)">{{ t('common.retry') }}</button>
      </div>

      <!-- Recent orders -->
      <section v-if="cart.recentOrders?.length" class="ui-panel ui-reveal space-y-3 p-4" :aria-label="t('menu.recentOrdersTitle')">
        <p class="ui-kicker">{{ t('menu.recentOrdersTitle') }}</p>
        <ul class="space-y-2">
          <li v-for="order in cart.recentOrders.slice(0, 5)" :key="order.order_number">
            <div class="flex items-center gap-3 rounded-xl border border-slate-700/50 bg-slate-900/40 px-3.5 py-3">
              <!-- Order info — tapping navigates to status -->
              <RouterLink
                :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
                class="min-w-0 flex-1 space-y-0.5"
                :aria-label="`${t('menu.viewStatus')} ${order.order_number}`"
              >
                <p class="text-xs font-semibold tracking-wide text-slate-200 tabular-nums">{{ order.order_number }}</p>
                <p v-if="order.items?.length" class="truncate text-[11px] text-slate-400 leading-relaxed" :title="order.items.map(i => i.dish_name || i.name).join(', ')">
                  {{ order.items.slice(0, 3).map(i => i.dish_name || i.name).join(', ') }}{{ order.items.length > 3 ? '…' : '' }}
                </p>
              </RouterLink>
              <!-- Price + reorder -->
              <div class="shrink-0 flex items-center gap-2.5">
                <p class="text-sm font-bold tabular-nums" style="color:var(--color-secondary)">{{ formatPrice(order.total) }}</p>
                <button
                  v-if="!isBrowseOnly && order.items?.length"
                  type="button"
                  class="ui-press rounded-full border border-[var(--color-secondary)]/30 bg-[var(--color-secondary)]/8 px-2.5 py-1 text-[11px] font-semibold text-[var(--color-secondary)] transition hover:bg-[var(--color-secondary)]/15 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/40"
                  :aria-label="`${t('menu.reorder')} — ${order.order_number}`"
                  @click="reorderItems(order)"
                >
                  {{ t('menu.reorder') }}
                </button>
              </div>
            </div>
          </li>
        </ul>
      </section>

    </div>

    <!-- ── Sticky cart bar — full-width on mobile, floating pill bottom-right on desktop ── -->
    <Transition name="cart-bar">
      <RouterLink
        v-if="cart.count"
        :to="{ name: 'cart' }"
        class="ui-cart-bar fixed z-20 flex items-center justify-between gap-4 rounded-2xl px-4 py-3 backdrop-blur-xl bottom-[5.15rem] left-3 right-3 sm:left-auto sm:right-6 sm:rtl:left-6 sm:rtl:right-auto sm:bottom-6 sm:w-auto sm:min-w-[15rem] sm:shadow-2xl"
        :aria-label="t('common.cart')"
      >
        <div class="flex items-center gap-2.5">
          <span class="flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-slate-950 shadow-sm" style="background:var(--color-secondary)">{{ cart.count }}</span>
          <p class="text-sm font-semibold text-white">{{ t('common.cart') }}</p>
        </div>
        <div class="flex items-center gap-2">
          <p class="text-base font-bold tabular-nums" style="color:var(--color-secondary)">{{ formatPrice(cart.total) }}</p>
          <AppIcon name="cart" class="h-4 w-4" style="color:var(--color-secondary)" aria-hidden="true" />
        </div>
      </RouterLink>
    </Transition>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon   from '../components/AppIcon.vue'
import DishCard  from '../components/DishCard.vue'
import { useI18n } from '../composables/useI18n'
import { withImageFallback } from '../lib/images'
import { trackEvent } from '../lib/analytics'
import { getTodayClosingTime, getNextOpenInfo, isCurrentlyOpenBySchedule } from '../lib/businessHours'
import api from '../lib/api'
import { useCartStore }     from '../stores/cart'
import { useCustomerStore } from '../stores/customer'
import { useMenuStore }     from '../stores/menu'
import { useTenantStore }   from '../stores/tenant'
import { useToastStore }    from '../stores/toast'

const menu           = useMenuStore()
const tenant         = useTenantStore()
const cart           = useCartStore()
const toast          = useToastStore()
const customerStore  = useCustomerStore()
const route  = useRoute()
const { currentLocale, formatPrice, t } = useI18n()

// ── Route props (passed by /m/:menuSlug) ─────────────────────────────────────
const props = defineProps({
  menuSlug: { type: String, default: '' },
})

// ── Table QR context ─────────────────────────────────────────────────────────
const tableContextBanner = ref('')
// ── Call waiter (dine-in, table context only) ────────────────────────────────
const callingWaiter       = ref(false)
const waiterCooldown      = ref(0)   // seconds remaining; >0 means "just notified, please wait"
let   _waiterCooldownTimer = null

const callWaiter = async () => {
  const slug = cart.tableSlug
  if (!slug || callingWaiter.value || waiterCooldown.value > 0) return
  callingWaiter.value = true
  try {
    await api.post('/waiter-call/', { table: slug })
    toast.show(t('menu.waiterCalled'), 'success')
    // Start a 30-second cooldown so the user can see "Notified" and can't double-tap
    waiterCooldown.value = 30
    clearInterval(_waiterCooldownTimer)
    _waiterCooldownTimer = setInterval(() => {
      waiterCooldown.value = Math.max(0, waiterCooldown.value - 1)
      if (waiterCooldown.value <= 0) clearInterval(_waiterCooldownTimer)
    }, 1000)
  } catch (e) {
    const status = e?.response?.status
    toast.show(status === 429 ? t('menu.waiterCallThrottled') : t('menu.waiterCallFailed'), 'error')
  } finally {
    callingWaiter.value = false
  }
}

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
const catSheetOpen      = ref(false)
const catSheetEl        = ref(null)
const catSheetTriggerEl = ref(null)

watch(catSheetOpen, (open) => {
  if (open) nextTick(() => catSheetEl.value?.querySelector('button')?.focus())
})

// ── Tenant / profile data ────────────────────────────────────────────────────
const meta             = computed(() => tenant.resolvedMeta || null)
const profile          = computed(() => meta.value?.profile || null)
const menuTheme        = computed(() => profile.value?.menu_theme || 'dark')
const isBrowseOnly     = computed(() => tenant.isBrowseOnlyPlan === true)
const ratingSummary    = computed(() => meta.value?.rating_summary || null)
const recentReviews    = computed(() => meta.value?.recent_reviews  || [])

// ── Loyalty programme teaser ──────────────────────────────────────────────────
const loyaltyConfig  = ref(null)
const loyaltyPoints  = computed(() => Number(customerStore.customer?.loyalty_points) || 0)
const loyaltyAvailable = computed(() =>
  customerStore.isAuthenticated &&
  !!loyaltyConfig.value?.enabled &&
  loyaltyPoints.value >= (Number(loyaltyConfig.value?.redeem_threshold) || 0) &&
  (Number(loyaltyConfig.value?.points_value) || 0) > 0
)
const fetchLoyaltyConfig = async () => {
  try {
    const res = await api.get('/customer/loyalty/config/')
    loyaltyConfig.value = res.data?.enabled ? res.data : null
  } catch {
    loyaltyConfig.value = null
  }
}
const tenantName       = computed(() => meta.value?.name || t('customerLayout.fallbackTenantName'))
const tenantDescription = computed(() => String(profile.value?.description || profile.value?.tagline || '').trim() || t('customerLeadPage.fallbackDescription'))
const heroImage        = computed(() => String(profile.value?.hero_url || '').trim())
const logoImage        = computed(() => String(profile.value?.logo_url || '').trim())
const locationLine     = computed(() => String(profile.value?.address || meta.value?.name || '').trim())
const cartCurrency     = computed(() => cart.items.find(i => i.currency)?.currency || meta.value?.plan?.currency || 'MAD')

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

// ── Menu text search ──────────────────────────────────────────────────────────
const menuSearchQuery = ref('')
const isSearchActive  = computed(() => menuSearchQuery.value.trim().length > 0)

/** Search results grouped by category — applies allergen filter via sectionDishes */
const menuSearchResults = computed(() => {
  const q = menuSearchQuery.value.trim().toLowerCase()
  if (!q) return []
  const groups = []
  for (const cat of visibleCategories.value) {
    const dishes = sectionDishes(cat.slug)
    const matched = dishes.filter(d =>
      (d.name || '').toLowerCase().includes(q) ||
      (d.description || '').toLowerCase().includes(q)
    )
    if (matched.length) groups.push({ category: cat, dishes: matched })
  }
  return groups
})

const totalSearchCount = computed(() =>
  menuSearchResults.value.reduce((n, g) => n + g.dishes.length, 0)
)

/** Pre-load all visible categories when search activates for comprehensive results */
watch(isSearchActive, (active) => {
  if (!active) return
  for (const cat of visibleCategories.value) {
    if (!loadedSlugs.value.has(cat.slug)) {
      loadedSlugs.value.add(cat.slug)
      menu.fetchDishesByCategory(cat.slug)
    }
  }
})

// ── Reorder from recent orders ────────────────────────────────────────────────
/** Add all items from a previous order back to the cart (best-effort — server validates at checkout). */
const reorderItems = (order) => {
  if (!order?.items?.length) {
    toast.show(t('menu.reorderEmpty'), 'info')
    return
  }
  for (const item of order.items) {
    cart.add({
      slug:          item.slug,
      name:          item.dish_name || item.name,
      price:         item.price,
      currency:      item.currency,
      qty:           item.qty || 1,
      note:          item.note || '',
      option_ids:    item.option_ids || [],
      option_labels: item.option_labels || [],
    })
  }
  toast.show(t('menu.reorderAdded'), 'success')
}

// ── Sticky category nav ──────────────────────────────────────────────────────
// The customer layout renders a sticky header (.ui-header, top:0) whose height
// differs by breakpoint. The category nav must stick directly BELOW it (not at a
// hardcoded offset, where it hides behind the header) and the scroll-to math must
// clear it — so we measure the header height at runtime.
const headerOffset = ref(0)
const measureHeaderOffset = () => {
  const h = document.querySelector('.ui-header')
  headerOffset.value = h ? Math.round(h.getBoundingClientRect().height) : 0
}
const activeCategorySlug = ref('')
const pillRowEl          = ref(null)
const isOverflowing      = ref(false)
let _pillObserver        = null

const checkPillOverflow = () => {
  if (!pillRowEl.value) return
  isOverflowing.value = pillRowEl.value.scrollWidth > pillRowEl.value.clientWidth
}

watch(isOverflowing, (v) => { if (!v) catSheetOpen.value = false })
watch(visibleCategories, () => nextTick(checkPillOverflow))

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
  const navEl = document.querySelector('.ui-menu-category-nav')
  const OFFSET = headerOffset.value + (navEl ? navEl.offsetHeight : 0) + 12
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
  menuSearchQuery.value = ''        // clear search so sections are visible
  activeCategorySlug.value = slug  // optimistic update
  nextTick(() => {
    const el = document.getElementById(`section-${slug}`)
    if (!el) return
    const navEl = document.querySelector('.ui-menu-category-nav')
    const OFFSET = headerOffset.value + (navEl ? navEl.offsetHeight : 0) + 8
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
  // Default to 'dark' so first-time visitors always start in dark mode.
  // 'system' is only active if the user explicitly toggled to it.
  const userPref = localStorage.getItem('ui-color-scheme') || 'dark'
  if (userPref === 'dark') {
    document.documentElement.removeAttribute('data-menu-theme')
    return
  }
  // userPref === 'system' — follow OS; restaurantTheme drives which light palette to use
  const osDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  if (osDark) document.documentElement.removeAttribute('data-menu-theme')
  else document.documentElement.setAttribute('data-menu-theme', restaurantTheme || 'light')
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
  fetchLoyaltyConfig()  // non-blocking — teaser fades in when data arrives

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
  measureHeaderOffset()
  nextTick(measureHeaderOffset)  // re-measure after the layout settles
  window.addEventListener('resize', measureHeaderOffset, { passive: true })

  // ④ Pill-row overflow detector
  await nextTick()
  checkPillOverflow()
  _pillObserver = new ResizeObserver(checkPillOverflow)
  if (pillRowEl.value) _pillObserver.observe(pillRowEl.value)

  trackEvent('menu_view', { source: 'customer_menu_browse' })
})

onUnmounted(() => {
  loadObserver?.disconnect()
  _pillObserver?.disconnect()
  window.removeEventListener('scroll', updateActiveCategory)
  window.removeEventListener('resize', measureHeaderOffset)
  // NOTE: do NOT remove data-menu-theme here.
  // CustomerLayout's route watcher fires before this hook runs, so removing
  // the attribute here would undo the theme already re-applied by applyColorScheme().
  clearInterval(_waiterCooldownTimer)
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
