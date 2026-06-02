<template>
  <!--
    Compact period-over-period change indicator.
    Shows +12% in green or −5% in red. Renders nothing when pct is null
    (e.g. previous period had zero revenue — no baseline to compare against).

    Props:
      pct        number | null  — signed percentage change (positive = better)
      threshold  number         — changes below this % are shown in slate (neutral)
  -->
  <p
    v-if="pct !== null && pct !== undefined"
    class="mt-0.5 text-[10px] font-semibold tabular-nums"
    :class="colorClass"
    :aria-label="ariaLabel"
  >
    {{ sign }}{{ Math.abs(pct) }}% {{ label }}
  </p>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();

const props = defineProps({
  pct:       { type: Number, default: null },
  threshold: { type: Number, default: 1 },  // changes < 1% shown as neutral
});

// "+" for gains, "−" (U+2212 minus) for losses, "" for exactly zero.
// Without the minus, a -5% change would render as "5%" — direction conveyed
// only by color, which fails for colorblind users and at-a-glance reading.
const sign = computed(() => (props.pct > 0 ? "+" : props.pct < 0 ? "−" : ""));

const colorClass = computed(() => {
  if (props.pct === null || props.pct === undefined) return "";
  if (Math.abs(props.pct) < props.threshold) return "text-slate-500";
  return props.pct > 0 ? "text-emerald-400" : "text-red-400";
});

const label = computed(() => t("ownerHome.vsPrevPeriod"));

const ariaLabel = computed(() => {
  if (props.pct === null) return "";
  const dir = props.pct > 0 ? "increase" : props.pct < 0 ? "decrease" : "no change";
  return `${Math.abs(props.pct)}% ${dir} vs previous period`;
});
</script>
