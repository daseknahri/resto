<template>
  <div v-if="dropdown" ref="rootRef" class="relative z-[3000]" @keydown="onKeydown">
    <button
      ref="triggerRef"
      type="button"
      class="ui-press ui-touch-target inline-flex items-center justify-center rounded-full border border-slate-700/80 bg-slate-950/70 font-semibold text-slate-100 transition hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
      :class="compact ? 'h-8 w-8 text-[11px]' : 'h-9 w-9 text-xs'"
      :aria-expanded="open ? 'true' : 'false'"
      aria-haspopup="listbox"
      :aria-label="t('common.language')"
      @click.stop="toggle"
    >
      <span class="text-sm leading-none" aria-hidden="true">{{ localeFlag(currentLocaleValue) }}</span>
      <span class="sr-only">{{ t("common.language") }}</span>
    </button>

    <Transition name="ui-fade">
      <div
        v-if="open"
        ref="menuRef"
        role="listbox"
        :aria-label="t('common.language')"
        class="absolute end-0 top-full z-[3100] mt-1.5 min-w-[5.25rem] overflow-hidden rounded-xl border border-slate-700/80 bg-slate-950/95 p-1 shadow-2xl shadow-black/50 backdrop-blur"
      >
        <button
          v-for="(option, idx) in localeOptions"
          :key="option.code"
          :ref="el => { if (el) optionRefs[idx] = el }"
          type="button"
          role="option"
          :aria-selected="currentLocaleValue === option.code"
          class="ui-press flex w-full items-center gap-1.5 whitespace-nowrap rounded-lg px-2 py-1.5 text-left text-[10px] text-slate-200 transition hover:bg-slate-800/80 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
          :class="currentLocaleValue === option.code ? 'bg-slate-800/70 font-semibold text-[var(--color-secondary)]' : ''"
          @click="selectLocale(option.code)"
        >
          <span class="text-sm leading-none" aria-hidden="true">{{ localeFlag(option.code) }}</span>
          <span class="truncate">{{ option.nativeLabel }}</span>
        </button>
      </div>
    </Transition>
  </div>

  <div
    v-else
    class="inline-flex items-center gap-1 rounded-full border border-slate-700/80 bg-slate-950/70"
    :class="compact ? 'p-0.5' : 'p-1'"
    :aria-label="t('common.language')"
    role="group"
  >
    <button
      v-for="option in localeOptions"
      :key="option.code"
      type="button"
      class="ui-press ui-touch-target rounded-full font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
      :class="[
        compact ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-[11px]',
        currentLocaleValue === option.code
          ? 'bg-[var(--color-secondary)] text-slate-950'
          : 'text-slate-300 hover:bg-slate-800 hover:text-slate-50',
      ]"
      :aria-pressed="currentLocaleValue === option.code"
      @click="setLocale(option.code)"
    >
      {{ option.nativeLabel }}
    </button>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
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
const triggerRef = ref(null);
const menuRef = ref(null);
const optionRefs = ref([]);

const localeFlag = (code) => {
  const map = {
    en: "🇬🇧",
    fr: "🇫🇷",
    ar: "🇲🇦",
  };
  return map[String(code || "").toLowerCase()] || "🌐";
};

const selectLocale = (code) => {
  setLocale(code);
  open.value = false;
  nextTick(() => triggerRef.value?.focus());
};

const toggle = () => {
  open.value = !open.value;
  if (open.value) {
    optionRefs.value = [];
    nextTick(() => {
      // Focus the currently selected option, or the first one
      const selectedIdx = localeOptions.findIndex(o => o.code === currentLocaleValue.value);
      const focusIdx = selectedIdx >= 0 ? selectedIdx : 0;
      optionRefs.value[focusIdx]?.focus();
    });
  }
};

const onKeydown = (e) => {
  if (!open.value) return;
  if (e.key === 'Escape') {
    e.preventDefault();
    open.value = false;
    nextTick(() => triggerRef.value?.focus());
  } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    const focused = document.activeElement;
    const opts = optionRefs.value.filter(Boolean);
    const idx = opts.indexOf(focused);
    const next = e.key === 'ArrowDown'
      ? Math.min(idx + 1, opts.length - 1)
      : Math.max(idx - 1, 0);
    opts[next]?.focus();
  }
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
