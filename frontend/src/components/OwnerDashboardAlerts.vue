<template>
  <!-- Only rendered when there is at least one actionable alert -->
  <div v-if="alerts.length" class="space-y-2" role="region" :aria-label="t('ownerHome.alertsRegion')">
    <TransitionGroup name="alert-slide" tag="div" class="space-y-2">
      <div
        v-for="alert in alerts"
        :key="alert.id"
        class="flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm"
        :class="alert.borderClass"
        role="alert"
      >
        <!-- Icon -->
        <span class="text-base leading-none" aria-hidden="true">{{ alert.icon }}</span>

        <!-- Message -->
        <p class="flex-1 text-xs font-medium" :class="alert.textClass">
          {{ alert.message }}
        </p>

        <!-- Action button (optional) -->
        <RouterLink
          v-if="alert.to"
          :to="alert.to"
          class="shrink-0 rounded-lg border px-2.5 py-1 text-[11px] font-semibold transition-colors"
          :class="alert.actionClass"
        >
          {{ alert.actionLabel }}
        </RouterLink>
        <button
          v-else-if="alert.action"
          :disabled="alert.loading"
          class="shrink-0 rounded-lg border px-2.5 py-1 text-[11px] font-semibold transition-colors disabled:opacity-50"
          :class="alert.actionClass"
          @click="alert.action()"
        >
          {{ alert.loading ? "…" : alert.actionLabel }}
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { bustCache } from "../lib/staleCache";
import { useOrderStore } from "../stores/order";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const { t } = useI18n();
const order = useOrderStore();
const tenant = useTenantStore();
const toast = useToastStore();

const props = defineProps({
  /** Number of published dishes that are currently 86'd (sold out) */
  soldOutCount: { type: Number, default: 0 },
  /** Ratings summary: { count, average } */
  ratingsSummary: { type: Object, default: null },
});

// Emits reset-complete so the parent can clear its soldOutCount optimistically
const emit = defineEmits(["reset-complete"]);

// ── Reset all availability (same logic as dish panel, keeps alerts in sync) ──
const resetting = ref(false);
const resetAvailability = async () => {
  if (resetting.value) return;
  resetting.value = true;
  try {
    await api.post("/owner/dishes/reset-availability/");
    bustCache("menu.categories");
    toast.show(t("ownerHome.resetAvailabilityDone", { count: props.soldOutCount }), "success");
    // Tell the parent to clear its soldOutCount so the alert disappears.
    emit("reset-complete");
  } catch {
    toast.show(t("ownerHome.resetAvailabilityFailed"), "error");
  } finally {
    resetting.value = false;
  }
};

// ── Stale pending orders — orders pending for more than STALE_MIN minutes ────
const STALE_MIN = 12;
const stalePendingOrders = computed(() =>
  order.orders.filter(
    (o) => o.status === "pending" && (Date.now() - new Date(o.created_at)) / 60000 > STALE_MIN
  )
);

// ── Payment overdue from tenant store ────────────────────────────────────────
const paymentOverdue = computed(() => Boolean(tenant.meta?.payment_overdue_since));

// ── Low rating alert (below 3.5 average with at least 5 reviews) ─────────────
const lowRating = computed(() => {
  const s = props.ratingsSummary;
  return s && s.count >= 5 && s.average !== null && s.average < 3.5;
});

// ── Build the alerts array ────────────────────────────────────────────────────
const alerts = computed(() => {
  const list = [];

  // 1. Payment overdue — highest priority
  if (paymentOverdue.value) {
    list.push({
      id: "payment",
      icon: "💳",
      message: t("ownerHome.alertPaymentOverdue"),
      borderClass: "border-red-500/40 bg-red-500/8",
      textClass: "text-red-200",
      to: { name: "owner-profile", query: { tab: "billing" } },
      actionLabel: t("ownerHome.alertPaymentAction"),
      actionClass: "border-red-500/40 text-red-300 hover:bg-red-500/10",
    });
  }

  // 2. Stale pending orders — operational urgency
  if (stalePendingOrders.value.length > 0) {
    list.push({
      id: "stale-pending",
      icon: "⏱",
      message: t("ownerHome.alertStalePending", {
        count: stalePendingOrders.value.length,
        minutes: STALE_MIN,
      }),
      borderClass: "border-amber-500/50 bg-amber-500/8",
      textClass: "text-amber-200",
      to: { name: "owner-orders" },
      actionLabel: t("ownerHome.alertViewOrders"),
      actionClass: "border-amber-500/40 text-amber-300 hover:bg-amber-500/10",
    });
  }

  // 3. Dishes sold out
  if (props.soldOutCount > 0) {
    list.push({
      id: "sold-out",
      icon: "🚫",
      message: t("ownerHome.alertSoldOut", { count: props.soldOutCount }),
      borderClass: "border-orange-500/30 bg-orange-500/6",
      textClass: "text-orange-200",
      action: resetAvailability,
      loading: resetting.value,
      actionLabel: t("ownerHome.alertResetAll"),
      actionClass: "border-orange-500/40 text-orange-300 hover:bg-orange-500/10",
    });
  }

  // 4. Low rating
  if (lowRating.value) {
    list.push({
      id: "low-rating",
      icon: "⭐",
      message: t("ownerHome.alertLowRating", {
        avg: props.ratingsSummary.average.toFixed(1),
        count: props.ratingsSummary.count,
      }),
      borderClass: "border-rose-500/30 bg-rose-500/6",
      textClass: "text-rose-200",
      to: { name: "owner-ratings" },
      actionLabel: t("ownerHome.alertViewRatings"),
      actionClass: "border-rose-500/40 text-rose-300 hover:bg-rose-500/10",
    });
  }

  return list;
});
</script>

<style scoped>
.alert-slide-enter-active,
.alert-slide-leave-active {
  transition: all 220ms ease;
}
.alert-slide-enter-from,
.alert-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
