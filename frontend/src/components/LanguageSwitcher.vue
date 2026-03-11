<template>
  <div class="inline-flex items-center gap-1 rounded-full border border-slate-700/80 bg-slate-950/70 p-1" :aria-label="t('common.language')">
    <button
      v-for="option in localeOptions"
      :key="option.code"
      type="button"
      class="rounded-full px-2.5 py-1 text-[11px] font-semibold transition-colors"
      :class="
        currentLocaleValue === option.code
          ? 'bg-[var(--color-secondary)] text-slate-950'
          : 'text-slate-300 hover:bg-slate-800 hover:text-slate-50'
      "
      @click="setLocale(option.code)"
    >
      {{ option.nativeLabel }}
    </button>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "../composables/useI18n";

const { currentLocale, localeOptions, setLocale, t } = useI18n();
const currentLocaleValue = computed(() => currentLocale.value);
</script>
