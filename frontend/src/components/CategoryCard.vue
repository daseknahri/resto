<template>
  <button
    class="group ui-surface-lift ui-press ui-reveal w-full overflow-hidden rounded-3xl border border-slate-700/60 bg-gradient-to-br from-slate-900/90 via-slate-950 to-slate-900/85 text-left shadow-lg shadow-black/40 transition-all duration-300 hover:-translate-y-0.5 hover:border-[var(--color-secondary)]/70 hover:shadow-xl hover:shadow-black/50"
    :style="{ '--ui-delay': `${Math.min(index || 0, 10) * 36}ms` }"
    @click="$emit('click')"
  >
    <div class="relative h-36 w-full overflow-hidden sm:h-44">
      <img :src="image" :alt="title" class="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" loading="lazy" />
      <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-black/0"></div>
      <span class="absolute right-3 top-3 rounded-full border border-white/25 bg-black/45 px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-slate-100">
        {{ itemCountLabel(count) }}
      </span>
      <div class="absolute bottom-3 left-3 right-3 flex items-center justify-between sm:bottom-4 sm:left-4 sm:right-4">
        <div>
          <p class="text-lg font-semibold text-white drop-shadow sm:text-xl">{{ title }}</p>
          <p class="text-xs text-slate-200">{{ t("categoryCard.openCategory") }}</p>
        </div>
        <span class="inline-flex h-8 w-8 items-center justify-center rounded-full bg-white/95 text-slate-900 font-semibold transition-transform group-hover:translate-x-0.5">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M5 12h14M13 5l7 7-7 7" />
          </svg>
          <span class="sr-only">{{ t("categoryCard.go") }}</span>
        </span>
      </div>
    </div>
  </button>
</template>

<script setup>
import { useI18n } from "../composables/useI18n";

defineEmits(["click"]);
const { itemCountLabel, t } = useI18n();

defineProps({
  title: { type: String, required: true },
  image: { type: String, required: true },
  count: { type: Number, default: 0 },
  index: { type: Number, default: 0 },
});
</script>
