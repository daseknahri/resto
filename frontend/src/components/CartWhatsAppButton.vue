<template>
  <button
    :class="variant === 'primary'
      ? 'ui-btn-outline w-full justify-center py-2.5 text-sm font-semibold'
      : 'ui-top-link ui-touch-target ui-press flex w-full items-center justify-center gap-1.5 text-xs font-medium underline decoration-slate-600 underline-offset-2 focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 focus:outline-none disabled:opacity-50'"
    :disabled="busy"
    :aria-busy="busy"
    @click="emit('whatsapp')"
  >
    <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" :class="[iconSize, 'animate-spin shrink-0']"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
    <AppIcon v-else name="chat" :class="iconSize" />
    {{ label }}
  </button>
</template>

<script setup>
// The "send via WhatsApp" CTA button of Cart.vue, extracted as a DUMB
// presentational button (RISK FE-2). It appears in two styles — a prominent
// outline button on browse-only plans (variant="primary") and a compact underline
// link otherwise (variant="link") — so the single component takes a `variant` prop
// that switches only the classes + icon size. It owns NO logic: the parent
// (Cart.vue) keeps `openWhatsApp` and the `sendingWhatsapp` state, passed in
// verbatim as `busy` / `label`; the tap forwards intent via the `whatsapp` emit.
import { computed } from 'vue';
import AppIcon from './AppIcon.vue';

const props = defineProps({
  /** Whether the WhatsApp handoff is in flight (sendingWhatsapp). */
  busy: { type: Boolean, default: false },
  /** The button label (the parent's sendingWhatsapp-aware label, verbatim). */
  label: { type: String, default: '' },
  /** 'primary' (browse-only prominent) | 'link' (compact underline). */
  variant: { type: String, default: 'primary' },
});

const iconSize = computed(() => (props.variant === 'primary' ? 'h-4 w-4' : 'h-3.5 w-3.5'));

const emit = defineEmits(['whatsapp']);
</script>
