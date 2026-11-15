/**
 * useCustomerActivity — shared customer-activity aggregator.
 *
 * Single place that fetches and exposes the signed-in customer's resumable and
 * historical activity, so the super-app hub ("Continue where you left off" rail
 * + usage-sorted service grid) and the account overview share ONE source of truth
 * instead of each re-implementing the lastRide / orders / services fetches.
 *
 * Exposes:
 *   activeItems  {ref}  { orders: [], ride: null, package: null } — in-progress,
 *                       resumable activity from /customer/active/.
 *   lastOrder    {computed}  most-recent order (active first, else most recent).
 *   lastRide     {ref}  most-recent ride (any status) from /rides/history/.
 *   topVerticals {computed}  vertical ids sorted by last_activity desc (usage order),
 *                            built from /customer/services/.
 *   serviceActivity {ref}  raw { vertical: { count, last_activity, enabled } } map.
 *   hasResumable {computed}  true when there's anything to show in the resume rail.
 *   loading      {ref}  true while the initial load is in flight.
 *   errors       {ref}  per-source failure ({ services, active, ride, orders } — null
 *                       when that source loaded; set on failure so the hub can show
 *                       a per-rail error + retry instead of a silent empty rail).
 *   loadFailed   {computed}  true when EVERY source failed (total failure).
 *   load         {fn}   idempotent loader (best-effort; silent-fails per source).
 *
 * Every fetch is best-effort and isolated: a failure in one source never blocks
 * the others, and an unauthenticated customer resolves to empty state.
 */
import { computed, ref } from "vue";
import api from "../lib/api";

export function useCustomerActivity() {
  const serviceActivity = ref({}); // { vertical: { count, last_activity, enabled } }
  const activeItems = ref({ orders: [], ride: null, package: null });
  const lastRide = ref(null);
  const recentOrders = ref([]); // recent orders (any status), newest first
  const loading = ref(false);
  // Run 8 G3a A-28: per-source errors so a failed rail can say so + retry.
  const errors = ref({ services: null, active: null, ride: null, orders: null });
  const loadFailed = computed(() =>
    Object.values(errors.value).every((e) => e !== null),
  );
  let loaded = false;

  /** Vertical ids sorted by most-recent activity desc; verticals with no
   *  activity are omitted (the grid keeps its own definition order for those). */
  const topVerticals = computed(() => {
    const entries = Object.entries(serviceActivity.value || {})
      .filter(([, v]) => v && (v.count || 0) > 0 && v.last_activity)
      .sort((a, b) => {
        const ta = Date.parse(a[1].last_activity) || 0;
        const tb = Date.parse(b[1].last_activity) || 0;
        return tb - ta;
      });
    return entries.map(([id]) => id);
  });

  /** Most relevant order to resume/reorder: a still-active order if any, else
   *  the most recent. */
  const lastOrder = computed(() => {
    if (activeItems.value.orders?.length) return activeItems.value.orders[0];
    return recentOrders.value[0] || null;
  });

  const hasResumable = computed(() => {
    const a = activeItems.value;
    return Boolean(a.orders?.length || a.ride || a.package);
  });

  async function _fetchServices() {
    try {
      const { data } = await api.get("/customer/services/");
      serviceActivity.value = data.services || {};
      errors.value.services = null;
      return true;
    } catch (err) {
      errors.value.services = err?.message || "load failed";
      return false;
    }
  }

  async function _fetchActive() {
    try {
      const { data } = await api.get("/customer/active/");
      activeItems.value = {
        orders: data.orders || [],
        ride: data.ride || null,
        package: data.package || null,
      };
      errors.value.active = null;
      return true;
    } catch (err) {
      errors.value.active = err?.message || "load failed";
      return false;
    }
  }

  async function _fetchLastRide() {
    try {
      const { data } = await api.get("/rides/history/");
      const rides = Array.isArray(data) ? data : [];
      lastRide.value = rides[0] || null;
      errors.value.ride = null;
      return true;
    } catch (err) {
      errors.value.ride = err?.message || "load failed";
      return false;
    }
  }

  async function _fetchRecentOrders() {
    try {
      const { data } = await api.get("/customer/orders/?page=1");
      recentOrders.value = data.orders || [];
      errors.value.orders = null;
      return true;
    } catch (err) {
      errors.value.orders = err?.message || "load failed";
      return false;
    }
  }

  /**
   * Load all activity sources. Idempotent: only runs once unless force=true.
   * @param {{ force?: boolean }} [opts]
   */
  async function load({ force = false } = {}) {
    if (loaded && !force) return;
    loading.value = true;
    try {
      const results = await Promise.all([
        _fetchServices(),
        _fetchActive(),
        _fetchLastRide(),
        _fetchRecentOrders(),
      ]);
      // A-28: only a load with at least one working source counts as loaded —
      // a total failure stays retryable instead of silently marking done.
      if (results.some(Boolean)) loaded = true;
    } finally {
      loading.value = false;
    }
  }

  return {
    serviceActivity,
    activeItems,
    lastOrder,
    lastRide,
    recentOrders,
    topVerticals,
    hasResumable,
    loading,
    errors,
    loadFailed,
    load,
  };
}
