<template>
  <button
    type="button"
    class="ui-press flex h-11 w-11 items-center justify-center rounded-full text-slate-300 transition-colors select-none hover:bg-slate-800 focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 focus-visible:outline-none focus:outline-none"
    :aria-label="ariaLabel"
    :disabled="disabled"
    @click="$emit('click')"
  >
    <slot>{{ label }}</slot>
  </button>
</template>

<script setup>
defineProps({
  ariaLabel: { type: String, required: true },
  label: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
});
defineEmits(['click']);
</script>
