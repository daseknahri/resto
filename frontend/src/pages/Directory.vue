<template>
  <div class="min-h-screen">
    <div class="ui-page-shell space-y-6 pb-16">
      <!-- Header -->
      <header class="ui-hero-ribbon ui-reveal px-6 py-8 text-center md:px-10 md:py-10">
        <p class="ui-kicker mb-2">{{ t('directory.kicker') }}</p>
        <h1 class="ui-display mt-1 text-4xl font-semibold text-white sm:text-5xl">
          {{ t('directory.title') }}
        </h1>
        <p class="ui-subtle mx-auto mt-3 max-w-lg text-base">{{ t('directory.subtitle') }}</p>
      </header>

      <!-- Filters -->
      <div
        role="group"
        :aria-label="t('directory.filtersLabel')"
        class="ui-toolbar-band flex flex-wrap items-center gap-3"
      >
        <!-- Search -->
        <input
          v-model="searchQuery"
          type="search"
          :aria-label="t('directory.searchPlaceholder')"
          class="ui-input ui-touch-target min-w-0 flex-1 basis-52 rounded-full"
          :placeholder="t('directory.searchPlaceholder')"
          enterkeyhint="search"
        />
        <!-- City filter -->
        <select
          v-if="filters.cities.length"
          v-model="selectedCity"
          :aria-label="t('directory.filterCity')"
          class="ui-input ui-touch-target w-auto shrink-0 rounded-full"
        >
          <option value="">{{ t('directory.filterCity') }}: {{ t('directory.filterAll') }}</option>
          <option v-for="city in filters.cities" :key="city" :value="city">{{ city }}</option>
        </select>
        <!-- Cuisine filter -->
        <select
          v-if="filters.cuisines.length"
          v-model="selectedCuisine"
          :aria-label="t('directory.filterCuisine')"
          class="ui-input ui-touch-target w-auto shrink-0 rounded-full"
        >
          <option value="">{{ t('directory.filterCuisine') }}: {{ t('directory.filterAll') }}</option>
          <option v-for="cuisine in filters.cuisines" :key="cuisine" :value="cuisine">{{ cuisine }}</option>
        </select>
      </div>

      <!-- Loading: skeleton card grid -->
      <ul v-if="loading" :aria-label="t('directory.loading')" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-hidden="true">
        <li
          v-for="i in 6"
          :key="i"
          class="animate-pulse overflow-hidden rounded-[1.35rem] border border-slate-800/60 bg-slate-900/60"
        >
          <div class="h-44 rounded-t-[1.35rem] bg-slate-800/60" />
          <div class="space-y-3 p-4">
            <div class="h-3 w-full rounded bg-slate-800/50" />
            <div class="flex gap-2 pt-1">
              <div class="h-5 w-16 rounded-full bg-slate-800/60" />
              <div class="h-5 w-20 rounded-full bg-slate-800/50" />
            </div>
            <div class="h-9 w-full rounded-xl bg-slate-800/60 pt-1" />
          </div>
        </li>
      </ul>

      <!-- Error -->
      <div
        v-else-if="fetchError"
        role="alert"
        class="mx-auto max-w-sm"
      >
        <div class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-5 py-4">
          <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-5 w-5 shrink-0 text-red-400" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
          </svg>
          <p class="flex-1 text-sm text-red-300">{{ t('directory.fetchError') }}</p>
          <button
            class="ui-btn-outline ui-press shrink-0 border-red-500/40 px-3 py-1.5 text-xs text-red-300 hover:border-red-400/60 hover:text-red-200"
            @click="fetchDirectory"
          >{{ t('common.retry') }}</button>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="!filteredRestaurants.length" role="status" class="ui-empty-state ui-reveal mx-auto max-w-sm py-8 text-center">
        <svg aria-hidden="true" viewBox="0 0 24 24" class="mx-auto mb-4 h-10 w-10 text-slate-600" fill="none" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803 7.5 7.5 0 0016.803 16.803z" />
        </svg>
        <p class="text-base font-semibold text-slate-100">{{ t('directory.noResults') }}</p>
        <p class="mt-1.5 text-sm text-slate-400">{{ t('directory.noResultsHint') }}</p>
      </div>

      <!-- Restaurant grid -->
      <ul
        v-else
        class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
      >
        <li
          v-for="(r, index) in filteredRestaurants"
          :key="r.slug"
          class="group relative flex flex-col overflow-hidden rounded-[1.35rem] border border-slate-800/60 bg-slate-900/60 shadow-md shadow-black/30 transition-all duration-300 hover:border-slate-700/60 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-black/40 ui-reveal"
          :class="{ 'opacity-75': !r.is_open }"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <!-- Hero image — taller, with name+meta overlay matching Marketplace quality -->
          <div class="relative h-44 overflow-hidden rounded-t-[1.35rem]">
            <!-- Background -->
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
              <span v-else class="absolute inset-0 flex items-center justify-center text-5xl text-slate-700" aria-hidden="true">🍽️</span>
            </div>
            <!-- Bottom gradient: name + meta overlaid -->
            <div class="pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-slate-950 via-slate-950/65 to-transparent" />
            <div class="absolute inset-x-0 bottom-0 z-10 px-3.5 pb-3">
              <h2 class="text-sm font-bold leading-snug text-white drop-shadow-md">{{ r.name }}</h2>
              <div class="mt-0.5 flex items-center gap-2 text-[11px]">
                <span v-if="r.rating_average" class="flex items-center gap-0.5 text-amber-400" :aria-label="`${r.rating_average.toFixed(1)} ${t('directory.ratingLabel')}, ${r.rating_count} ${t('directory.reviewsLabel')}`">
                  <svg viewBox="0 0 12 12" class="h-2.5 w-2.5 fill-current" aria-hidden="true"><path d="M6 1l1.39 2.82 3.11.45-2.25 2.19.53 3.09L6 8.12 3.22 9.55l.53-3.09L1.5 4.27l3.11-.45z"/></svg>
                  <span class="tabular-nums">{{ r.rating_average.toFixed(1) }}</span>
                  <span class="text-slate-500 tabular-nums">({{ r.rating_count }})</span>
                </span>
                <span v-if="r.cuisine_type" class="text-slate-400">· {{ r.cuisine_type }}</span>
              </div>
            </div>

            <!-- Open/closed badge (top-start) -->
            <span
              class="absolute start-2 top-2 z-20 flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold tracking-wide backdrop-blur-md"
              :class="r.is_open
                ? 'border border-emerald-500/30 bg-emerald-950/90 text-emerald-300'
                : 'border border-slate-700/40 bg-slate-950/80 text-slate-500'"
            >
              <span
                v-if="r.is_open"
                aria-hidden="true"
                class="block h-1.5 w-1.5 rounded-full bg-emerald-400 motion-safe:animate-pulse"
              />
              {{ r.is_open ? t('directory.open') : t('directory.closed') }}
            </span>
          </div>

          <!-- Card body: tagline + capability chips + CTA -->
          <div class="flex flex-1 flex-col gap-2.5 p-4">
            <p v-if="r.tagline" class="line-clamp-2 text-xs leading-relaxed text-slate-400" :title="r.tagline">{{ r.tagline }}</p>

            <div class="mt-auto flex flex-wrap items-center gap-1.5 pt-1">
              <span v-if="r.city" class="ui-chip text-[11px]">{{ r.city }}</span>
              <span v-if="r.delivery_enabled" class="ui-chip text-[11px]">
                {{ t('directory.delivery') }}
              </span>
            </div>

            <!-- CTA -->
            <a
              :href="restaurantUrl(r.slug)"
              class="ui-btn-primary ui-press mt-1 w-full py-2.5 text-sm"
              :aria-label="`${t('directory.viewMenu')} — ${r.name}`"
            >
              {{ t('directory.viewMenu') }}
            </a>
          </div>
        </li>
      </ul>
    </div>
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
