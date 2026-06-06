<template>
  <div ref="rootRef" class="relative z-[3000]" :aria-label="t('common.currency')" @keydown="onKeydown">
    <button
      ref="triggerRef"
      type="button"
      class="ui-press inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-700/80 bg-slate-950/70 font-semibold text-slate-100 transition hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
      :aria-expanded="open ? 'true' : 'false'"
      aria-haspopup="listbox"
      @click.stop="toggle"
    >
      <span class="text-[10px] leading-none font-bold" aria-hidden="true">{{ currency.selected }}</span>
      <span class="sr-only">{{ t("common.currency") }}</span>
    </button>

    <div
      v-if="open"
      ref="menuRef"
      role="listbox"
      :aria-label="t('common.currency')"
      class="ui-reveal absolute end-0 top-full z-[3100] mt-1.5 min-w-[7.5rem] overflow-hidden rounded-xl border border-slate-700/80 bg-slate-950/95 p-1 shadow-2xl shadow-black/50 backdrop-blur"
    >
      <button
        v-for="(rate, idx) in currency.available"
        :key="rate.code"
        :ref="el => { if (el) optionRefs[idx] = el }"
        type="button"
        role="option"
        :aria-selected="currency.selected === rate.code"
        class="flex w-full items-center gap-2 whitespace-nowrap rounded-lg px-2.5 py-2 text-start text-[11px] text-slate-200 transition hover:bg-slate-800/80 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/50"
        :class="currency.selected === rate.code ? 'bg-slate-800/70 text-[var(--color-secondary)]' : ''"
        @click="select(rate.code)"
      >
        <span class="w-7 shrink-0 font-bold tabular-nums">{{ rate.code }}</span>
        <span class="flex-1 truncate text-[10px] text-slate-400">{{ rate.symbol }}</span>
        <span v-if="currency.selected === rate.code" class="ms-auto h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-secondary)]" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "../composables/useI18n";
import { useCurrencyStore } from "../stores/currency";

const { t } = useI18n();
const currency = useCurrencyStore();

const open = ref(false);
const rootRef = ref(null);
const triggerRef = ref(null);
const menuRef = ref(null);
const optionRefs = ref([]);

const select = (code) => {
  currency.setCode(code);
  open.value = false;
  nextTick(() => triggerRef.value?.focus());
};

const toggle = () => {
  open.value = !open.value;
  if (open.value) {
    optionRefs.value = [];
    nextTick(() => {
      // Focus the currently selected option, or the first one
      const selectedIdx = currency.available.findIndex(r => r.code === currency.selected);
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
  if (!open.value) return;
  if (!rootRef.value?.contains(event.target)) {
    open.value = false;
  }
};

onMounted(() => document.addEventListener("click", onDocClick));
onBeforeUnmount(() => document.removeEventListener("click", onDocClick));
</script>
