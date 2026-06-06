<template>
  <div ref="rootRef" role="group" class="relative z-[3000]" :aria-label="t('common.currency')" @keydown="onKeydown">
    <button
      ref="triggerRef"
      type="button"
      class="ui-press ui-touch-target inline-flex w-11 items-center justify-center rounded-full border border-slate-700/80 bg-slate-950/70 font-semibold text-slate-100 transition-colors hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
      :aria-expanded="open"
      aria-haspopup="menu"
      :aria-label="t('common.currency') + ': ' + currency.selected"
      @click.stop="toggle"
    >
      <span class="text-[10px] leading-none font-bold" aria-hidden="true">{{ currency.selected }}</span>
      <span class="sr-only">{{ t("common.currency") }}</span>
    </button>

    <Transition name="ui-fade">
      <div
        v-if="open"
        ref="menuRef"
        role="menu"
        :aria-label="t('common.currency')"
        class="ui-panel absolute end-0 top-full z-[3100] mt-1.5 min-w-[7.5rem] overflow-hidden p-1 shadow-2xl shadow-black/50"
      >
        <button
          v-for="(rate, idx) in currency.available"
          :key="rate.code"
          :ref="el => { if (el) optionRefs[idx] = el }"
          type="button"
          role="menuitemradio"
          :aria-checked="currency.selected === rate.code"
          class="ui-press ui-touch-target flex w-full items-center gap-2 whitespace-nowrap rounded-lg px-2.5 text-start text-[11px] text-slate-200 transition-colors hover:bg-slate-800/80 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/50"
          :class="currency.selected === rate.code ? 'bg-slate-800/70 text-[var(--color-secondary)]' : ''"
          @click="select(rate.code)"
        >
          <span class="w-7 shrink-0 font-bold tabular-nums">{{ rate.code }}</span>
          <span class="flex-1 truncate text-[10px] text-slate-400">{{ rate.symbol }}</span>
          <span v-if="currency.selected === rate.code" class="ms-auto h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-secondary)]" aria-hidden="true" />
        </button>
      </div>
    </Transition>
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
  } else if (e.key === 'Home') {
    e.preventDefault();
    const opts = optionRefs.value.filter(Boolean);
    opts[0]?.focus();
  } else if (e.key === 'End') {
    e.preventDefault();
    const opts = optionRefs.value.filter(Boolean);
    opts[opts.length - 1]?.focus();
  } else if (e.key === 'Tab') {
    open.value = false;
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
