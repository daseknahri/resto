<template>
  <!--
    Inline SVG sparkline — no chart library, no extra bytes.
    Renders a polyline from an array of numeric values.

    Props:
      values   number[]  — raw data points (at least 2 for a meaningful line)
      color    string    — Tailwind color token or CSS color string
      height   number    — SVG height in px (width is always 100%)
      filled   boolean   — fill area under the line (default: true)
  -->
  <svg
    :viewBox="`-${PAD} 0 ${W + PAD * 2} ${height}`"
    preserveAspectRatio="none"
    :aria-hidden="label ? undefined : 'true'"
    class="w-full overflow-visible"
    :style="{ height: `${height}px` }"
  >
    <title v-if="label">{{ label }}</title>
    <!-- Filled area -->
    <path
      v-if="filled && points.length >= 2"
      :d="areaPath"
      class="opacity-20"
      :fill="resolvedColor"
    />
    <!-- Line -->
    <polyline
      v-if="points.length >= 2"
      :points="polylinePoints"
      fill="none"
      :stroke="resolvedColor"
      stroke-width="1.5"
      stroke-linecap="round"
      stroke-linejoin="round"
      vector-effect="non-scaling-stroke"
    />
    <!-- Last-point dot — outer ring for contrast, inner filled dot -->
    <g v-if="points.length >= 1" aria-hidden="true">
      <circle
        :cx="points[points.length - 1][0]"
        :cy="points[points.length - 1][1]"
        r="3.5"
        :fill="resolvedColor"
        fill-opacity="0.18"
        vector-effect="non-scaling-stroke"
      />
      <circle
        :cx="points[points.length - 1][0]"
        :cy="points[points.length - 1][1]"
        r="2"
        :fill="resolvedColor"
        vector-effect="non-scaling-stroke"
      />
    </g>
  </svg>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  values: { type: Array, default: () => [] },
  color: { type: String, default: "currentColor" },
  height: { type: Number, default: 28 },
  filled: { type: Boolean, default: true },
  label: { type: String, default: "" },
});

const W = 80; // internal viewBox width — arbitrary, scales with CSS width
const PAD = 2; // vertical padding so the stroke isn't clipped at edges

// Resolve Tailwind token shorthand to a CSS color, or pass through raw CSS.
// Only the tokens actually used in the dashboard are listed here.
const COLOR_MAP = {
  secondary: "var(--color-secondary)",
  emerald: "var(--color-success)",
  amber: "var(--color-secondary)",
  red: "var(--color-danger-soft)",
  slate: "var(--color-muted)",
  sky: "var(--color-info)",
};
const resolvedColor = computed(() => COLOR_MAP[props.color] || props.color || "currentColor");

// Normalise values → [x, y] pixel coordinates inside the viewBox.
const points = computed(() => {
  const vals = props.values.filter((v) => v !== null && v !== undefined && !Number.isNaN(Number(v)));
  if (vals.length < 1) return [];
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const xStep = vals.length > 1 ? W / (vals.length - 1) : 0;
  const usableH = props.height - PAD * 2;
  return vals.map((v, i) => [
    Math.round(i * xStep),
    Math.round(PAD + (1 - (Number(v) - min) / range) * usableH),
  ]);
});

const polylinePoints = computed(() => points.value.map(([x, y]) => `${x},${y}`).join(" "));

// SVG path for the filled area: line path + close down to the baseline.
const areaPath = computed(() => {
  const pts = points.value;
  if (pts.length < 2) return "";
  const baseline = props.height - PAD;
  const start = `M ${pts[0][0]},${baseline}`;
  const line = pts.map(([x, y]) => `L ${x},${y}`).join(" ");
  const end = `L ${pts[pts.length - 1][0]},${baseline} Z`;
  return `${start} ${line} ${end}`;
});
</script>
