<template>
  <section class="mx-auto hidden w-full max-w-6xl px-4 pt-3 md:block" :aria-label="t('customerFlow.title')">
    <div class="ui-journey-rail ui-reveal space-y-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 space-y-1">
          <p class="ui-kicker">{{ t("customerFlow.title") }}</p>
          <p class="truncate text-sm font-semibold leading-tight text-white">{{ currentStepLabel }}</p>
        </div>
        <span
          class="ui-status-pill tabular-nums"
          :aria-label="`${t('customerFlow.title')} — ${steps.length ? activeStep + 1 : 0} / ${steps.length}`"
        >
          {{ steps.length ? activeStep + 1 : 0 }}/{{ steps.length }}
        </span>
      </div>

      <div
        class="ui-journey-progress"
        role="progressbar"
        :aria-label="t('customerFlow.title')"
        :aria-valuenow="activeStep"
        :aria-valuemin="0"
        :aria-valuemax="steps.length - 1"
        :aria-valuetext="`${activeStep + 1} / ${steps.length}`"
      >
        <span :style="{ width: progressWidth }"></span>
      </div>

      <div class="ui-state-strip">
        <div class="relative z-[1] grid gap-2 md:grid-cols-[minmax(0,1fr),auto,auto] md:items-center">
          <div class="min-w-0">
            <p class="truncate text-sm font-medium text-white">{{ currentStepLabel }}</p>
            <p class="ui-subtle mt-1 text-xs">{{ currentStepHint }}</p>
          </div>
          <span class="ui-state-chip tabular-nums" data-active="true">
            {{ completionLabel }}
          </span>
          <span class="ui-state-chip" :data-active="Boolean(cart.count)">
            {{ cart.count ? itemCountLabel(cart.count) : t("customerFlow.review") }}
          </span>
        </div>
      </div>

      <div class="grid min-w-0 grid-cols-5 gap-3">
        <RouterLink
          v-for="(step, index) in steps"
          :key="step.name"
          :to="step.to"
          class="ui-journey-step ui-surface-lift ui-press ui-reveal"
          :data-active="step.isActive"
          :data-complete="step.isCompleted"
          :aria-current="step.isActive ? 'page' : undefined"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <div class="flex items-start justify-between gap-3">
            <div
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold tabular-nums"
              :class="stepDotClass(step)"
              aria-hidden="true"
            >
              {{ step.index + 1 }}
            </div>
            <span class="ui-chip text-[10px] tabular-nums">
              {{ String(step.index + 1).padStart(2, "0") }}
            </span>
          </div>
          <div class="mt-3 space-y-1">
            <p class="text-start text-sm font-semibold leading-tight">{{ step.label }}</p>
            <p class="text-start text-[11px] leading-tight" :class="stepHintClass(step)">{{ step.hint }}</p>
          </div>
        </RouterLink>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { useCartStore } from "../stores/cart";
import { useCustomerStore } from "../stores/customer";
import { useLeadStore } from "../stores/lead";

const route = useRoute();
const cart = useCartStore();
const customerStore = useCustomerStore();
const lead = useLeadStore();
const { itemCountLabel, t } = useI18n();

const activeStep = computed(() => {
  const name = String(route.name || "");
  if (name === "customer-home") return 0;
  if (name === "menu" || name === "category" || name === "dish") return 1;
  if (name === "cart") return 2;
  if (name === "reserve") return 3;
  if (name === "customer-account") return 4;
  return 0;
});

const steps = computed(() => [
  {
    index: 0,
    name: "customer-home",
    label: t("customerFlow.info"),
    to: { name: "customer-home" },
    hint: lead.success ? t("customerFlow.saved") : t("customerFlow.start"),
  },
  {
    index: 1,
    name: "menu",
    label: t("customerFlow.menu"),
    to: { name: "menu" },
    hint: t("customerFlow.browse"),
  },
  {
    index: 2,
    name: "cart",
    label: t("customerFlow.cart"),
    to: { name: "cart" },
    hint: cart.count ? itemCountLabel(cart.count) : t("customerFlow.review"),
  },
  {
    index: 3,
    name: "reserve",
    label: t("customerFlow.reserve"),
    to: { name: "reserve" },
    hint: t("customerFlow.book"),
  },
  {
    index: 4,
    name: "customer-account",
    label: t("customerFlow.account"),
    to: { name: "customer-account" },
    hint: customerStore.isAuthenticated ? t("customerFlow.accountSignedIn") : t("customerFlow.accountSignIn"),
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

const currentStepLabel = computed(() => steps.value[activeStep.value]?.label || t("customerFlow.info"));
const currentStepHint = computed(() => steps.value[activeStep.value]?.hint || t("customerFlow.start"));
const completionLabel = computed(() => `${steps.value.filter((step) => step.isCompleted).length}/${steps.value.length}`);
const progressWidth = computed(() => {
  const maxIndex = Math.max(steps.value.length - 1, 1);
  return `${(activeStep.value / maxIndex) * 100}%`;
});

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
