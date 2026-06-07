<template>
  <button
    class="group ui-panel-soft ui-surface-lift ui-press ui-reveal w-full overflow-hidden text-start focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
    :style="{ '--ui-delay': `${Math.min(index || 0, 9) * 28}ms` }"
    @click="$emit('click')"
  >
    <div class="relative h-40 w-full overflow-hidden sm:h-52">
      <img
        :src="image"
        alt=""
        class="h-full w-full object-cover transition-transform duration-[var(--motion-slow)] ease-[var(--ease-fluid)] group-hover:scale-105"
        :loading="eager ? 'eager' : 'lazy'"
        :fetchpriority="eager ? 'high' : 'auto'"
        decoding="async"
        @error="$event.target.style.display='none'"
      />
      <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-black/0" aria-hidden="true"></div>
      <!-- item count badge — RTL-safe absolute position -->
      <span
        class="ui-chip absolute end-3 top-3 border-white/25 bg-black/45 px-2 py-0.5 text-xs uppercase text-slate-100"
        aria-hidden="true"
      >
        {{ itemCountLabel(count) }}
      </span>
      <!-- title + CTA row — RTL-safe inset -->
      <div class="absolute bottom-3 start-3 end-3 flex items-center justify-between sm:bottom-4 sm:start-4 sm:end-4">
        <div class="min-w-0 me-2">
          <p class="line-clamp-2 text-lg font-semibold leading-snug text-white drop-shadow sm:text-xl" aria-hidden="true">{{ title }}</p>
          <p class="text-xs text-slate-200" aria-hidden="true">{{ t("categoryCard.openCategory") }}</p>
        </div>
        <!-- directional chevron: flips in RTL -->
        <span
          class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/95 font-semibold text-slate-900 transition-transform"
          aria-hidden="true"
        >
          <svg viewBox="0 0 24 24" class="h-4 w-4 transition-transform group-hover:translate-x-0.5 rtl:scale-x-[-1]" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M5 12h14M13 5l7 7-7 7" />
          </svg>
        </span>
      </div>
    </div>
    <!-- sr-only label so the button itself is announced meaningfully -->
    <span class="sr-only">{{ title }} — {{ itemCountLabel(count) }} — {{ t("categoryCard.openCategory") }}</span>
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
  eager: { type: Boolean, default: false },
});
</script>
