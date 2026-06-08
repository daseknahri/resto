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
      <ul v-if="loading" :aria-label="t('directory.loading')" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <li
          v-for="i in 6"
          :key="i"
          class="ui-skeleton animate-pulse overflow-hidden"
        >
          <div class="h-36 rounded-t-[1.35rem] bg-slate-800/60" />
          <div class="space-y-3 p-5">
            <div class="h-4 w-3/4 rounded bg-slate-700/60" />
            <div class="h-3 w-full rounded bg-slate-800/50" />
            <div class="h-3 w-2/3 rounded bg-slate-800/40" />
            <div class="flex gap-2 pt-1">
              <div class="h-5 w-16 rounded-full bg-slate-800/60" />
              <div class="h-5 w-14 rounded-full bg-slate-800/50" />
              <div class="h-5 w-12 rounded-full bg-slate-800/40" />
            </div>
            <div class="h-9 w-full rounded-full bg-slate-800/60 pt-1" />
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
          class="ui-panel ui-surface-lift ui-reveal group relative flex flex-col overflow-hidden"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <!-- Logo / hero strip -->
          <div class="relative flex h-36 items-center justify-center overflow-hidden rounded-t-[calc(1rem+2px)] bg-slate-800/60">
            <img
              v-if="r.logo_url"
              :src="r.logo_url"
              :alt="r.name"
              loading="lazy"
              decoding="async"
              class="h-full w-full object-cover opacity-90 transition-opacity duration-300 group-hover:opacity-100"
              @error="$event.target.style.display='none'"
            />
            <span v-else aria-hidden="true">
              <svg aria-hidden="true" viewBox="0 0 24 24" class="h-14 w-14 text-slate-600" fill="none" stroke="currentColor" stroke-width="1.2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 8.25v-1.5m0 1.5c-1.355 0-2.697.056-4.024.166C6.845 8.51 6 9.473 6 10.608v2.513m6-4.87c1.355 0 2.697.056 4.024.166C17.155 8.51 18 9.473 18 10.608v2.513m-3 4.493V19.5m-6-7.5h12m-12 0a1.5 1.5 0 01-1.5-1.5v-.75A2.25 2.25 0 014.75 8.5M18 15.5a1.5 1.5 0 001.5-1.5v-.75A2.25 2.25 0 0019.25 8.5" />
              </svg>
            </span>
            <!-- Open/closed badge overlaid on hero strip -->
            <span
              class="ui-status-pill absolute end-3 top-3 shrink-0 text-[11px]"
              :class="r.is_open ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300' : 'border-slate-600/40 bg-slate-900/70 text-slate-400'"
            >
              <span
                v-if="r.is_open"
                aria-hidden="true"
                class="ui-live-dot h-1.5 w-1.5 bg-emerald-400"
              />
              {{ r.is_open ? t('directory.open') : t('directory.closed') }}
            </span>
          </div>

          <!-- Card body -->
          <div class="flex flex-1 flex-col gap-2.5 p-5">
            <div>
              <h2 class="min-w-0 truncate text-base font-bold leading-snug tracking-tight text-slate-50">{{ r.name }}</h2>
              <p v-if="r.tagline" class="mt-0.5 line-clamp-2 text-xs leading-relaxed text-slate-400">{{ r.tagline }}</p>
            </div>

            <!-- Rating -->
            <div
              v-if="r.rating_average"
              class="flex items-center gap-1.5 text-xs"
              :aria-label="`${r.rating_average.toFixed(1)} ${t('directory.ratingLabel')}, ${r.rating_count} ${t('directory.reviewsLabel')}`"
            >
              <span aria-hidden="true" class="text-amber-400">★★★★★</span>
              <span aria-hidden="true" class="font-semibold tabular-nums text-amber-300">{{ r.rating_average.toFixed(1) }}</span>
              <span aria-hidden="true" class="tabular-nums text-slate-500">({{ r.rating_count }})</span>
            </div>

            <div class="mt-auto flex flex-wrap items-center gap-1.5 pt-1">
              <span v-if="r.cuisine_type" class="ui-chip text-[11px]">{{ r.cuisine_type }}</span>
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
