<template>
  <div ref="rootRef" class="relative z-[3000]" :aria-label="t('common.currency')">
    <button
      type="button"
      class="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-700/80 bg-slate-950/70 font-semibold text-slate-100 transition hover:border-[var(--color-secondary)] hover:text-[var(--color-secondary)]"
      :aria-expanded="open ? 'true' : 'false'"
      @click.stop="open = !open"
    >
      <span class="text-[10px] leading-none font-bold">{{ currency.selected }}</span>
      <span class="sr-only">{{ t("common.currency") }}</span>
    </button>

    <div
      v-if="open"
      class="absolute right-0 top-full z-[3100] mt-1.5 min-w-[7rem] overflow-hidden rounded-xl border border-slate-700/80 bg-slate-950/95 p-1 shadow-2xl shadow-black/50 backdrop-blur"
    >
      <button
        v-for="rate in currency.available"
        :key="rate.code"
        type="button"
        class="flex w-full items-center gap-2 whitespace-nowrap rounded-lg px-2 py-1.5 text-left text-[11px] text-slate-200 transition hover:bg-slate-800/80"
        :class="currency.selected === rate.code ? 'bg-slate-800/70 text-[var(--color-secondary)]' : ''"
        @click="select(rate.code)"
      >
        <span class="w-7 shrink-0 font-bold">{{ rate.code }}</span>
        <span class="truncate text-slate-400 text-[10px]">{{ rate.symbol }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "../composables/useI18n";
import { useCurrencyStore } from "../stores/currency";

const { t } = useI18n();
const currency = useCurrencyStore();

const open = ref(false);
const rootRef = ref(null);

const select = (code) => {
  currency.setCode(code);
  open.value = false;
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
