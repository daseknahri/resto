<template>
  <div v-if="dropdown" ref="rootRef" class="relative z-[1200]" :aria-label="t('common.language')">
    <button
      type="button"
      class="inline-flex items-center justify-center rounded-full border border-slate-700/80 bg-slate-950/70 font-semibold text-slate-100 transition hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)]"
      :class="compact ? 'h-8 w-8 text-[11px]' : 'h-9 w-9 text-xs'"
      :aria-expanded="open ? 'true' : 'false'"
      @click.stop="open = !open"
    >
      <span class="text-sm leading-none">{{ localeFlag(currentLocaleValue) }}</span>
      <span class="sr-only">{{ t("common.language") }}</span>
    </button>

    <div
      v-if="open"
      class="absolute right-0 top-full z-[1300] mt-1.5 min-w-[5.25rem] overflow-hidden rounded-xl border border-slate-700/80 bg-slate-950/95 p-1 shadow-2xl shadow-black/50 backdrop-blur"
    >
      <button
        v-for="option in localeOptions"
        :key="option.code"
        type="button"
        class="flex w-full items-center gap-1 whitespace-nowrap rounded-lg px-1.5 py-1 text-left text-[10px] text-slate-200 transition hover:bg-slate-800/80"
        :class="currentLocaleValue === option.code ? 'bg-slate-800/70 text-[var(--color-secondary)]' : ''"
        @click="selectLocale(option.code)"
      >
        <span class="text-sm leading-none">{{ localeFlag(option.code) }}</span>
        <span class="truncate">{{ option.nativeLabel }}</span>
      </button>
    </div>
  </div>

  <div
    v-else
    class="inline-flex items-center gap-1 rounded-full border border-slate-700/80 bg-slate-950/70"
    :class="compact ? 'p-0.5' : 'p-1'"
    :aria-label="t('common.language')"
  >
    <button
      v-for="option in localeOptions"
      :key="option.code"
      type="button"
      class="rounded-full font-semibold transition-colors"
      :class="[
        compact ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-[11px]',
        currentLocaleValue === option.code
          ? 'bg-[var(--color-secondary)] text-slate-950'
          : 'text-slate-300 hover:bg-slate-800 hover:text-slate-50',
      ]"
      @click="setLocale(option.code)"
    >
      {{ option.nativeLabel }}
    </button>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "../composables/useI18n";

const props = defineProps({
  compact: {
    type: Boolean,
    default: false,
  },
  dropdown: {
    type: Boolean,
    default: false,
  },
});

const { currentLocale, localeOptions, setLocale, t } = useI18n();
const currentLocaleValue = computed(() => currentLocale.value);
const open = ref(false);
const rootRef = ref(null);

const localeFlag = (code) => {
  const map = {
    en: "\uD83C\uDDEC\uD83C\uDDE7",
    fr: "\uD83C\uDDEB\uD83C\uDDF7",
    ar: "\uD83C\uDDF2\uD83C\uDDE6",
  };
  return map[String(code || "").toLowerCase()] || "\uD83C\uDF10";
};

const selectLocale = (code) => {
  setLocale(code);
  open.value = false;
};

const onDocClick = (event) => {
  if (!props.dropdown || !open.value) return;
  const root = rootRef.value;
  if (!root) return;
  if (!root.contains(event.target)) {
    open.value = false;
  }
};

onMounted(() => {
  document.addEventListener("click", onDocClick);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick);
});
</script>
