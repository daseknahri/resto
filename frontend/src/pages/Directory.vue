<template>
  <div class="min-h-screen bg-slate-950 px-3 py-6 pb-16 sm:px-4 sm:py-10">
    <!-- Header -->
    <header class="mx-auto mb-8 max-w-4xl space-y-2 text-center">
      <p class="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-secondary,#f59e0b)]">
        {{ t('directory.kicker') }}
      </p>
      <h1 class="text-3xl font-bold tracking-tight text-white sm:text-4xl">
        {{ t('directory.title') }}
      </h1>
      <p class="text-sm text-slate-400">{{ t('directory.subtitle') }}</p>
    </header>

    <!-- Filters -->
    <div class="mx-auto mb-6 max-w-4xl flex flex-wrap gap-2">
      <!-- Search -->
      <input
        v-model="searchQuery"
        type="search"
        :aria-label="t('directory.searchPlaceholder')"
        class="flex-1 min-w-44 rounded-full border border-slate-700 bg-slate-900 px-4 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
        :placeholder="t('directory.searchPlaceholder')"
      />
      <!-- City filter -->
      <select
        v-if="filters.cities.length"
        v-model="selectedCity"
        :aria-label="t('directory.filterCity')"
        class="rounded-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-300 focus:outline-none"
      >
        <option value="">{{ t('directory.filterCity') }}: {{ t('directory.filterAll') }}</option>
        <option v-for="city in filters.cities" :key="city" :value="city">{{ city }}</option>
      </select>
      <!-- Cuisine filter -->
      <select
        v-if="filters.cuisines.length"
        v-model="selectedCuisine"
        :aria-label="t('directory.filterCuisine')"
        class="rounded-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-300 focus:outline-none"
      >
        <option value="">{{ t('directory.filterCuisine') }}: {{ t('directory.filterAll') }}</option>
        <option v-for="cuisine in filters.cuisines" :key="cuisine" :value="cuisine">{{ cuisine }}</option>
      </select>
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
        <p class="flex-1 text-sm text-red-300">{{ t('directory.fetchError') }}</p>
        <button
          class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
          @click="fetchDirectory"
        >{{ t('common.retry') }}</button>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!filteredRestaurants.length" class="py-16 text-center space-y-2">
      <p class="text-base font-semibold text-slate-300">{{ t('directory.noResults') }}</p>
      <p class="text-sm text-slate-500">{{ t('directory.noResultsHint') }}</p>
    </div>

    <!-- Restaurant grid -->
    <ul
      v-else
      class="mx-auto grid max-w-4xl gap-3 sm:grid-cols-2 lg:grid-cols-3"
    >
      <li
        v-for="r in filteredRestaurants"
        :key="r.slug"
        class="group relative flex flex-col overflow-hidden rounded-2xl border border-slate-700/60 bg-slate-900/50 transition-colors hover:border-slate-600"
      >
        <!-- Logo / hero strip -->
        <div class="flex h-28 items-center justify-center bg-slate-800/60 overflow-hidden">
          <img
            v-if="r.logo_url"
            :src="r.logo_url"
            :alt="r.name"
            class="h-full w-full object-cover opacity-80"
          />
          <span v-else class="text-3xl text-slate-600">🍽️</span>
        </div>

        <!-- Card body -->
        <div class="flex flex-1 flex-col gap-2 p-4">
          <div class="flex items-start justify-between gap-2">
            <h2 class="text-sm font-bold text-slate-100 leading-snug">{{ r.name }}</h2>
            <span
              class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold"
              :class="r.is_open ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-700/50 text-slate-400'"
            >
              {{ r.is_open ? t('directory.open') : t('directory.closed') }}
            </span>
          </div>

          <p v-if="r.tagline" class="text-xs text-slate-400 line-clamp-2">{{ r.tagline }}</p>

          <div class="flex flex-wrap items-center gap-1.5 mt-auto">
            <span v-if="r.cuisine_type" class="rounded-full border border-slate-700 px-2 py-0.5 text-[10px] text-slate-400">
              {{ r.cuisine_type }}
            </span>
            <span v-if="r.city" class="rounded-full border border-slate-700 px-2 py-0.5 text-[10px] text-slate-400">
              📍 {{ r.city }}
            </span>
            <span v-if="r.delivery_enabled" class="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] text-sky-300">
              {{ t('directory.delivery') }}
            </span>
          </div>

          <!-- Rating -->
          <div v-if="r.rating_average" class="flex items-center gap-1 text-xs text-amber-400">
            <span>★ {{ r.rating_average.toFixed(1) }}</span>
            <span class="text-slate-500">({{ r.rating_count }})</span>
          </div>

          <!-- CTA -->
          <a
            :href="restaurantUrl(r.slug)"
            class="mt-2 inline-flex items-center justify-center gap-1.5 rounded-full bg-[var(--color-secondary,#f59e0b)] px-4 py-2 text-xs font-semibold text-slate-950 transition-opacity hover:opacity-90"
          >
            {{ t('directory.viewMenu') }}
          </a>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';

const { t } = useI18n();

const loading = ref(true);
const fetchError = ref(false);
const restaurants = ref([]);
const filters = ref({ cities: [], cuisines: [] });

const searchQuery = ref('');
const selectedCity = ref('');
const selectedCuisine = ref('');

const filteredRestaurants = computed(() => {
  let list = restaurants.value;
  const q = searchQuery.value.trim().toLowerCase();
  if (q) {
    list = list.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.cuisine_type.toLowerCase().includes(q) ||
        r.city.toLowerCase().includes(q) ||
        r.tagline.toLowerCase().includes(q)
    );
  }
  if (selectedCity.value) {
    list = list.filter((r) => r.city === selectedCity.value);
  }
  if (selectedCuisine.value) {
    list = list.filter((r) => r.cuisine_type === selectedCuisine.value);
  }
  return list;
});

const restaurantUrl = (slug) => {
  // Build tenant subdomain URL from the current host
  if (typeof window === 'undefined') return '#';
  const { protocol, host } = window.location;
  // Strip any existing subdomain to get the root domain
  const parts = host.split('.');
  const rootDomain = parts.length > 2 ? parts.slice(-2).join('.') : host;
  return `${protocol}//${slug}.${rootDomain}/browse`;
};

const fetchDirectory = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const res = await api.get('/directory/');
    restaurants.value = res.data.restaurants || [];
    filters.value = res.data.filters || { cities: [], cuisines: [] };
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(fetchDirectory);
</script>
