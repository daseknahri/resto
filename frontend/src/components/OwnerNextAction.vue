<template>
  <article
    class="ui-command-deck ui-reveal space-y-3 p-4 sm:p-5"
    role="region"
    :aria-label="t('ownerHome.focusTitle')"
  >
    <!-- Header: kicker + skip -->
    <div class="flex items-center justify-between gap-2">
      <p class="ui-kicker inline-flex items-center gap-1.5">
        <span class="ui-live-dot bg-[var(--color-secondary)]" aria-hidden="true" />
        {{ t('ownerHome.focusTitle') }}
      </p>
      <button
        v-if="action.kind !== 'allClear' && skippableCount > 1"
        type="button"
        class="ui-press rounded-full border border-slate-700 px-2.5 py-1 text-[11px] font-medium text-slate-400 transition-colors hover:border-slate-500 hover:text-slate-200"
        :aria-label="t('ownerHome.nextActionSkip')"
        @click="skip"
      >
        {{ t('ownerHome.nextActionSkip') }} →
      </button>
    </div>

    <!-- All-clear -->
    <div
      v-if="action.kind === 'allClear'"
      class="flex items-center gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/8 px-4 py-5"
      role="status"
    >
      <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-5 w-5"><path d="M20 6 9 17l-5-5"/></svg>
      </span>
      <div class="min-w-0">
        <p class="text-base font-bold text-emerald-200">{{ t('ownerHome.nextActionAllClearTitle') }}</p>
        <p class="text-xs text-emerald-300/70">{{ t('ownerHome.nextActionAllClearBody') }}</p>
      </div>
    </div>

    <!-- Single next-action card -->
    <div
      v-else
      class="rounded-2xl border px-4 py-4"
      :class="toneClass"
    >
      <div class="flex items-start gap-3">
        <span
          class="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-xl"
          :class="iconWrapClass"
          aria-hidden="true"
        >{{ icon }}</span>
        <div class="min-w-0 flex-1 space-y-0.5">
          <p class="ui-stat-label" :class="labelToneClass">{{ headline }}</p>
          <p class="text-lg font-bold leading-tight text-white">{{ title }}</p>
          <p v-if="subtitle" class="text-xs text-slate-400">{{ subtitle }}</p>
        </div>
      </div>

      <!-- Primary action button -->
      <button
        type="button"
        class="ui-btn-primary ui-press ui-touch-target mt-3.5 w-full justify-center gap-2 px-5 py-3 text-sm font-semibold"
        :disabled="busy"
        :aria-busy="busy"
        @click="act"
      >
        <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
        {{ busy ? t('common.loading') : primaryLabel }}
      </button>
    </div>
  </article>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "../composables/useI18n";
import { useNowTicker } from "../composables/useNowTicker";
import { computeNextAction } from "../lib/ownerLiveFocus";

defineOptions({ name: "OwnerNextAction" });

const props = defineProps({
  // Live orders from the order store.
  orders: { type: Array, default: () => [] },
  // Count of currently sold-out (86'd) dishes, surfaced from readiness.
  soldOutCount: { type: Number, default: 0 },
  // True while the parent is performing the emitted mutation.
  busy: { type: Boolean, default: false },
});

const emit = defineEmits(["act", "skip"]);

const { t } = useI18n();
const { now } = useNowTicker();

// THE one highest-priority action right now (recomputes as the ticker advances).
const action = computed(() =>
  computeNextAction(props.orders, { now: now.value, soldOutCount: props.soldOutCount }),
);

// How many distinct things currently need attention — drives whether "Next" is
// offered (only useful when there is more than one candidate to cycle through).
const skippableCount = computed(() => {
  const list = props.orders || [];
  const pending = list.filter((o) => o.status === "pending").length;
  const ready = list.filter((o) => o.status === "ready").length;
  const preparing = list.filter((o) => o.status === "preparing").length;
  return pending + ready + preparing + (props.soldOutCount > 0 ? 1 : 0);
});

const orderRef = computed(() => action.value.order?.order_number || "");

// ── Per-kind presentation ──────────────────────────────────────────────────
const headline = computed(() => ({
  confirm: t("ownerHome.nextActionKindConfirm"),
  dueSoon: t("ownerHome.nextActionKindDueSoon"),
  handoff: t("ownerHome.nextActionKindHandoff"),
  fire: t("ownerHome.nextActionKindFire"),
  overdue: t("ownerHome.nextActionKindOverdue"),
  soldOut: t("ownerHome.nextActionKindSoldOut"),
}[action.value.kind] || ""));

const title = computed(() => {
  const k = action.value.kind;
  const num = orderRef.value;
  if (k === "confirm") return t("ownerHome.nextActionConfirm", { order: num });
  if (k === "dueSoon") return t("ownerHome.nextActionDueSoon", { order: num });
  if (k === "handoff") return t("ownerHome.nextActionHandoff", { order: num });
  if (k === "fire") return t("ownerHome.nextActionFire", { order: num });
  if (k === "overdue") return t("ownerHome.nextActionOverdue", { order: num });
  if (k === "soldOut") return t("ownerHome.nextActionSoldOut", { n: action.value.count });
  return "";
});

const subtitle = computed(() => {
  const k = action.value.kind;
  const m = action.value.minutes;
  if (k === "confirm" && typeof m === "number") return t("ownerHome.nextActionWaiting", { min: Math.max(0, m) });
  if (k === "overdue" && typeof m === "number") return t("ownerHome.nextActionPreparingFor", { min: Math.max(0, m) });
  if (k === "dueSoon" && typeof m === "number") {
    return m >= 0
      ? t("ownerHome.upcomingFiresIn", { min: m })
      : t("ownerHome.upcomingOverdueBy", { min: Math.abs(m) });
  }
  return "";
});

const primaryLabel = computed(() => ({
  confirm: t("ownerHome.nextActionDoConfirm"),
  dueSoon: t("ownerHome.upcomingStartNow"),
  handoff: t("ownerHome.nextActionDoHandoff"),
  fire: t("ownerHome.nextActionDoFire"),
  overdue: t("ownerHome.nextActionDoReady"),
  soldOut: t("ownerHome.nextActionDoReset"),
}[action.value.kind] || ""));

const icon = computed(() => ({
  confirm: "🔔",
  dueSoon: "🗓️",
  handoff: "🛍️",
  fire: "🔥",
  overdue: "⏱",
  soldOut: "🍽️",
}[action.value.kind] || "•"));

// Tone: red for overdue/urgent, amber for waiting, sky for handoff, violet for due-soon.
const tone = computed(() => {
  const k = action.value.kind;
  if (k === "overdue") return "red";
  if (k === "confirm") return (action.value.minutes ?? 0) >= 15 ? "red" : "amber";
  if (k === "dueSoon") return "violet";
  if (k === "handoff") return "emerald";
  if (k === "fire") return "orange";
  return "slate";
});

const toneClass = computed(() => ({
  red: "border-red-500/50 bg-red-500/8",
  amber: "border-amber-500/50 bg-amber-500/8",
  violet: "border-violet-500/40 bg-violet-500/8",
  emerald: "border-emerald-500/40 bg-emerald-500/8",
  orange: "border-orange-500/40 bg-orange-500/8",
  slate: "border-slate-700 bg-slate-900/40",
}[tone.value]));

const iconWrapClass = computed(() => ({
  red: "bg-red-500/15",
  amber: "bg-amber-500/15",
  violet: "bg-violet-500/15",
  emerald: "bg-emerald-500/15",
  orange: "bg-orange-500/15",
  slate: "bg-slate-800/60",
}[tone.value]));

const labelToneClass = computed(() => ({
  red: "text-red-300/80",
  amber: "text-amber-300/80",
  violet: "text-violet-300/80",
  emerald: "text-emerald-300/80",
  orange: "text-orange-300/80",
  slate: "text-slate-400",
}[tone.value]));

const act = () => emit("act", action.value);
const skip = () => emit("skip", action.value);

// Exposed for parents/tests that want the current descriptor directly.
defineExpose({ action });
</script>
