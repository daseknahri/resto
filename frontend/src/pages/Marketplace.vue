<template>
  <main class="min-h-screen pb-16">
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
            @click="requestLocation"
          >
            <span aria-hidden="true">📍</span>
            <span class="hidden sm:inline">{{ locating ? '…' : t('marketplace.locationBtn') }}</span>
          </button>
        </div>

        <!-- Row 2: dropdown filters -->
        <div class="flex flex-wrap gap-2">
          <!-- City -->
          <select
            v-if="filters.cities.length"
            v-model="selectedCity"
            :aria-label="t('marketplace.filterCity')"
            class="rounded-full border border-slate-700/70 bg-slate-950/75 px-3 py-1.5 text-xs text-slate-300 transition focus-visible:border-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/30"
          >
            <option value="">{{ t('marketplace.filterCity') }}: {{ t('marketplace.filterAll') }}</option>
            <option v-for="c in filters.cities" :key="c" :value="c">{{ c }}</option>
          </select>

          <!-- Cuisine -->
          <select
            v-if="filters.cuisines.length"
            v-model="selectedCuisine"
            :aria-label="t('marketplace.filterCuisine')"
            class="rounded-full border border-slate-700/70 bg-slate-950/75 px-3 py-1.5 text-xs text-slate-300 transition focus-visible:border-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/30"
          >
            <option value="">{{ t('marketplace.filterCuisine') }}: {{ t('marketplace.filterAll') }}</option>
            <option v-for="c in filters.cuisines" :key="c" :value="c">{{ c }}</option>
          </select>

          <!-- Fulfillment -->
          <select
            v-model="selectedFulfillment"
            :aria-label="t('marketplace.filterFulfillment')"
            class="rounded-full border border-slate-700/70 bg-slate-950/75 px-3 py-1.5 text-xs text-slate-300 transition focus-visible:border-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/30"
          >
            <option value="any">{{ t('marketplace.filterFulfillmentAny') }}</option>
            <option value="delivery">{{ t('marketplace.filterFulfillmentDelivery') }}</option>
            <option value="pickup">{{ t('marketplace.filterFulfillmentPickup') }}</option>
          </select>

          <!-- Price tier -->
          <select
            v-model="selectedPriceTier"
            :aria-label="t('marketplace.filterPriceTier')"
            class="rounded-full border border-slate-700/70 bg-slate-950/75 px-3 py-1.5 text-xs text-slate-300 transition focus-visible:border-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/30"
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
            class="rounded-full border border-slate-700/70 bg-slate-950/75 px-3 py-1.5 text-xs text-slate-300 transition focus-visible:border-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/30"
          >
            <option value="">{{ t('marketplace.filterMinRating') }}: {{ t('marketplace.filterAll') }}</option>
            <option value="3">{{ t('marketplace.minRating3') }}</option>
            <option value="3.5">{{ t('marketplace.minRating35') }}</option>
            <option value="4">{{ t('marketplace.minRating4') }}</option>
            <option value="4.5">{{ t('marketplace.minRating45') }}</option>
          </select>

          <!-- Business type (restaurants vs shops) -->
          <select
            v-model="selectedBusinessType"
            :aria-label="t('marketplace.filterType')"
            class="rounded-full border border-slate-700/70 bg-slate-950/75 px-3 py-1.5 text-xs text-slate-300 transition focus-visible:border-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
          >
            <option value="">{{ t('marketplace.typeAll') }}</option>
            <option value="food">{{ t('marketplace.typeFood') }}</option>
            <option value="shop">{{ t('marketplace.typeShop') }}</option>
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

      <!-- Grid -->
      <ul v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <li
          v-for="(r, index) in displayedRestaurants"
          :key="r.slug"
          class="ui-panel ui-surface-lift ui-reveal group relative flex flex-col overflow-hidden"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <!-- Hero / logo strip -->
          <div class="relative flex h-32 items-center justify-center overflow-hidden rounded-t-[1.35rem] bg-slate-800/60">
            <img
              v-if="r.logo_url"
              :src="r.logo_url"
              :alt="r.name"
              loading="lazy"
              decoding="async"
              class="h-full w-full object-cover opacity-85 transition-opacity duration-300 group-hover:opacity-95"
              @error="$event.target.style.display='none'"
            />
            <span v-else class="text-4xl text-slate-600" aria-hidden="true">🍽️</span>

            <!-- Favourite toggle -->
            <button
              class="ui-press absolute end-2 top-2 flex h-8 w-8 items-center justify-center rounded-full backdrop-blur-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
              :class="isFavourite(r.slug) ? 'bg-red-500/20 text-red-400' : 'bg-slate-900/60 text-slate-500 hover:text-red-400'"
              :aria-label="isFavourite(r.slug) ? t('marketplace.unfavourite') : t('marketplace.favourite')"
              :aria-pressed="isFavourite(r.slug)"
              @click.prevent="toggleFavourite(r.slug)"
            >
              <svg viewBox="0 0 20 20" class="h-4 w-4" :fill="isFavourite(r.slug) ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.75" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z"/>
              </svg>
            </button>

            <!-- Open/closed badge -->
            <span
              class="absolute bottom-2 end-2 rounded-full px-2.5 py-0.5 text-[10px] font-semibold tracking-wide backdrop-blur-sm"
              :class="r.is_open
                ? 'bg-emerald-900/80 text-emerald-300'
                : 'bg-slate-800/80 text-slate-400'"
            >
              {{ r.is_open ? t('marketplace.open') : t('marketplace.closed') }}
            </span>

            <!-- Distance badge -->
            <span
              v-if="r.distance_km != null"
              class="absolute start-2 top-2 rounded-full bg-slate-900/80 px-2.5 py-0.5 text-[10px] tabular-nums text-slate-300 backdrop-blur-sm"
            >
              <span aria-hidden="true">📍</span> {{ t('marketplace.kmAway', { km: r.distance_km }) }}
            </span>
          </div>

          <!-- Card body -->
          <div class="flex flex-1 flex-col gap-2 p-4">
            <!-- Name + price tier + rating on same visual band -->
            <div class="flex items-start justify-between gap-2 min-w-0">
              <div class="min-w-0 flex-1">
                <h2 class="truncate text-sm font-bold leading-snug text-slate-100">{{ r.name }}</h2>
                <div v-if="r.rating_average" class="mt-0.5 flex items-center gap-1 text-[11px] text-amber-400">
                  <span class="tabular-nums">★ {{ r.rating_average.toFixed(1) }}</span>
                  <span class="tabular-nums text-slate-500">({{ r.rating_count }})</span>
                </div>
              </div>
              <span class="shrink-0 text-[11px] font-medium text-slate-500 pt-0.5">{{ '€'.repeat(r.price_tier || 2) }}</span>
            </div>

            <!-- Tagline -->
            <p v-if="r.tagline" class="text-xs text-slate-400 line-clamp-2 leading-relaxed">{{ r.tagline }}</p>

            <!-- Chips row -->
            <div class="mt-auto flex flex-wrap items-center gap-1 pt-1">
              <span v-if="isShopBusiness(r)" class="rounded-full border border-indigo-500/40 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-300">
                {{ t('marketplace.badgeShop') }}
              </span>
              <span v-if="r.flash_sale_active" class="rounded-full border border-amber-500/30 bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300">
                <span aria-hidden="true">⚡</span> {{ t('marketplace.flashSale') }}
              </span>
              <span v-if="r.promo_badge && !r.flash_sale_active" class="rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                {{ t('marketplace.promo', { badge: r.promo_badge }) }}
              </span>
              <span v-if="r.cuisine_type" class="rounded-full border border-slate-700/70 px-2 py-0.5 text-[10px] text-slate-400">
                {{ r.cuisine_type }}
              </span>
              <span v-if="r.city" class="rounded-full border border-slate-700/70 px-2 py-0.5 text-[10px] text-slate-400">
                {{ r.city }}
              </span>
              <span
                v-if="r.delivery_enabled"
                class="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] text-sky-300"
              >
                {{ t('marketplace.delivery') }}
              </span>
              <span
                v-for="tag in (r.tags || []).slice(0, 2)"
                :key="tag"
                class="rounded-full border border-violet-500/25 bg-violet-500/8 px-2 py-0.5 text-[10px] text-violet-300"
              >
                {{ tag }}
              </span>
            </div>

            <!-- Delivery info row -->
            <div v-if="r.delivery_enabled" class="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
              <span v-if="Number(r.delivery_fee) > 0" class="tabular-nums">
                {{ t('marketplace.deliveryFee') }}: {{ r.delivery_fee }}
              </span>
              <span v-else class="text-emerald-400/80">{{ t('marketplace.freeDelivery') }}</span>
              <span v-if="Number(r.delivery_minimum_order) > 0" class="tabular-nums">
                · {{ t('marketplace.minOrder', { amount: r.delivery_minimum_order }) }}
              </span>
            </div>

            <!-- CTA -->
            <router-link
              :to="{ name: 'marketplace-menu', params: { slug: r.slug } }"
              class="ui-btn-primary mt-2 w-full text-xs"
            >
              {{ t('marketplace.viewMenu') }}
            </router-link>
          </div>
        </li>
      </ul>
    </div>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';

const FAVOURITES_KEY = 'marketplace:favourites';
const loadFavourites = () => {
  try { return new Set(JSON.parse(localStorage.getItem(FAVOURITES_KEY) || '[]')); } catch { return new Set(); }
};
const saveFavourites = (set) => {
  try { localStorage.setItem(FAVOURITES_KEY, JSON.stringify([...set])); } catch { /* storage unavailable */ }
};

const { t } = useI18n();

// ── State ─────────────────────────────────────────────────────────────────────
const loading = ref(true);
const fetchError = ref(false);
const restaurants = ref([]);
const filters = ref({ cities: [], cuisines: [], tags: [] });

// Filters
const searchQuery = ref('');
const selectedCity = ref('');
const selectedCuisine = ref('');
const selectedFulfillment = ref('any');
const selectedPriceTier = ref('');
const selectedMinRating = ref('');
const selectedBusinessType = ref(''); // '' = all | 'food' (restaurant/cafe) | 'shop' (retail/grocery/bakery)
const openOnly = ref(false);
const selectedTags = ref([]);

// Buckets the fine-grained business_type into the two marketplace lenses.
const SHOP_BUSINESS_TYPES = ['retail', 'grocery', 'bakery'];
const isShopBusiness = (r) => SHOP_BUSINESS_TYPES.includes(r?.business_type || 'restaurant');

// Location
const locating = ref(false);
const locationDenied = ref(false);
const userLat = ref(null);
const userLng = ref(null);

// ── Active filter count ───────────────────────────────────────────────────────
// ── Favourites ────────────────────────────────────────────────────────────────
const favourites = ref(loadFavourites());
const showFavouritesOnly = ref(false);
const isFavourite = (slug) => favourites.value.has(slug);
const toggleFavourite = (slug) => {
  const next = new Set(favourites.value);
  if (next.has(slug)) next.delete(slug);
  else next.add(slug);
  favourites.value = next;
  saveFavourites(next);
};

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
  openOnly.value = false;
  selectedTags.value = [];
  showFavouritesOnly.value = false;
};

// Favourites + business-type filtering are client-side (favourites live in
// localStorage; business_type is already in each result, so no refetch needed).
const displayedRestaurants = computed(() => {
  let list = restaurants.value;
  if (showFavouritesOnly.value) {
    list = list.filter((r) => favourites.value.has(r.slug));
  }
  if (selectedBusinessType.value === 'shop') {
    list = list.filter((r) => isShopBusiness(r));
  } else if (selectedBusinessType.value === 'food') {
    list = list.filter((r) => !isShopBusiness(r));
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

// ── API fetch ─────────────────────────────────────────────────────────────────
const fetchRestaurants = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const params = {};
    if (searchQuery.value) params.q = searchQuery.value;
    if (selectedCity.value) params.city = selectedCity.value;
    if (selectedCuisine.value) params.cuisine = selectedCuisine.value;
    if (selectedFulfillment.value !== 'any') params.fulfillment = selectedFulfillment.value;
    if (selectedPriceTier.value) params.price_tier = selectedPriceTier.value;
    if (selectedMinRating.value) params.min_rating = selectedMinRating.value;
    if (openOnly.value) params.open = '1';
    if (selectedTags.value.length) params.tags = selectedTags.value.join(',');
    if (userLat.value != null) { params.lat = userLat.value; params.lng = userLng.value; }

    const res = await api.get('/marketplace/', { params });
    restaurants.value = res.data.restaurants || [];
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

// Debounced refetch when filters change
let _debounce = null;
watch(
  [searchQuery, selectedCity, selectedCuisine, selectedFulfillment,
   selectedPriceTier, selectedMinRating, openOnly, selectedTags],
  () => {
    clearTimeout(_debounce);
    _debounce = setTimeout(fetchRestaurants, 350);
  }
);

onMounted(fetchRestaurants);
</script>
