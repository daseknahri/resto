<template>
  <div class="min-h-screen bg-slate-950 px-3 py-6 pb-16 sm:px-4 sm:py-10">

    <!-- Header -->
    <header class="mx-auto mb-8 max-w-4xl space-y-2 text-center">
      <p class="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-secondary,#f59e0b)]">
        {{ t('marketplace.kicker') }}
      </p>
      <h1 class="text-3xl font-bold tracking-tight text-white sm:text-4xl">
        {{ t('marketplace.title') }}
      </h1>
      <p class="text-sm text-slate-400">{{ t('marketplace.subtitle') }}</p>
    </header>

    <!-- Filter bar -->
    <div class="mx-auto mb-5 max-w-4xl space-y-2">
      <!-- Row 1: search + location -->
      <div class="flex gap-2">
        <input
          v-model="searchQuery"
          type="search"
          class="flex-1 min-w-0 rounded-full border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
          :placeholder="t('marketplace.searchPlaceholder')"
        />
        <button
          class="flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-300 hover:border-slate-500 disabled:opacity-50"
          :disabled="locating"
          @click="requestLocation"
        >
          <span>📍</span>
          <span class="hidden sm:inline">{{ locating ? '…' : t('marketplace.locationBtn') }}</span>
        </button>
      </div>

      <!-- Row 2: dropdown filters -->
      <div class="flex flex-wrap gap-2">
        <!-- City -->
        <select
          v-if="filters.cities.length"
          v-model="selectedCity"
          class="rounded-full border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 focus:outline-none"
        >
          <option value="">{{ t('marketplace.filterCity') }}: {{ t('marketplace.filterAll') }}</option>
          <option v-for="c in filters.cities" :key="c" :value="c">{{ c }}</option>
        </select>

        <!-- Cuisine -->
        <select
          v-if="filters.cuisines.length"
          v-model="selectedCuisine"
          class="rounded-full border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 focus:outline-none"
        >
          <option value="">{{ t('marketplace.filterCuisine') }}: {{ t('marketplace.filterAll') }}</option>
          <option v-for="c in filters.cuisines" :key="c" :value="c">{{ c }}</option>
        </select>

        <!-- Fulfillment -->
        <select
          v-model="selectedFulfillment"
          class="rounded-full border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 focus:outline-none"
        >
          <option value="any">{{ t('marketplace.filterFulfillmentAny') }}</option>
          <option value="delivery">{{ t('marketplace.filterFulfillmentDelivery') }}</option>
          <option value="pickup">{{ t('marketplace.filterFulfillmentPickup') }}</option>
        </select>

        <!-- Price tier -->
        <select
          v-model="selectedPriceTier"
          class="rounded-full border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 focus:outline-none"
        >
          <option value="">{{ t('marketplace.filterPriceTier') }}: {{ t('marketplace.filterAll') }}</option>
          <option value="1">€</option>
          <option value="2">€€</option>
          <option value="3">€€€</option>
        </select>

        <!-- Min rating -->
        <select
          v-model="selectedMinRating"
          class="rounded-full border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 focus:outline-none"
        >
          <option value="">{{ t('marketplace.filterMinRating') }}: {{ t('marketplace.filterAll') }}</option>
          <option value="3">★ 3+</option>
          <option value="3.5">★ 3.5+</option>
          <option value="4">★ 4+</option>
          <option value="4.5">★ 4.5+</option>
        </select>

        <!-- Open now toggle -->
        <button
          type="button"
          class="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors"
          :class="openOnly
            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
            : 'border-slate-700 text-slate-400 hover:border-slate-500'"
          @click="openOnly = !openOnly"
        >
          🟢 {{ t('marketplace.filterOpenNow') }}
        </button>
      </div>

      <!-- Tag pills -->
      <div v-if="filters.tags.length" class="flex flex-wrap gap-1.5">
        <button
          v-for="tag in filters.tags"
          :key="tag"
          type="button"
          class="rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors"
          :class="selectedTags.includes(tag)
            ? 'border-[var(--color-secondary,#f59e0b)]/60 bg-[var(--color-secondary,#f59e0b)]/10 text-[var(--color-secondary,#f59e0b)]'
            : 'border-slate-700 text-slate-400 hover:border-slate-500'"
          @click="toggleTag(tag)"
        >
          {{ tag }}
        </button>
      </div>

      <!-- Active filter count + clear -->
      <div v-if="activeFilterCount > 0" class="flex items-center gap-2">
        <span class="text-xs text-slate-500">{{ t('marketplace.filtersActive', { count: activeFilterCount }) }}</span>
        <button
          class="rounded-full border border-slate-700 px-2 py-0.5 text-[11px] text-slate-400 hover:text-slate-200"
          @click="clearFilters"
        >
          ✕ {{ t('marketplace.clearFilters') }}
        </button>
      </div>

      <!-- Location denied notice -->
      <p v-if="locationDenied" class="text-xs text-amber-400/80">{{ t('marketplace.locationDenied') }}</p>
    </div>

    <!-- Loading: skeleton card grid -->
    <ul v-if="loading" class="mx-auto grid max-w-4xl gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <li v-for="i in 6" :key="i" class="animate-pulse overflow-hidden rounded-2xl border border-slate-700/60 bg-slate-900/50">
        <div class="h-28 bg-slate-800/60" />
        <div class="p-4 space-y-2">
          <div class="h-4 w-3/4 rounded bg-slate-700/60" />
          <div class="h-3 w-1/2 rounded bg-slate-800/50" />
          <div class="flex gap-2 pt-1">
            <div class="h-5 w-16 rounded-full bg-slate-800/60" />
            <div class="h-5 w-12 rounded-full bg-slate-800/50" />
          </div>
        </div>
      </li>
    </ul>

    <!-- Error -->
    <div v-else-if="fetchError" class="mx-auto max-w-sm">
      <div class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
        <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
        </svg>
        <p class="flex-1 text-sm text-red-300">{{ t('marketplace.fetchError') }}</p>
        <button
          class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
          @click="fetchRestaurants"
        >{{ t('common.retry') }}</button>
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="!restaurants.length" class="py-16 text-center space-y-2">
      <p class="text-base font-semibold text-slate-300">{{ t('marketplace.noResults') }}</p>
      <p class="text-sm text-slate-500">{{ t('marketplace.noResultsHint') }}</p>
    </div>

    <!-- Grid -->
    <ul v-else class="mx-auto grid max-w-4xl gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <li
        v-for="r in restaurants"
        :key="r.slug"
        class="group relative flex flex-col overflow-hidden rounded-2xl border border-slate-700/60 bg-slate-900/50 transition-colors hover:border-slate-500"
      >
        <!-- Hero / logo strip -->
        <div class="relative flex h-28 items-center justify-center bg-slate-800/60 overflow-hidden">
          <img
            v-if="r.logo_url"
            :src="r.logo_url"
            :alt="r.name"
            class="h-full w-full object-cover opacity-80"
          />
          <span v-else class="text-3xl text-slate-600">🍽️</span>

          <!-- Open/closed badge -->
          <span
            class="absolute right-2 top-2 rounded-full px-2 py-0.5 text-[10px] font-semibold backdrop-blur-sm"
            :class="r.is_open
              ? 'bg-emerald-900/80 text-emerald-300'
              : 'bg-slate-800/80 text-slate-400'"
          >
            {{ r.is_open ? t('marketplace.open') : t('marketplace.closed') }}
          </span>

          <!-- Distance badge -->
          <span
            v-if="r.distance_km != null"
            class="absolute left-2 top-2 rounded-full bg-slate-900/80 px-2 py-0.5 text-[10px] text-slate-300 backdrop-blur-sm"
          >
            📍 {{ t('marketplace.kmAway', { km: r.distance_km }) }}
          </span>
        </div>

        <!-- Card body -->
        <div class="flex flex-1 flex-col gap-2 p-4">
          <!-- Name + price tier -->
          <div class="flex items-start justify-between gap-2">
            <h2 class="text-sm font-bold text-slate-100 leading-snug">{{ r.name }}</h2>
            <span class="shrink-0 text-[11px] text-slate-500 font-medium">{{ '€'.repeat(r.price_tier || 2) }}</span>
          </div>

          <!-- Tagline -->
          <p v-if="r.tagline" class="text-xs text-slate-400 line-clamp-2">{{ r.tagline }}</p>

          <!-- Chips row -->
          <div class="flex flex-wrap items-center gap-1 mt-auto">
            <span v-if="r.cuisine_type" class="rounded-full border border-slate-700 px-2 py-0.5 text-[10px] text-slate-400">
              {{ r.cuisine_type }}
            </span>
            <span v-if="r.city" class="rounded-full border border-slate-700 px-2 py-0.5 text-[10px] text-slate-400">
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
            <span v-if="Number(r.delivery_fee) > 0">
              {{ t('marketplace.deliveryFee') }}: {{ r.delivery_fee }}
            </span>
            <span v-else class="text-emerald-400/80">{{ t('marketplace.freeDelivery') }}</span>
            <span v-if="Number(r.delivery_minimum_order) > 0">
              · {{ t('marketplace.minOrder', { amount: r.delivery_minimum_order }) }}
            </span>
          </div>

          <!-- Flash sale badge -->
          <div v-if="r.flash_sale_active" class="flex items-center">
            <span class="rounded-full bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-[10px] font-semibold text-amber-300">
              ⚡ {{ t('marketplace.flashSale') }}
            </span>
          </div>

          <!-- Promo badge -->
          <div v-if="r.promo_badge && !r.flash_sale_active" class="flex items-center">
            <span class="rounded-full bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
              {{ t('marketplace.promo', { badge: r.promo_badge }) }}
            </span>
          </div>

          <!-- Rating -->
          <div v-if="r.rating_average" class="flex items-center gap-1 text-xs text-amber-400">
            <span>★ {{ r.rating_average.toFixed(1) }}</span>
            <span class="text-slate-500">({{ r.rating_count }})</span>
          </div>

          <!-- CTA -->
          <router-link
            :to="{ name: 'marketplace-menu', params: { slug: r.slug } }"
            class="mt-1 inline-flex items-center justify-center gap-1.5 rounded-full bg-[var(--color-secondary,#f59e0b)] px-4 py-2 text-xs font-semibold text-slate-950 transition-opacity hover:opacity-90"
          >
            {{ t('marketplace.viewMenu') }}
          </router-link>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';

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
const openOnly = ref(false);
const selectedTags = ref([]);

// Location
const locating = ref(false);
const locationDenied = ref(false);
const userLat = ref(null);
const userLng = ref(null);

// ── Active filter count ───────────────────────────────────────────────────────
const activeFilterCount = computed(() => {
  let n = 0;
  if (searchQuery.value) n++;
  if (selectedCity.value) n++;
  if (selectedCuisine.value) n++;
  if (selectedFulfillment.value !== 'any') n++;
  if (selectedPriceTier.value) n++;
  if (selectedMinRating.value) n++;
  if (openOnly.value) n++;
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
  openOnly.value = false;
  selectedTags.value = [];
};

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
