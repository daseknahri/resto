<template>
  <section class="mx-auto hidden w-full max-w-5xl px-4 pt-3 md:block">
    <div class="ui-panel space-y-2 p-3 md:p-4">
      <p class="text-[11px] uppercase tracking-[0.2em] text-slate-500">Guest journey</p>
      <div class="grid grid-cols-4 gap-2">
        <RouterLink
          v-for="step in steps"
          :key="step.name"
          :to="step.to"
          class="rounded-xl border px-2 py-2 text-center transition md:px-3"
          :class="stepClass(step)"
          :aria-current="step.isActive ? 'page' : undefined"
        >
          <div class="mx-auto mb-1 flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-semibold" :class="stepDotClass(step)">
            {{ step.index + 1 }}
          </div>
          <p class="text-xs font-semibold leading-tight">{{ step.label }}</p>
          <p class="mt-0.5 text-[10px] leading-tight" :class="stepHintClass(step)">{{ step.hint }}</p>
        </RouterLink>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useCartStore } from "../stores/cart";
import { useLeadStore } from "../stores/lead";

const route = useRoute();
const cart = useCartStore();
const lead = useLeadStore();

const activeStep = computed(() => {
  const name = String(route.name || "");
  if (name === "customer-home") return 0;
  if (name === "menu" || name === "category" || name === "dish") return 1;
  if (name === "cart") return 2;
  if (name === "reserve") return 3;
  return 0;
});

const steps = computed(() => [
  {
    index: 0,
    name: "customer-home",
    label: "Info",
    to: { name: "customer-home" },
    hint: lead.success ? "Saved" : "Start",
  },
  {
    index: 1,
    name: "menu",
    label: "Menu",
    to: { name: "menu" },
    hint: "Browse",
  },
  {
    index: 2,
    name: "cart",
    label: "Cart",
    to: { name: "cart" },
    hint: cart.count ? `${cart.count} item${cart.count > 1 ? "s" : ""}` : "Review",
  },
  {
    index: 3,
    name: "reserve",
    label: "Reserve",
    to: { name: "reserve" },
    hint: "Book",
  },
].map((step) => {
  const isActive = activeStep.value === step.index;
  const isCompleted = activeStep.value > step.index || (step.index === 0 && lead.success);
  return {
    ...step,
    isActive,
    isCompleted,
  };
}));

const stepClass = (step) => {
  if (step.isActive) return "border-[var(--color-secondary)] bg-[var(--color-secondary)]/12 text-[var(--color-secondary)]";
  if (step.isCompleted) return "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
  return "border-slate-700/70 bg-slate-950/40 text-slate-200 hover:border-[var(--color-secondary)]/50 hover:text-[var(--color-secondary)]";
};

const stepDotClass = (step) => {
  if (step.isActive) return "border-[var(--color-secondary)] bg-[var(--color-secondary)]/20 text-[var(--color-secondary)]";
  if (step.isCompleted) return "border-emerald-400/60 bg-emerald-500/20 text-emerald-200";
  return "border-slate-600 bg-slate-900/60 text-slate-300";
};

const stepHintClass = (step) => {
  if (step.isActive) return "text-[var(--color-secondary)]";
  if (step.isCompleted) return "text-emerald-200/90";
  return "text-slate-500";
};
</script>
