<template>
  <div class="min-h-screen pb-16">
    <div class="ui-page-shell max-w-4xl space-y-5">

      <!-- Header -->
      <header class="ui-hero-ribbon ui-reveal px-5 py-6 md:px-6 md:py-7">
        <div class="space-y-2 text-center">
          <p class="ui-kicker">{{ t('marketplace.kicker') }}</p>
          <h1 class="ui-display text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            {{ t('marketplace.title') }}
          </h1>
          <p class="ui-subtle mx-auto max-w-lg text-slate-300/80">{{ t('marketplace.subtitle') }}</p>
        </div>
      </header>

      <!-- ── Single pill strip: type tabs + "More services" pill ────────────── -->
      <div
        class="flex gap-1.5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        role="group"
        :aria-label="t('marketplace.filterType')"
      >
        <!-- Business-type filter pills (All · Restaurants · Shops) -->
        <button
          v-for="tab in BUSINESS_TYPE_TABS"
          :key="tab.key"
          type="button"
          :aria-pressed="selectedBusinessType === tab.key"
          class="ui-press flex shrink-0 items-center gap-1.5 rounded-full border px-4 py-2 text-xs font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
          :class="selectedBusinessType === tab.key
            ? 'border-[var(--color-secondary)]/70 bg-[var(--color-secondary)]/15 text-[var(--color-secondary)]'
            : 'border-slate-700/70 bg-slate-950/60 text-slate-400 hover:border-slate-600/80 hover:text-slate-300'"
          @click="setBusinessType(tab.key)"
        >
          <span aria-hidden="true" class="text-sm leading-none">{{ tab.icon }}</span>
          {{ tab.label }}
        </button>

        <!-- Divider -->
        <span class="mx-0.5 w-px shrink-0 self-stretch rounded-full bg-slate-700/50" aria-hidden="true" />

        <!-- More services pill — expands an inline sheet with route-based services -->
        <button
          type="button"
          :aria-expanded="moreServicesOpen"
          class="ui-press relative flex shrink-0 items-center gap-1.5 rounded-full border px-4 py-2 text-xs font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
          :class="moreServicesOpen
            ? 'border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
            : 'border-slate-700/70 bg-slate-950/60 text-slate-400 hover:border-slate-600/80 hover:text-slate-300'"
          @click="moreServicesOpen = !moreServicesOpen"
        >
          <span aria-hidden="true" class="text-sm leading-none">⋯</span>
          {{ t('marketplace.moreServices') }}
        </button>
      </div>

      <!-- More-services sheet — route-based services (ride, courier, etc.) -->
      <Transition name="ui-fade">
        <div
          v-if="moreServicesOpen"
          class="flex flex-wrap gap-2"
          role="group"
          :aria-label="t('marketplace.moreServices')"
        >
          <button
            v-for="svc in ROUTE_SERVICES"
            :key="svc.id"
            type="button"
            :aria-disabled="svc.status === 'coming_soon' ? 'true' : undefined"
            :disabled="svc.status === 'coming_soon'"
            class="ui-press flex items-center gap-2 rounded-2xl border px-4 py-2.5 text-xs font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
            :class="svc.status === 'coming_soon'
              ? 'cursor-default border-slate-700/40 bg-slate-950/40 text-slate-500 opacity-60'
              : HUB_ACCENT_CLASSES[svc.accent].idle"
            @click="svc.status === 'live' && onServiceClick(svc)"
          >
            <span aria-hidden="true" class="text-base leading-none">{{ svc.icon }}</span>
            <span>{{ t('services.' + svc.id + 'Title') }}</span>
            <span
              v-if="svc.status === 'coming_soon'"
              class="rounded-full border border-slate-600/50 bg-slate-800/60 px-1.5 py-px text-[9px] font-medium text-slate-500"
            >{{ t('services.comingSoon') }}</span>
          </button>
        </div>
      </Transition>

      <!-- Shop sub-type chips — visible only when 'shop' lens is active -->
      <div
        v-if="selectedBusinessType === 'shop'"
        class="flex gap-1.5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        role="group"
        :aria-label="t('marketplace.typeShop')"
      >
        <button
          v-for="sub in SHOP_SUBTYPES"
          :key="sub.key"
          type="button"
          :aria-pressed="selectedShopSubtype === sub.key"
          class="ui-press flex shrink-0 items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/40"
          :class="selectedShopSubtype === sub.key
            ? 'border-indigo-500/70 bg-indigo-500/15 text-indigo-300'
            : 'border-slate-700/70 bg-slate-950/60 text-slate-400 hover:border-slate-600/80 hover:text-slate-300'"
          @click="setShopSubtype(sub.key)"
        >{{ sub.label }}</button>
      </div>

      <!-- Filter bar -->
      <section :aria-label="t('marketplace.kicker')" class="ui-section-band space-y-3 px-4 py-3.5">
        <!-- Row 1: search + location -->
        <div class="flex gap-2">
          <input
            v-model="searchQuery"
            type="search"
            :aria-label="t('marketplace.searchPlaceholder')"
            class="ui-input flex-1 min-w-0 rounded-full px-4 py-2 text-sm placeholder-slate-500"
            :placeholder="t('marketplace.searchPlaceholder')"
            enterkeyhint="search"
          />
          <button
            class="ui-btn-outline ui-press ui-touch-target flex shrink-0 items-center gap-1.5 px-3.5 py-2 text-xs disabled:opacity-50"
            :aria-label="t('marketplace.locationBtn')"
            :disabled="locating"
            :aria-busy="locating"
            @click="requestLocation"
          >
            <svg v-if="locating" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            <span v-else aria-hidden="true">📍</span>
            <span class="hidden sm:inline">{{ locating ? t('common.loading') : t('marketplace.locationBtn') }}</span>
          </button>
        </div>

        <!-- Row 2: dropdown filters -->
        <div class="flex flex-wrap gap-2">
          <!-- City -->
          <select
            v-if="filters.cities.length"
            v-model="selectedCity"
            :aria-label="t('marketplace.filterCity')"
            class="ui-input ui-touch-target rounded-full"
          >
            <option value="">{{ t('marketplace.filterCity') }}: {{ t('marketplace.filterAll') }}</option>
            <option v-for="c in filters.cities" :key="c" :value="c">{{ c }}</option>
          </select>

          <!-- Cuisine -->
          <select
            v-if="filters.cuisines.length"
            v-model="selectedCuisine"
            :aria-label="t('marketplace.filterCuisine')"
            class="ui-input ui-touch-target rounded-full"
          >
            <option value="">{{ t('marketplace.filterCuisine') }}: {{ t('marketplace.filterAll') }}</option>
            <option v-for="c in filters.cuisines" :key="c" :value="c">{{ c }}</option>
          </select>

          <!-- Fulfillment -->
          <select
            v-model="selectedFulfillment"
            :aria-label="t('marketplace.filterFulfillment')"
            class="ui-input ui-touch-target rounded-full"
          >
            <option value="any">{{ t('marketplace.filterFulfillmentAny') }}</option>
            <option value="delivery">{{ t('marketplace.filterFulfillmentDelivery') }}</option>
            <option value="pickup">{{ t('marketplace.filterFulfillmentPickup') }}</option>
          </select>

          <!-- Price tier -->
          <select
            v-model="selectedPriceTier"
            :aria-label="t('marketplace.filterPriceTier')"
            class="ui-input ui-touch-target rounded-full"
          >
            <option value="">{{ t('marketplace.filterPriceTier') }}: {{ t('marketplace.filterAll') }}</option>
            <option value="1">{{ t('marketplace.priceTier1') }}</option>
            <option value="2">{{ t('marketplace.priceTier2') }}</option>
            <option value="3">{{ t('marketplace.priceTier3') }}</option>
          </select>

          <!-- Min rating -->
          <select
            v-model="selectedMinRating"
            :aria-label="t('marketplace.filterMinRating')"
            class="ui-input ui-touch-target rounded-full"
          >
            <option value="">{{ t('marketplace.filterMinRating') }}: {{ t('marketplace.filterAll') }}</option>
            <option value="3">{{ t('marketplace.minRating3') }}</option>
            <option value="3.5">{{ t('marketplace.minRating35') }}</option>
            <option value="4">{{ t('marketplace.minRating4') }}</option>
            <option value="4.5">{{ t('marketplace.minRating45') }}</option>
          </select>

          <!-- Open now toggle -->
          <button
            type="button"
            :aria-pressed="openOnly"
            class="ui-state-chip ui-press px-3 py-1.5 text-xs font-medium"
            :data-active="openOnly ? 'true' : 'false'"
            @click="openOnly = !openOnly"
          >
            <span aria-hidden="true">🟢</span>
            {{ t('marketplace.filterOpenNow') }}
          </button>

          <!-- Favourites toggle -->
          <button
            type="button"
            :aria-pressed="showFavouritesOnly"
            class="ui-state-chip ui-press px-3 py-1.5 text-xs font-medium"
            :data-active="showFavouritesOnly ? 'true' : 'false'"
            @click="showFavouritesOnly = !showFavouritesOnly"
          >
            <span aria-hidden="true">❤️</span>
            {{ t('marketplace.filterFavourites') }}
          </button>
        </div>

        <!-- Tag pills -->
        <div v-if="filters.tags.length" class="flex flex-wrap gap-1.5">
          <button
            v-for="tag in filters.tags"
            :key="tag"
            type="button"
            :aria-pressed="selectedTags.includes(tag)"
            class="ui-state-chip ui-press px-2.5 py-1 text-[11px] font-medium"
            :data-active="selectedTags.includes(tag) ? 'true' : 'false'"
            @click="toggleTag(tag)"
          >
            {{ tag }}
          </button>
        </div>

        <!-- Active filter count + clear -->
        <div v-if="activeFilterCount > 0" class="flex items-center gap-2">
          <span class="text-xs text-slate-500">{{ t('marketplace.filtersActive', { count: activeFilterCount }) }}</span>
          <button
            class="ui-press rounded-full border border-slate-700/70 px-2.5 py-0.5 text-[11px] text-slate-400 transition hover:border-slate-500 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
            :aria-label="t('marketplace.clearFilters')"
            @click="clearFilters"
          >
            ✕ {{ t('marketplace.clearFilters') }}
          </button>
        </div>

        <!-- Location denied notice -->
        <p v-if="locationDenied" class="text-xs text-amber-400/80" role="status">
          {{ t('marketplace.locationDenied') }}
        </p>
      </section>

      <!-- Active order tracking strip — appears for 2 h after a marketplace checkout -->
      <Transition name="ui-fade">
        <router-link
          v-if="activeOrder"
          :to="{ name: 'marketplace-order-status', params: { slug: activeOrder.slug, orderNumber: activeOrder.number } }"
          class="group flex items-center gap-3 rounded-xl border border-[var(--color-secondary)]/30 bg-[var(--color-secondary)]/8 px-4 py-3 transition hover:border-[var(--color-secondary)]/50 hover:bg-[var(--color-secondary)]/12 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
          :aria-label="t('marketplace.activeOrderLabel', { number: activeOrder.number })"
        >
          <!-- Pulsing live indicator -->
          <span class="relative flex h-2.5 w-2.5 shrink-0" aria-hidden="true">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--color-secondary)] opacity-60" />
            <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-[var(--color-secondary)]" />
          </span>
          <div class="min-w-0 flex-1">
            <p class="text-sm font-semibold text-white">{{ t('marketplace.activeOrderTitle', { number: activeOrder.number }) }}</p>
            <p class="mt-0.5 text-[11px] text-slate-400">{{ t('marketplace.activeOrderHint') }}</p>
          </div>
          <svg aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 rtl:rotate-180"><path d="M6 12l4-4-4-4"/></svg>
          <button
            type="button"
            class="ms-2 shrink-0 rounded-full p-1 text-slate-500 transition hover:text-slate-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-500"
            :aria-label="t('common.dismiss')"
            @click.prevent="activeOrderDismissed = true"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-3.5 w-3.5" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>
          </button>
        </router-link>
      </Transition>

      <!-- Book a ride promo tile -->
      <router-link
        to="/ride"
        class="group flex items-center justify-between gap-4 overflow-hidden rounded-2xl bg-gradient-to-r from-violet-900/70 via-indigo-900/70 to-slate-900/80 border border-violet-500/25 px-5 py-4 transition-all hover:border-violet-500/40 hover:from-violet-900/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50"
        :aria-label="t('marketplace.rideTileTitle')"
      >
        <div class="min-w-0">
          <p class="text-sm font-bold text-white leading-snug">{{ t('marketplace.rideTileTitle') }}</p>
          <p class="mt-0.5 text-[11px] text-slate-400 leading-relaxed">{{ t('marketplace.rideTileSubtitle') }}</p>
        </div>
        <span class="shrink-0 rounded-full bg-violet-500 px-4 py-1.5 text-xs font-bold text-white transition-opacity group-hover:opacity-90">
          {{ t('marketplace.rideTileCta') }}
        </span>
      </router-link>

      <!-- Deals & Promotions strip -->
      <section
        v-if="!loading && dealRestaurants.length"
        class="space-y-2"
        :aria-label="t('marketplace.dealsTitle')"
      >
        <div class="flex items-center gap-2 px-1">
          <p class="ui-kicker">{{ t('marketplace.dealsTitle') }}</p>
          <span class="ms-auto inline-flex items-center gap-0.5 rounded-full border border-amber-500/30 bg-amber-500/8 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-amber-400">
            <svg viewBox="0 0 12 12" fill="currentColor" class="h-2 w-2" aria-hidden="true"><path d="M6 .5 7.65 4.05l3.85.56L8.75 7.2l.65 3.8L6 9.38l-3.4 1.62.65-3.8L.5 4.61l3.85-.56z"/></svg>
            {{ dealRestaurants.length }}
          </span>
        </div>
        <div class="flex gap-2.5 overflow-x-auto pb-1 snap-x -mx-1 px-1">
          <router-link
            v-for="r in dealRestaurants"
            :key="'deal-' + r.slug"
            :to="{ name: 'marketplace-menu', params: { slug: r.slug } }"
            class="group relative flex shrink-0 snap-start flex-col overflow-hidden rounded-xl border border-amber-500/20 bg-slate-900/60 transition-colors hover:border-amber-500/40 hover:bg-amber-500/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40"
            style="width: 156px"
          >
            <div class="relative h-24 w-full overflow-hidden bg-slate-800">
              <img
                v-if="r.logo_url"
                :src="r.logo_url"
                :alt="r.name"
                loading="lazy"
                decoding="async"
                class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                @error="$event.target.style.display='none'"
              />
              <div v-else class="flex h-full w-full items-center justify-center bg-gradient-to-br from-amber-900/20 to-slate-900">
                <span aria-hidden="true" class="text-4xl opacity-40">{{ businessIcon(r) }}</span>
              </div>
              <div class="absolute inset-0 bg-gradient-to-t from-slate-950/70 via-transparent to-transparent" />
              <span class="absolute start-2 top-2 rounded-full bg-amber-400 px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wider text-black leading-none">
                {{ r.promo_badge || t('marketplace.dealBadge') }}
              </span>
            </div>
            <div class="px-2.5 py-2">
              <p class="truncate text-[12px] font-semibold leading-snug text-slate-200 group-hover:text-white">{{ r.name }}</p>
              <p class="mt-0.5 text-[10px]" :class="r.is_open ? 'text-emerald-400' : 'text-slate-500'">{{ r.is_open ? t('marketplace.open') : t('marketplace.closed') }}</p>
            </div>
          </router-link>
        </div>
      </section>

      <!-- Recently visited quick-access row -->
      <section
        v-if="!loading && recentRestaurants.length"
        class="space-y-2"
        :aria-label="t('marketplace.recentlyVisited')"
      >
        <p class="ui-kicker px-1">{{ t('marketplace.recentlyVisited') }}</p>
        <div class="flex gap-2.5 overflow-x-auto pb-1 snap-x -mx-1 px-1">
          <router-link
            v-for="r in recentRestaurants"
            :key="r.slug"
            :to="{ name: 'marketplace-menu', params: { slug: r.slug } }"
            class="group flex shrink-0 snap-start items-center gap-2.5 rounded-xl border border-slate-800/70 bg-slate-900/60 px-3 py-2.5 transition-colors hover:border-[var(--color-secondary)]/40 hover:bg-slate-900/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
          >
            <div class="h-10 w-10 shrink-0 overflow-hidden rounded-lg bg-slate-800 flex items-center justify-center">
              <img
                v-if="r.logo_url"
                :src="r.logo_url"
                :alt="r.name"
                loading="lazy"
                decoding="async"
                class="h-full w-full object-cover"
                @error="$event.target.style.display='none'"
              />
              <span v-else aria-hidden="true" class="text-xl">{{ businessIcon(r) }}</span>
            </div>
            <div class="min-w-0 max-w-[110px]">
              <p class="truncate text-[12px] font-semibold leading-tight text-slate-200 group-hover:text-white">{{ r.name }}</p>
              <p
                class="mt-0.5 text-[10px] leading-tight"
                :class="r.is_open ? 'text-emerald-400' : 'text-slate-500'"
              >{{ r.is_open ? t('marketplace.open') : t('marketplace.closed') }}</p>
            </div>
          </router-link>
        </div>
      </section>

      <!-- Results count + sort — sort always visible so user can pick before results arrive -->
      <div v-if="!fetchError && (displayedRestaurants.length || loading)" class="flex items-center justify-between gap-3 px-1">
        <p class="text-[11px] text-slate-500">{{ loading ? '' : t('marketplace.resultsCount', { n: displayedRestaurants.length }) }}</p>
        <select
          v-model="sortBy"
          :aria-label="t('marketplace.sortBy')"
          class="ui-input ui-touch-target rounded-full"
        >
          <option value="relevance">{{ t('marketplace.sortRelevance') }}</option>
          <option value="rating">{{ t('marketplace.sortRating') }}</option>
          <option value="name">{{ t('marketplace.sortNameAz') }}</option>
          <option v-if="userLat != null" value="nearest">{{ t('marketplace.sortNearest') }}</option>
          <option value="open">{{ t('marketplace.sortOpenFirst') }}</option>
        </select>
      </div>

      <!-- Loading: skeleton card grid -->
      <ul v-if="loading" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" :aria-label="t('marketplace.loading')">
        <li
          v-for="i in 6"
          :key="i"
          class="ui-skeleton animate-pulse overflow-hidden"
        >
          <div class="h-32 rounded-t-[1.35rem] bg-slate-800/60" />
          <div class="space-y-2.5 p-4">
            <div class="h-4 w-3/4 rounded bg-slate-700/60" />
            <div class="h-3 w-1/2 rounded bg-slate-800/50" />
            <div class="flex gap-2 pt-1">
              <div class="h-5 w-16 rounded-full bg-slate-800/60" />
              <div class="h-5 w-12 rounded-full bg-slate-800/50" />
              <div class="h-5 w-10 rounded-full bg-slate-800/40" />
            </div>
            <div class="mt-1 h-8 w-full rounded-full bg-slate-800/50" />
          </div>
        </li>
      </ul>

      <!-- Error -->
      <div v-else-if="fetchError" role="alert" class="mx-auto max-w-sm">
        <div class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
          <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
          </svg>
          <p class="flex-1 text-sm text-red-300">{{ t('marketplace.fetchError') }}</p>
          <button
            class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/50"
            :aria-label="t('marketplace.retryFetchAriaLabel')"
            @click="fetchRestaurants"
          >{{ t('common.retry') }}</button>
        </div>
      </div>

      <!-- Empty: favourites filter on but none saved -->
      <div
        v-else-if="showFavouritesOnly && !displayedRestaurants.length"
        class="ui-empty-state ui-reveal py-8 text-center space-y-2"
      >
        <p class="text-2xl" aria-hidden="true">❤️</p>
        <p class="text-sm font-semibold text-slate-100">{{ t('marketplace.noFavourites') }}</p>
        <p class="text-xs text-slate-400">{{ t('marketplace.noFavouritesHint') }}</p>
      </div>

      <!-- Empty -->
      <div
        v-else-if="!displayedRestaurants.length"
        class="ui-empty-state ui-reveal py-8 text-center space-y-2"
      >
        <p class="text-2xl" aria-hidden="true">🔍</p>
        <p class="text-sm font-semibold text-slate-100">{{ t('marketplace.noResults') }}</p>
        <p class="text-xs text-slate-400">{{ t('marketplace.noResultsHint') }}</p>
        <button
          class="ui-btn-outline mt-3 inline-flex items-center gap-1.5 px-5 py-2 text-sm"
          @click="clearFilters"
        >
          {{ t('marketplace.clearFilters') }}
        </button>
      </div>

      <!-- Grid + Load More -->
      <ul v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" :aria-label="t('marketplace.kicker')" aria-live="polite" aria-relevant="additions">
        <li
          v-for="(r, index) in displayedRestaurants"
          :key="r.slug"
          class="contents"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <!-- The entire card is the link — one focus ring, no separate CTA needed -->
          <router-link
            :to="{ name: 'marketplace-menu', params: { slug: r.slug } }"
            class="group relative flex flex-col overflow-hidden rounded-[1.35rem] border border-slate-800/60 bg-slate-900/60 shadow-md shadow-black/30 transition-all duration-300 hover:border-slate-700/60 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-black/40 ui-reveal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
            :class="{ 'opacity-70': !r.is_open }"
          >
            <!-- Hero image with gradient overlay — name + rating live here -->
            <div class="relative h-44 overflow-hidden rounded-t-[1.35rem]">
              <!-- Background: image or gradient placeholder -->
              <div class="absolute inset-0 bg-gradient-to-br from-slate-800 to-slate-900">
                <img
                  v-if="r.logo_url"
                  :src="r.logo_url"
                  :alt="r.name"
                  loading="lazy"
                  decoding="async"
                  class="h-full w-full object-cover opacity-80 transition-all duration-500 group-hover:scale-105 group-hover:opacity-90"
                  @error="$event.target.style.display='none'"
                />
                <span v-else class="absolute inset-0 flex items-center justify-center text-5xl text-slate-700" aria-hidden="true">{{ businessIcon(r) }}</span>
              </div>
              <!-- Bottom gradient: name + rating overlaid -->
              <div class="pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-slate-950 via-slate-950/70 to-transparent" />
              <div class="absolute inset-x-0 bottom-0 z-10 px-3.5 pb-3">
                <h2 class="text-sm font-bold leading-snug text-white drop-shadow-md" :title="r.name">{{ r.name }}</h2>
                <div class="mt-0.5 flex items-center gap-2 text-[11px]">
                  <span v-if="r.rating_average" class="flex items-center gap-0.5 text-amber-400">
                    <svg viewBox="0 0 12 12" class="h-2.5 w-2.5 fill-current" aria-hidden="true"><path d="M6 1l1.39 2.82 3.11.45-2.25 2.19.53 3.09L6 8.12 3.22 9.55l.53-3.09L1.5 4.27l3.11-.45z"/></svg>
                    <span class="tabular-nums">{{ r.rating_average.toFixed(1) }}</span>
                    <span class="text-slate-500 tabular-nums">({{ r.rating_count }})</span>
                  </span>
                  <span v-if="r.price_tier" class="text-slate-400">{{ '€'.repeat(r.price_tier) }}</span>
                  <span v-if="r.cuisine_type" class="text-slate-500">· {{ r.cuisine_type }}</span>
                </div>
              </div>

              <!-- Closed frosted overlay — appears over the hero image when the restaurant is closed -->
              <div
                v-if="!r.is_open"
                class="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-1.5 bg-slate-950/55 backdrop-blur-[2px]"
                aria-hidden="true"
              >
                <span class="rounded-full border border-slate-600/50 bg-slate-900/90 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-slate-300">
                  {{ t('marketplace.closed') }}
                </span>
                <span v-if="nextOpenLabel(r)" class="px-4 text-center text-[10px] leading-snug text-slate-400">{{ nextOpenLabel(r) }}</span>
              </div>

              <!-- Favourite toggle (top-right) — pointer-events kept so click doesn't navigate -->
              <button
                class="ui-press absolute end-2 top-2 z-20 flex h-8 w-8 items-center justify-center rounded-full backdrop-blur-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
                :class="isFavourite(r.slug) ? 'bg-red-500/25 text-red-400' : 'bg-slate-900/70 text-slate-500 hover:text-red-400'"
                :aria-label="isFavourite(r.slug) ? t('marketplace.unfavourite') : t('marketplace.favourite')"
                :aria-pressed="isFavourite(r.slug)"
                @click.prevent.stop="toggleFavourite(r.slug)"
              >
                <svg viewBox="0 0 20 20" class="h-4 w-4" :fill="isFavourite(r.slug) ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z"/>
                </svg>
              </button>

              <!-- Open/closed badge with live dot (top-left) -->
              <span
                class="absolute start-2 top-2 z-20 flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold tracking-wide backdrop-blur-md"
                :class="r.is_open
                  ? 'bg-emerald-950/90 text-emerald-300 border border-emerald-500/30'
                  : 'bg-slate-950/80 text-slate-500 border border-slate-700/40'"
              >
                <span
                  v-if="r.is_open"
                  class="block h-1.5 w-1.5 rounded-full bg-emerald-400 motion-safe:animate-pulse"
                  aria-hidden="true"
                />
                {{ r.is_open ? t('marketplace.open') : (nextOpenLabel(r) || t('marketplace.closed')) }}
              </span>

              <!-- Distance badge (sits above name overlay) -->
              <span
                v-if="r.distance_km != null"
                class="absolute bottom-14 end-2.5 z-20 rounded-full bg-slate-900/80 px-2 py-0.5 text-[10px] tabular-nums text-slate-300 backdrop-blur-sm"
              >
                📍 {{ t('marketplace.kmAway', { km: r.distance_km }) }}
              </span>
            </div>

            <!-- Card body: tagline + chips + delivery info + ETA chip -->
            <div class="flex flex-1 flex-col gap-2 p-4 pt-3">
              <!-- Tagline -->
              <p v-if="r.tagline" class="text-xs text-slate-400 line-clamp-1 leading-relaxed" :title="r.tagline">{{ r.tagline }}</p>

              <!-- Chips row -->
              <div class="flex flex-wrap items-center gap-1">
                <span v-if="isShopBusiness(r)" class="rounded-full border border-indigo-500/40 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-300">
                  {{ t('marketplace.badgeShop') }}
                </span>
                <span v-if="r.flash_sale_active" class="rounded-full border border-amber-500/30 bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300">
                  <span aria-hidden="true">⚡</span> {{ t('marketplace.flashSale') }}
                </span>
                <span v-if="r.promo_badge && !r.flash_sale_active" class="rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                  {{ t('marketplace.promo', { badge: r.promo_badge }) }}
                </span>
                <span
                  v-if="r.delivery_enabled"
                  class="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] text-sky-300"
                >
                  🚴 {{ t('marketplace.delivery') }}
                </span>
                <!-- ETA chip — the single most decision-relevant signal -->
                <span
                  v-if="r.prep_eta_min != null && r.prep_eta_max != null"
                  class="inline-flex items-center gap-1 rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] font-semibold text-sky-300"
                  :title="t('common.estimate')"
                >
                  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" class="h-2.5 w-2.5 shrink-0" aria-hidden="true"><circle cx="6" cy="6" r="4.5"/><path d="M6 3.5v2.75l1.5 1"/></svg>
                  {{ t('menu.etaReadyIn', { min: r.prep_eta_min, max: r.prep_eta_max }) }}
                </span>
                <span
                  v-for="tag in (r.tags || []).slice(0, 2)"
                  :key="tag"
                  class="rounded-full border border-violet-500/25 bg-violet-500/8 px-2 py-0.5 text-[10px] text-violet-300"
                >{{ tag }}</span>
              </div>

              <!-- Delivery fee info -->
              <div v-if="r.delivery_enabled" class="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                <span v-if="Number(r.delivery_fee) > 0" class="tabular-nums">
                  {{ t('marketplace.deliveryFee') }}: {{ fmtFee(r.delivery_fee) }}
                </span>
                <span v-else class="font-medium text-emerald-400/80">{{ t('marketplace.freeDelivery') }}</span>
                <span v-if="Number(r.delivery_minimum_order) > 0" class="tabular-nums">
                  · {{ t('marketplace.minOrder', { amount: fmtFee(r.delivery_minimum_order) }) }}
                </span>
              </div>
            </div>
          </router-link>
        </li>
      </ul>

      <!-- Load More -->
      <div v-if="!loading && !fetchError && hasMore" class="flex justify-center pt-2 pb-4">
        <button
          type="button"
          class="ui-btn-outline ui-press inline-flex items-center gap-2 rounded-full px-8 py-3 text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50 disabled:opacity-60"
          :disabled="loadingMore"
          :aria-busy="loadingMore"
          :aria-label="t('marketplace.loadMoreAriaLabel')"
          @click="loadMoreRestaurants"
        >
          <svg
            v-if="loadingMore"
            aria-hidden="true"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            class="h-4 w-4 animate-spin shrink-0"
          ><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ loadingMore ? t('marketplace.loadingMore') : t('marketplace.loadMore') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';
import { getNextOpenInfo } from '../lib/businessHours';
import { SERVICES } from '../lib/services';

const MKT_PAGE_SIZE = 20;

// ── Hub rail accent classes (full literal strings — never concat) ─────────────
const HUB_ACCENT_CLASSES = {
  amber:   { active: 'border-amber-500/70 bg-amber-500/15 text-amber-300',   idle: 'border-slate-700/70 bg-slate-950/60 text-slate-300 hover:border-amber-500/40 hover:text-amber-200'   },
  indigo:  { active: 'border-indigo-500/70 bg-indigo-500/15 text-indigo-300', idle: 'border-slate-700/70 bg-slate-950/60 text-slate-300 hover:border-indigo-500/40 hover:text-indigo-200' },
  emerald: { active: 'border-emerald-500/70 bg-emerald-500/15 text-emerald-300', idle: 'border-slate-700/70 bg-slate-950/60 text-slate-300 hover:border-emerald-500/40 hover:text-emerald-200' },
  rose:    { active: 'border-rose-500/70 bg-rose-500/15 text-rose-300',       idle: 'border-slate-700/70 bg-slate-950/60 text-slate-300 hover:border-rose-500/40 hover:text-rose-200'     },
  sky:     { active: 'border-sky-500/70 bg-sky-500/15 text-sky-300',         idle: 'border-slate-700/70 bg-slate-950/60 text-slate-300 hover:border-sky-500/40 hover:text-sky-200'       },
};

const FAVOURITES_KEY = 'marketplace:favourites';
const loadFavourites = () => {
  try { return new Set(JSON.parse(localStorage.getItem(FAVOURITES_KEY) || '[]')); } catch { return new Set(); }
};
const saveFavourites = (set) => {
  try { localStorage.setItem(FAVOURITES_KEY, JSON.stringify([...set])); } catch { /* storage unavailable */ }
};

// ── Recently visited ──────────────────────────────────────────────────────────
const RECENT_KEY = 'marketplace:recent';
const RECENT_TTL_MS = 30 * 24 * 60 * 60 * 1000; // prune entries older than 30 days
const loadRecentSlugs = () => {
  try {
    const raw = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
    const cutoff = Date.now() - RECENT_TTL_MS;
    // New format: [{slug, ts}]. Legacy plain strings have no ts — silently drop them.
    return raw
      .filter(e => e && typeof e === 'object' && e.slug && (e.ts || 0) >= cutoff)
      .map(e => e.slug);
  } catch { return []; }
};
const recentSlugs = ref(loadRecentSlugs());

// ── Active order tracking strip ───────────────────────────────────────────────
// Show a persistent "track your order" pill for the 2 hours following a checkout
const activeOrderDismissed = ref(false);
const activeOrder = computed(() => {
  if (activeOrderDismissed.value) return null;
  try {
    const num = localStorage.getItem('mktLastOrderNumber');
    const at = parseInt(localStorage.getItem('mktLastOrderAt') || '0', 10);
    const orderSlug = localStorage.getItem('mktLastOrderSlug');
    if (!num || !orderSlug || (Date.now() - at) > 7200000) return null; // 2 h window
    return { number: num, slug: orderSlug };
  } catch { return null; }
});

// Verify active order still exists and is non-terminal; clear localStorage if not.
const validateActiveOrder = async () => {
  const ord = activeOrder.value;
  if (!ord) return;
  const TERMINAL = new Set(['completed', 'cancelled']);
  try {
    const res = await api.get(`/marketplace/order/${ord.number}/`, { params: { restaurant: ord.slug } });
    if (TERMINAL.has(res.data?.status)) {
      try { localStorage.removeItem('mktLastOrderNumber'); localStorage.removeItem('mktLastOrderAt'); localStorage.removeItem('mktLastOrderSlug'); } catch { /* ignore */ }
      activeOrderDismissed.value = true;
    }
  } catch {
    // 404 / network error — treat as gone
    try { localStorage.removeItem('mktLastOrderNumber'); localStorage.removeItem('mktLastOrderAt'); localStorage.removeItem('mktLastOrderSlug'); } catch { /* ignore */ }
    activeOrderDismissed.value = true;
  }
};

const { t, currentLocale: locale } = useI18n();

// ── Business-type category tabs ───────────────────────────────────────────────
const BUSINESS_TYPE_TABS = computed(() => [
  { key: '',     icon: '🌐', label: t('marketplace.typeAll') },
  { key: 'food', icon: '🍽️', label: t('marketplace.typeFood') },
  { key: 'shop', icon: '🛍️', label: t('marketplace.typeShop') },
]);

// ── "More services" pill — route-based services (ride, courier, driver) ──────
// Lens-kind entries (food/shops/pharmacy) are covered by BUSINESS_TYPE_TABS; only
// route-kind entries go in the "More" expandable sheet.
const ROUTE_SERVICES = SERVICES.filter((svc) => svc.kind === 'route');
// Controls visibility of the "More services" inline sheet
const moreServicesOpen = ref(false);

// ── Shop sub-type chips ───────────────────────────────────────────────────────
const SHOP_SUBTYPES = computed(() => [
  { key: '',          label: t('marketplace.typeShop') },
  { key: 'grocery',   label: t('stepPublish.businessTypeGrocery') },
  { key: 'bakery',    label: t('stepPublish.businessTypeBakery') },
  { key: 'retail',    label: t('stepPublish.businessTypeRetail') },
  { key: 'pharmacy',  label: t('stepPublish.businessTypePharmacy') },
]);

// ── State ─────────────────────────────────────────────────────────────────────
const loading = ref(true);
const loadingMore = ref(false);
const fetchError = ref(false);
const restaurants = ref([]);
const filters = ref({ cities: [], cuisines: [], tags: [] });
// Pagination state (R9b)
const currentPage = ref(1);
const hasMore = ref(false);

// Filters
const searchQuery = ref('');
const selectedCity = ref('');
const selectedCuisine = ref('');
const selectedFulfillment = ref('any');
const selectedPriceTier = ref('');
const selectedMinRating = ref('');
// '' = all | 'food' (restaurant/cafe) | 'shop' (retail/grocery/bakery).
// Seeded from ?type= so the landing-page vertical cards deep-link to a lens.
const route = useRoute();
const router = useRouter();
const _initialType = ['food', 'shop'].includes(String(route.query.type || '')) ? String(route.query.type) : '';
const selectedBusinessType = ref(_initialType);

// ── Shop sub-type chips ───────────────────────────────────────────────────────
// '' = all shops | 'grocery' | 'bakery' | 'retail' | 'pharmacy'
// Seeded from ?sub= when ?type=shop so deep-links (e.g. ?type=shop&sub=pharmacy) work.
const _SHOP_SUBTYPE_KEYS = ['grocery', 'bakery', 'retail', 'pharmacy'];
const _initialSub = (_initialType === 'shop' && _SHOP_SUBTYPE_KEYS.includes(String(route.query.sub || '')))
  ? String(route.query.sub)
  : '';
const selectedShopSubtype = ref(_initialSub);

// Set business-type lens and mirror into ?type= query param (shareable URL).
// Also clears ?sub= — the caller is responsible for setting it afterwards if needed.
const setBusinessType = (key) => {
  selectedBusinessType.value = key;
  selectedShopSubtype.value = '';
  const q = { ...route.query };
  if (key) { q.type = key; } else { delete q.type; }
  delete q.sub;
  router.replace({ query: q });
};

// Mirror the selected shop sub-type chip into ?sub= query param.
const setShopSubtype = (key) => {
  selectedShopSubtype.value = key;
  const q = { ...route.query };
  if (key) { q.sub = key; } else { delete q.sub; }
  router.replace({ query: q });
};

// Handle a click on the hub rail service card.
// For lens entries with a subtype field: set type=shop + subtype in one go.
const onServiceClick = (svc) => {
  if (svc.kind === 'lens') {
    if (svc.subtype) {
      // Deep-link directly into the sub-lens (e.g. pharmacy → ?type=shop&sub=pharmacy)
      selectedBusinessType.value = svc.lens;
      selectedShopSubtype.value = svc.subtype;
      const q = { ...route.query, type: svc.lens, sub: svc.subtype };
      router.replace({ query: q });
    } else {
      setBusinessType(svc.lens);
    }
  } else if (svc.kind === 'route') {
    router.push({ name: svc.routeName });
  }
};

const openOnly = ref(false);
const selectedTags = ref([]);

// Formats a decimal fee value (string or number) as a localised number string.
// No currency symbol is shown here — the card listing doesn't know the restaurant's currency.
const fmtFee = (val) => {
  const n = parseFloat(val || 0);
  if (Number.isNaN(n)) return String(val);
  return n.toLocaleString(locale.value, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

// Buckets the fine-grained business_type into the two marketplace lenses.
const SHOP_BUSINESS_TYPES = ['retail', 'grocery', 'bakery', 'pharmacy'];
const isShopBusiness = (r) => SHOP_BUSINESS_TYPES.includes(r?.business_type || 'restaurant');

// Returns an emoji placeholder icon appropriate for the business type.
// Used when a restaurant/shop has no logo image set.
const businessIcon = (r) => {
  const t = r?.business_type || 'restaurant';
  if (t === 'cafe') return '☕';
  if (t === 'bakery') return '🥖';
  if (t === 'pharmacy') return '💊';
  if (t === 'retail' || t === 'grocery') return '🛍️';
  return '🍽️';
};

// Location
const locating = ref(false);
const locationDenied = ref(false);
const userLat = ref(null);
const userLng = ref(null);

// ── Active filter count ───────────────────────────────────────────────────────
// ── Favourites ────────────────────────────────────────────────────────────────
const favourites = ref(loadFavourites());
const showFavouritesOnly = ref(false);
const sortBy = ref('relevance'); // 'relevance' | 'rating' | 'name' | 'nearest' | 'open'
const isFavourite = (slug) => favourites.value.has(slug);
const toggleFavourite = (slug) => {
  const next = new Set(favourites.value);
  if (next.has(slug)) next.delete(slug);
  else next.add(slug);
  favourites.value = next;
  saveFavourites(next);
};

/**
 * For a closed restaurant with a schedule, return a formatted "Opens {day} {time}" string.
 * Returns null for open restaurants or those with no schedule data.
 */
const nextOpenLabel = (r) => {
  if (r.is_open) return null;
  const schedule = r.business_hours_schedule;
  if (!schedule || !Object.keys(schedule).length) return null;
  const info = getNextOpenInfo(schedule, locale.value);
  if (!info) return null;
  const dayPart = info.isTomorrow ? t('mktMenu.tomorrow') : (info.dayLabel || '');
  return t('mktMenu.opensAt', { day: dayPart, time: info.openTime });
};

// Recently visited restaurants — matched against loaded restaurant list so closed/removed ones vanish
const recentRestaurants = computed(() => {
  if (!recentSlugs.value.length || !restaurants.value.length) return [];
  const bySlug = Object.fromEntries(restaurants.value.map(r => [r.slug, r]));
  return recentSlugs.value.map(s => bySlug[s]).filter(Boolean).slice(0, 5);
});

// Restaurants with active deals / promotions — shown in a featured strip above the main grid
const dealRestaurants = computed(() => {
  if (!restaurants.value.length) return [];
  return restaurants.value.filter(r => r.flash_sale_active || r.promo_badge).slice(0, 8);
});

const activeFilterCount = computed(() => {
  let n = 0;
  if (searchQuery.value) n++;
  if (selectedCity.value) n++;
  if (selectedCuisine.value) n++;
  if (selectedFulfillment.value !== 'any') n++;
  if (selectedPriceTier.value) n++;
  if (selectedMinRating.value) n++;
  if (selectedBusinessType.value) n++;
  if (openOnly.value) n++;
  if (showFavouritesOnly.value) n++;
  n += selectedTags.value.length;
  return n;
});

const clearFilters = () => {
  searchQuery.value = '';
  selectedCity.value = '';
  selectedCuisine.value = '';
  selectedFulfillment.value = 'any';
  selectedPriceTier.value = '';
  selectedMinRating.value = '';
  selectedBusinessType.value = '';
  selectedShopSubtype.value = '';
  openOnly.value = false;
  selectedTags.value = [];
  showFavouritesOnly.value = false;
  const q = { ...route.query };
  delete q.type;
  delete q.sub;
  router.replace({ query: q });
};

// Favourites filter is client-side (data lives in localStorage).
// Business-type filtering is now server-side via _buildParams() → no client
// filter here, so the full paginated set is always visible.
// Sort is also client-side — applied after filtering.
const displayedRestaurants = computed(() => {
  let list = restaurants.value;
  if (showFavouritesOnly.value) {
    list = list.filter((r) => favourites.value.has(r.slug));
  }
  // Apply sort (spread to avoid mutating the reactive array)
  if (sortBy.value === 'rating') {
    list = [...list].sort((a, b) =>
      (b.rating_average || 0) !== (a.rating_average || 0)
        ? (b.rating_average || 0) - (a.rating_average || 0)
        : (b.rating_count || 0) - (a.rating_count || 0)
    );
  } else if (sortBy.value === 'name') {
    list = [...list].sort((a, b) => a.name.localeCompare(b.name));
  } else if (sortBy.value === 'nearest') {
    list = [...list].sort((a, b) => {
      if (a.distance_km == null && b.distance_km == null) return 0;
      if (a.distance_km == null) return 1;
      if (b.distance_km == null) return -1;
      return a.distance_km - b.distance_km;
    });
  } else if (sortBy.value === 'open') {
    list = [...list].sort((a, b) => Number(b.is_open) - Number(a.is_open));
  }
  return list;
});

const toggleTag = (tag) => {
  const idx = selectedTags.value.indexOf(tag);
  if (idx >= 0) selectedTags.value.splice(idx, 1);
  else selectedTags.value.push(tag);
};

// ── Location ──────────────────────────────────────────────────────────────────
const requestLocation = () => {
  if (!navigator.geolocation) return;
  locating.value = true;
  locationDenied.value = false;
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      userLat.value = pos.coords.latitude;
      userLng.value = pos.coords.longitude;
      locating.value = false;
      fetchRestaurants();
    },
    () => {
      locating.value = false;
      locationDenied.value = true;
    },
    { timeout: 8000 }
  );
};

// ── API fetch helpers ─────────────────────────────────────────────────────────
const _buildParams = () => {
  const params = { page_size: MKT_PAGE_SIZE };
  if (searchQuery.value) params.q = searchQuery.value;
  if (selectedCity.value) params.city = selectedCity.value;
  if (selectedCuisine.value) params.cuisine = selectedCuisine.value;
  if (selectedFulfillment.value !== 'any') params.fulfillment = selectedFulfillment.value;
  if (selectedPriceTier.value) params.price_tier = selectedPriceTier.value;
  if (selectedMinRating.value) params.min_rating = selectedMinRating.value;
  if (openOnly.value) params.open = '1';
  if (selectedTags.value.length) params.tags = selectedTags.value.join(',');
  if (userLat.value != null) { params.lat = userLat.value; params.lng = userLng.value; }
  // Server-side business_type filter — sent only when a lens is active so the
  // backend paginates the correct subset before returning results.
  if (selectedBusinessType.value === 'food') {
    params.business_type = 'restaurant,cafe';
  } else if (selectedBusinessType.value === 'shop') {
    params.business_type = selectedShopSubtype.value
      ? selectedShopSubtype.value
      : SHOP_BUSINESS_TYPES.join(',');
  }
  // selectedBusinessType === '' → omit param entirely (backend returns all types)
  return params;
};

// ── Initial / filter-change fetch (resets to page 1, replaces results) ────────
const fetchRestaurants = async () => {
  loading.value = true;
  fetchError.value = false;
  currentPage.value = 1;
  hasMore.value = false;
  try {
    const params = { ..._buildParams(), page: 1 };
    const res = await api.get('/marketplace/', { params });
    restaurants.value = res.data.restaurants || [];
    hasMore.value = Boolean(res.data.has_more);
    currentPage.value = res.data.page ?? 1;
    // Merge filter options preserving any already loaded (so dropdowns don't disappear)
    const incoming = res.data.filters || {};
    if (incoming.cities?.length) filters.value.cities = incoming.cities;
    if (incoming.cuisines?.length) filters.value.cuisines = incoming.cuisines;
    if (incoming.tags?.length) filters.value.tags = incoming.tags;
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

// ── Load More — fetches next page and appends results ─────────────────────────
const loadMoreRestaurants = async () => {
  if (loadingMore.value || !hasMore.value) return;
  loadingMore.value = true;
  const nextPage = currentPage.value + 1;
  try {
    const params = { ..._buildParams(), page: nextPage };
    const res = await api.get('/marketplace/', { params });
    const incoming = res.data.restaurants || [];
    restaurants.value = [...restaurants.value, ...incoming];
    hasMore.value = Boolean(res.data.has_more);
    currentPage.value = res.data.page ?? nextPage;
    // Merge filter options from new page too
    const incomingFilters = res.data.filters || {};
    if (incomingFilters.cities?.length) filters.value.cities = incomingFilters.cities;
    if (incomingFilters.cuisines?.length) filters.value.cuisines = incomingFilters.cuisines;
    if (incomingFilters.tags?.length) filters.value.tags = incomingFilters.tags;
  } catch {
    // Non-fatal: keep existing results, button remains visible so user can retry
  } finally {
    loadingMore.value = false;
  }
};

// Debounced refetch when filters change (including business-type lens + sub-type
// so the server re-fetches the correctly filtered + paginated set from page 1).
let _debounce = null;
watch(
  [searchQuery, selectedCity, selectedCuisine, selectedFulfillment,
   selectedPriceTier, selectedMinRating, openOnly, selectedTags,
   selectedBusinessType, selectedShopSubtype],
  () => {
    clearTimeout(_debounce);
    _debounce = setTimeout(fetchRestaurants, 350);
  }
);

// Keep selectedBusinessType / selectedShopSubtype in sync with browser
// back/forward navigation so the chip highlight and list stay consistent.
// Watches BOTH params: a history step can change only ?sub (subtype clicks
// write the URL), and a type-only watch would miss it.
watch(() => [route.query.type, route.query.sub], ([typeVal, subVal]) => {
  selectedBusinessType.value = ['food', 'shop'].includes(String(typeVal || '')) ? String(typeVal) : '';
  const sub = String(subVal || '');
  selectedShopSubtype.value = (selectedBusinessType.value === 'shop' && _SHOP_SUBTYPE_KEYS.includes(sub)) ? sub : '';
});

onMounted(() => { fetchRestaurants(); validateActiveOrder(); });
</script>
