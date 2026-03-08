<template>
  <transition name="fade-slide">
    <div
      v-if="toast.visible"
      class="fixed bottom-6 right-6 z-30 rounded-2xl border border-slate-800 bg-slate-900/90 px-4 py-3 shadow-2xl shadow-black/40 text-sm text-slate-100 flex items-center gap-3"
      role="status"
      aria-live="polite"
    >
      <span
        class="h-2 w-2 rounded-full"
        :class="toast.type === 'success' ? 'bg-emerald-400' : toast.type === 'error' ? 'bg-rose-400' : 'bg-amber-300'"
      ></span>
      <span>{{ toast.message }}</span>
      <button class="text-xs text-slate-400 hover:text-slate-200" @click="toast.hide()">Close</button>
    </div>
  </transition>
</template>

<script setup>
import { useToastStore } from "../stores/toast";

const toast = useToastStore();
</script>

<style scoped>
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 200ms ease;
}
.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
