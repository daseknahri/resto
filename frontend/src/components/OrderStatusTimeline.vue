<template>
  <div class="ui-journey-rail ui-reveal p-4 sm:p-5" :style="{ '--ui-delay': '70ms' }">
    <ol class="flex items-center justify-between gap-1">
      <li
        v-for="(step, idx) in steps"
        :key="step.value"
        class="flex flex-1 flex-col items-center gap-1.5"
      >
        <!-- step circle with optional pulse ring on the active step -->
        <div class="relative flex items-center justify-center">
          <div
            v-if="idx === currentStepIndex && currentStepIndex >= 0 && orderStatus !== 'completed'"
            class="absolute -inset-1.5 motion-safe:animate-ping rounded-full border border-[var(--color-secondary)]/35"
            aria-hidden="true"
          />
          <div
            class="relative flex h-9 w-9 items-center justify-center rounded-full border-2 text-xs font-bold transition-all duration-500"
            :class="stepClass(step.value)"
            :aria-current="idx === currentStepIndex ? 'step' : undefined"
          >
            <span v-if="isStepDone(step.value) && idx !== currentStepIndex">✓</span>
            <span v-else-if="idx === currentStepIndex">
              <!-- pulsing dot for current step -->
              <span class="block h-2.5 w-2.5 rounded-full bg-current motion-safe:animate-pulse" aria-hidden="true" />
              <span class="sr-only">{{ step.label }}</span>
            </span>
            <span v-else>{{ idx + 1 }}</span>
          </div>
        </div>
        <p class="text-center text-[10px] leading-tight text-slate-400 sm:text-xs">{{ step.label }}</p>
        <!-- Timestamp under reached steps (task 5) -->
        <p
          v-if="stepTimestamp(step.value, idx)"
          class="text-center text-[9px] leading-none tabular-nums text-slate-600"
          :aria-label="stepTimestamp(step.value, idx) || ''"
        >{{ stepTimestamp(step.value, idx) }}</p>
      </li>
    </ol>
    <!-- Progress bar -->
    <div
      class="mt-4 ui-journey-progress"
      role="progressbar"
      :aria-valuenow="progressPercent"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-label="statusLabel(orderStatus)"
      :aria-valuetext="statusLabel(orderStatus)"
    >
      <span
        class="absolute inset-y-0 start-0 rounded-full transition-all duration-500"
        :style="{ width: `${progressPercent}%` }"
      />
    </div>
  </div>
</template>

<script setup>
// Status-timeline display, extracted from OrderStatus.vue as a standalone
// presentational child (RISK FE-2). All status derivation — which step is
// current/done, per-step timestamps, progress %, labels — stays owned by the
// parent as computed properties / functions and is simply passed down as
// props (same convention as DriverPageDeliveryHistory's statusLabel/fmtDate/
// fmtMoney props): this component runs no fetch/poll/status logic of its own,
// it only renders whatever the parent has already derived.
defineProps({
  /** Ordered list of { value, label } steps for this order's fulfillment type. */
  steps: { type: Array, required: true },
  /** Index of the current step within `steps` (-1 when cancelled/unknown). */
  currentStepIndex: { type: Number, default: -1 },
  /** 0-100 fill percentage for the progress bar, owned by the parent. */
  progressPercent: { type: Number, default: 0 },
  /** Raw order status (e.g. "preparing"), used for the pulse-ring condition + aria text. */
  orderStatus: { type: String, default: "" },
  /** Per-step circle class resolver, owned by the parent. */
  stepClass: { type: Function, required: true },
  /** Whether a given step value has been reached, owned by the parent. */
  isStepDone: { type: Function, required: true },
  /** Localized "reached at" timestamp for a step, owned by the parent. */
  stepTimestamp: { type: Function, required: true },
  /** Status → localized label resolver, owned by the parent (shared with the header pill). */
  statusLabel: { type: Function, required: true },
});
</script>
