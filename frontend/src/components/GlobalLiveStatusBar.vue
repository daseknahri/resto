<template>
  <!--
    GlobalLiveStatusBar — persistent slim bar shown whenever the signed-in
    customer has an in-progress order, ride, or package. Mounts above the
    bottom nav so it is always visible without overlapping it.

    Self-hides (v-if) when nothing is active, so it consumes zero layout
    space on idle screens. Polling interval: 30 s.
  -->
  <Transition name="glsb-slide">
    <div
      v-if="visible"
      class="glsb-root"
      role="status"
      :aria-label="t('globalLiveStatusBar.ariaRegion')"
    >
      <!-- Primary active item link -->
      <RouterLink
        :to="primaryTo"
        class="glsb-link"
        :aria-label="primaryAriaLabel"
        @click="onLinkClick"
      >
        <!-- pulsing dot -->
        <span class="glsb-dot-wrap" aria-hidden="true">
          <span class="glsb-dot-ping" />
          <span class="glsb-dot-core" />
        </span>

        <!-- icon -->
        <span class="glsb-icon" aria-hidden="true">{{ primaryIcon }}</span>

        <!-- label text -->
        <span class="glsb-label">{{ primaryLabel }}</span>

        <!-- status chip -->
        <span class="glsb-chip">{{ primaryStatusText }}</span>

        <!-- chevron -->
        <svg
          class="glsb-chevron rtl:scale-x-[-1]"
          aria-hidden="true"
          viewBox="0 0 16 16"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path d="M6 12l4-4-4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </RouterLink>

      <!-- overflow badge: +N more active items -->
      <span
        v-if="overflowCount > 0"
        class="glsb-overflow"
        :aria-label="t('globalLiveStatusBar.moreActive', { n: overflowCount })"
        aria-hidden="false"
      >
        +{{ overflowCount }}
      </span>
    </div>
  </Transition>
</template>

<script setup>
/**
 * GlobalLiveStatusBar
 *
 * Pulls from useCustomerActivity._fetchActive() on a 30-second interval so
 * the bar stays fresh without requiring a WebSocket. The composable is
 * re-used (not re-created) so other consumers (SuperAppHub) benefit from
 * the same in-flight request.
 *
 * Routing logic mirrors SuperAppHub.resumeCards:
 *   order with restaurant_slug → marketplace-order-status
 *   order without slug        → order-status
 *   ride                      → /ride
 *   package                   → /send-package
 */
import { computed, onMounted, onUnmounted } from "vue";
import { useCustomerActivity } from "../composables/useCustomerActivity";
import { useI18n } from "../composables/useI18n";
import { useCustomerStore } from "../stores/customer";

const { t } = useI18n();
const customerStore = useCustomerStore();

// ── activity ────────────────────────────────────────────────────────────────
const { activeItems, load } = useCustomerActivity();

// Refresh every 30 s while component is mounted.
let _timer = null;
const _refresh = () => load({ force: true });

onMounted(async () => {
  if (customerStore.isAuthenticated) {
    await load();
  }
  _timer = setInterval(() => {
    if (customerStore.isAuthenticated) _refresh();
  }, 30_000);
});

onUnmounted(() => {
  clearInterval(_timer);
});

// ── status translation helpers ────────────────────────────────────────────
const ORDER_STATUS_LABEL = {
  pending:          "globalLiveStatusBar.statusPending",
  confirmed:        "globalLiveStatusBar.statusConfirmed",
  preparing:        "globalLiveStatusBar.statusPreparing",
  ready:            "globalLiveStatusBar.statusReady",
  out_for_delivery: "globalLiveStatusBar.statusOutForDelivery",
};
const RIDE_STATUS_LABEL = {
  scheduled:   "tripSchedule.statusScheduled",
  searching:   "globalLiveStatusBar.statusSearchingDriver",
  accepted:    "globalLiveStatusBar.statusDriverOnWay",
  arrived:     "globalLiveStatusBar.statusDriverArrived",
  in_progress: "globalLiveStatusBar.statusInProgress",
};
const PKG_STATUS_LABEL = {
  searching:   "globalLiveStatusBar.statusSearchingCourier",
  accepted:    "globalLiveStatusBar.statusCourierOnWay",
  arrived:     "globalLiveStatusBar.statusCourierArrived",
  in_progress: "globalLiveStatusBar.statusPackageInProgress",
};

const _orderStatus  = (s) => t(ORDER_STATUS_LABEL[s] || "globalLiveStatusBar.statusPending");
const _rideStatus   = (s) => t(RIDE_STATUS_LABEL[s]  || "globalLiveStatusBar.statusInProgress");
const _pkgStatus    = (s) => t(PKG_STATUS_LABEL[s]   || "globalLiveStatusBar.statusInProgress");

// ── primary card (first active item across all types) ────────────────────
/**
 * Priority: orders first (most common), then ride, then package.
 * Returns a descriptor object or null.
 */
const primaryCard = computed(() => {
  const a = activeItems.value;
  const orders = a.orders || [];
  if (orders.length > 0) {
    const o = orders[0];
    return {
      kind: "order",
      icon: "🍽️",
      label: o.restaurant_name
        ? t("globalLiveStatusBar.orderFromName", { name: o.restaurant_name })
        : t("globalLiveStatusBar.orderLabel"),
      statusText: _orderStatus(o.status),
      to: o.restaurant_slug
        ? { name: "marketplace-order-status", params: { slug: o.restaurant_slug, orderNumber: o.order_number } }
        : { name: "order-status", params: { orderNumber: o.order_number } },
      ariaLabel: t("globalLiveStatusBar.tapToTrackOrder", { number: o.order_number }),
    };
  }
  if (a.ride) {
    const r = a.ride;
    return {
      kind: "ride",
      icon: "🚕",
      label: r.dropoff_address || t("globalLiveStatusBar.rideLabel"),
      statusText: _rideStatus(r.status),
      to: { name: "ride" },
      ariaLabel: t("globalLiveStatusBar.tapToTrackRide"),
    };
  }
  if (a.package) {
    const p = a.package;
    return {
      kind: "package",
      icon: "📦",
      label: p.dropoff_address || t("globalLiveStatusBar.packageLabel"),
      statusText: _pkgStatus(p.status),
      to: { name: "send-package" },
      ariaLabel: t("globalLiveStatusBar.tapToTrackPackage"),
    };
  }
  return null;
});

const primaryTo         = computed(() => primaryCard.value?.to || "/");
const primaryIcon       = computed(() => primaryCard.value?.icon || "");
const primaryLabel      = computed(() => primaryCard.value?.label || "");
const primaryStatusText = computed(() => primaryCard.value?.statusText || "");
const primaryAriaLabel  = computed(() => primaryCard.value?.ariaLabel || "");

// Total active count (orders + optional ride + optional package).
const totalActiveCount = computed(() => {
  const a = activeItems.value;
  return (a.orders?.length || 0) + (a.ride ? 1 : 0) + (a.package ? 1 : 0);
});

// Items shown beyond the primary card.
const overflowCount = computed(() => Math.max(0, totalActiveCount.value - 1));

// Bar is visible only when authenticated AND something is active.
const visible = computed(
  () => customerStore.isAuthenticated && primaryCard.value !== null,
);

// ── accessibility helper ──────────────────────────────────────────────────
const onLinkClick = () => {
  // No additional side-effects needed; router handles navigation.
};
</script>

<style scoped>
/* ── Bar shell ──────────────────────────────────────────────────────────── */
.glsb-root {
  /*
   * Sits above the bottom nav (which is 64px + safe-area on mobile).
   * On md+ screens the bottom nav is hidden (md:hidden) so we use a fixed
   * bottom that retracts automatically on desktop.
   */
  position: fixed;
  bottom: calc(64px + env(safe-area-inset-bottom, 0px));
  inset-inline-start: 0;
  inset-inline-end: 0;
  z-index: 200; /* below modals (z-300+) but above content */
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none; /* let taps pass through the gap area */
  padding: 0 1rem 0.375rem;
}

@media (min-width: 768px) {
  /* No bottom nav on desktop → sit just above the page bottom */
  .glsb-root {
    bottom: 0.75rem;
  }
}

/* ── Link pill ──────────────────────────────────────────────────────────── */
.glsb-link {
  pointer-events: auto;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  min-height: 44px; /* tap-target ≥ 44 px */
  padding: 0.5rem 0.875rem 0.5rem 0.75rem;
  border-radius: 9999px;
  border: 1px solid rgba(var(--color-secondary-rgb, 234 179 8), 0.35);
  background: rgba(15, 23, 42, 0.92); /* slate-950/92 */
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  color: var(--color-secondary, #eab308);
  text-decoration: none;
  font-size: 0.8125rem; /* 13px */
  font-weight: 600;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.45);
  transition: border-color 0.15s, background-color 0.15s, opacity 0.15s;
  max-width: calc(100vw - 2.5rem);
}

.glsb-link:hover,
.glsb-link:focus-visible {
  border-color: rgba(var(--color-secondary-rgb, 234 179 8), 0.65);
  background: rgba(15, 23, 42, 0.97);
  outline: none;
}

.glsb-link:focus-visible {
  outline: 2px solid var(--color-secondary, #eab308);
  outline-offset: 2px;
}

/* ── Pulsing live dot ───────────────────────────────────────────────────── */
.glsb-dot-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 0.625rem;
  height: 0.625rem;
  flex-shrink: 0;
}
.glsb-dot-ping {
  position: absolute;
  inset: 0;
  border-radius: 9999px;
  background: var(--color-secondary, #eab308);
  opacity: 0.5;
  animation: ping 1.2s cubic-bezier(0, 0, 0.2, 1) infinite;
}
.glsb-dot-core {
  position: relative;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 9999px;
  background: var(--color-secondary, #eab308);
}

@keyframes ping {
  75%, 100% { transform: scale(2); opacity: 0; }
}

/* ── Icon ───────────────────────────────────────────────────────────────── */
.glsb-icon {
  font-size: 1rem;
  line-height: 1;
  flex-shrink: 0;
}

/* ── Label text ─────────────────────────────────────────────────────────── */
.glsb-label {
  max-width: 9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #f1f5f9; /* slate-100 */
}

/* ── Status chip ────────────────────────────────────────────────────────── */
.glsb-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  border: 1px solid rgba(var(--color-secondary-rgb, 234 179 8), 0.3);
  background: rgba(var(--color-secondary-rgb, 234 179 8), 0.1);
  color: var(--color-secondary, #eab308);
  font-size: 0.6875rem; /* 11px */
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── Chevron ────────────────────────────────────────────────────────────── */
.glsb-chevron {
  width: 0.875rem;
  height: 0.875rem;
  color: rgba(241, 245, 249, 0.5); /* slate-100/50 */
  flex-shrink: 0;
}

/* ── Overflow badge ─────────────────────────────────────────────────────── */
.glsb-overflow {
  pointer-events: auto;
  margin-inline-start: 0.375rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.5rem;
  height: 1.5rem;
  border-radius: 9999px;
  background: rgba(var(--color-secondary-rgb, 234 179 8), 0.15);
  border: 1px solid rgba(var(--color-secondary-rgb, 234 179 8), 0.35);
  color: var(--color-secondary, #eab308);
  font-size: 0.6875rem;
  font-weight: 700;
  padding: 0 0.25rem;
}

/* ── Slide-in/out transition ────────────────────────────────────────────── */
.glsb-slide-enter-active,
.glsb-slide-leave-active {
  transition: transform 0.22s ease, opacity 0.22s ease;
}
.glsb-slide-enter-from,
.glsb-slide-leave-to {
  transform: translateY(1rem);
  opacity: 0;
}
</style>
