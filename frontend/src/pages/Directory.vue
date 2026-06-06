<template>
  <div class="min-h-screen">
    <div class="ui-page-shell space-y-6 pb-16">
      <!-- Header -->
      <header class="ui-hero-ribbon ui-reveal px-4 py-4 text-center md:px-6 md:py-5">
        <p class="ui-kicker">{{ t('directory.kicker') }}</p>
        <h1 class="ui-display mt-1 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          {{ t('directory.title') }}
        </h1>
        <p class="ui-subtle mx-auto mt-1 max-w-md">{{ t('directory.subtitle') }}</p>
      </header>

      <!-- Filters -->
      <div class="flex flex-wrap gap-2">
        <!-- Search -->
        <input
          v-model="searchQuery"
          type="search"
          :aria-label="t('directory.searchPlaceholder')"
          class="ui-input ui-touch-target min-w-0 flex-1 basis-44 rounded-full"
          :placeholder="t('directory.searchPlaceholder')"
          enterkeyhint="search"
        />
        <!-- City filter -->
        <select
          v-if="filters.cities.length"
          v-model="selectedCity"
          :aria-label="t('directory.filterCity')"
          class="ui-input ui-touch-target w-auto rounded-full"
        >
          <option value="">{{ t('directory.filterCity') }}: {{ t('directory.filterAll') }}</option>
          <option v-for="city in filters.cities" :key="city" :value="city">{{ city }}</option>
        </select>
        <!-- Cuisine filter -->
        <select
          v-if="filters.cuisines.length"
          v-model="selectedCuisine"
          :aria-label="t('directory.filterCuisine')"
          class="ui-input ui-touch-target w-auto rounded-full"
        >
          <option value="">{{ t('directory.filterCuisine') }}: {{ t('directory.filterAll') }}</option>
          <option v-for="cuisine in filters.cuisines" :key="cuisine" :value="cuisine">{{ cuisine }}</option>
        </select>
      </div>

      <!-- Loading: skeleton card grid -->
      <ul v-if="loading" :aria-label="t('directory.loading')" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <li
          v-for="i in 6"
          :key="i"
          class="ui-skeleton animate-pulse overflow-hidden"
        >
          <div class="h-28 rounded-t-[1.35rem] bg-slate-800/60" />
          <div class="space-y-2 p-4">
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
      <div
        v-else-if="fetchError"
        role="alert"
        class="mx-auto max-w-sm"
      >
        <div class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
          <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
          </svg>
          <p class="flex-1 text-sm text-red-300">{{ t('directory.fetchError') }}</p>
          <button
            class="ui-btn-outline ui-press shrink-0 border-red-500/40 px-3 py-1 text-xs text-red-300 hover:border-red-400/60 hover:text-red-200"
            @click="fetchDirectory"
          >{{ t('common.retry') }}</button>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="!filteredRestaurants.length" class="ui-empty-state ui-reveal mx-auto max-w-sm text-center">
        <p class="text-sm font-semibold text-slate-100">{{ t('directory.noResults') }}</p>
        <p class="mt-1 text-xs text-slate-400">{{ t('directory.noResultsHint') }}</p>
      </div>

      <!-- Restaurant grid -->
      <ul
        v-else
        class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
      >
        <li
          v-for="(r, index) in filteredRestaurants"
          :key="r.slug"
          class="ui-panel ui-surface-lift ui-reveal group relative flex flex-col overflow-hidden"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <!-- Logo / hero strip -->
          <div class="flex h-28 items-center justify-center overflow-hidden rounded-t-[calc(1rem+2px)] bg-slate-800/60">
            <img
              v-if="r.logo_url"
              :src="r.logo_url"
              :alt="r.name"
              loading="lazy"
              decoding="async"
              class="h-full w-full object-cover opacity-80"
              @error="$event.target.style.display='none'"
            />
            <span v-else class="text-4xl opacity-20" aria-hidden="true">
              <svg viewBox="0 0 24 24" class="h-12 w-12 text-slate-500" fill="none" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 8.25v-1.5m0 1.5c-1.355 0-2.697.056-4.024.166C6.845 8.51 6 9.473 6 10.608v2.513m6-4.87c1.355 0 2.697.056 4.024.166C17.155 8.51 18 9.473 18 10.608v2.513m-3 4.493V19.5m-6-7.5h12m-12 0a1.5 1.5 0 01-1.5-1.5v-.75A2.25 2.25 0 014.75 8.5M18 15.5a1.5 1.5 0 001.5-1.5v-.75A2.25 2.25 0 0019.25 8.5" />
              </svg>
            </span>
          </div>

          <!-- Card body -->
          <div class="flex flex-1 flex-col gap-2 p-4">
            <div class="flex items-start justify-between gap-2">
              <h2 class="min-w-0 flex-1 truncate text-sm font-bold leading-snug text-slate-100">{{ r.name }}</h2>
              <span
                class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="r.is_open ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-700/50 text-slate-400'"
              >
                {{ r.is_open ? t('directory.open') : t('directory.closed') }}
              </span>
            </div>

            <p v-if="r.tagline" class="line-clamp-2 text-xs text-slate-400">{{ r.tagline }}</p>

            <div class="mt-auto flex flex-wrap items-center gap-1.5">
              <span v-if="r.cuisine_type" class="ui-chip text-[10px]">{{ r.cuisine_type }}</span>
              <span v-if="r.city" class="ui-chip text-[10px]">{{ r.city }}</span>
              <span v-if="r.delivery_enabled" class="inline-flex items-center gap-1 rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] text-sky-300">
                {{ t('directory.delivery') }}
              </span>
            </div>

            <!-- Rating -->
            <div v-if="r.rating_average" class="flex items-center gap-1 text-xs text-amber-400">
              <span aria-hidden="true">★</span>
              <span class="tabular-nums">{{ r.rating_average.toFixed(1) }}</span>
              <span class="tabular-nums text-slate-500">({{ r.rating_count }})</span>
            </div>

            <!-- CTA -->
            <a
              :href="restaurantUrl(r.slug)"
              class="ui-btn-primary ui-press mt-2 w-full py-2 text-xs"
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
