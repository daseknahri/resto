import { defineStore } from "pinia";
import api from "../lib/api";

const LINEAR_NEXT = {
  pending: "confirmed",
  confirmed: "preparing",
  preparing: "ready",
};

// Next status is fulfillment-type aware:
//  - pickup:  ready → completed (picked up)
//  - delivery: ready → out_for_delivery → completed (delivered)
//  - dine-in: ready (unpaid) is finished by the Settle action, not a plain
//             advance, so return null; a prepaid dine-in ready → completed.
function nextStatusFor(order) {
  if (!order) return null;
  const s = order.status;
  if (s in LINEAR_NEXT) return LINEAR_NEXT[s];
  if (s === "ready") {
    if (order.fulfillment_type === "delivery") return "out_for_delivery";
    if (order.fulfillment_type === "table" && order.payment_status !== "paid") return null;
    return "completed";
  }
  if (s === "out_for_delivery") return "completed";
  return null;
}

export const useWaiterStore = defineStore("waiter", {
  state: () => ({
    orders: [],
    recentOrders: [],       // recently finished orders (for the waiter's history view)
    recentLoading: false,
    loading: false,
    error: null,
    lastSyncAt: null,          // ISO string of last successful full fetch
    offlineQueue: [],          // [{ orderId, newStatus, queuedAt }]
    isSyncing: false,
    isOnline: typeof navigator !== "undefined" ? navigator.onLine : true,
    updatingOrderIds: new Set(),
    shiftSummary: null,        // { orders_handled, total_revenue, currency, average_prep_time_minutes, since, period_hours }
    shiftSummaryLoading: false,
    shiftSummaryError: null,
  }),

  getters: {
    activeOrders: (state) => state.orders,

    pendingCount: (state) => state.orders.filter((o) => o.status === "pending").length,

    byStatus: (state) => {
      const groups = { pending: [], confirmed: [], preparing: [], ready: [] };
      for (const o of state.orders) {
        if (groups[o.status]) groups[o.status].push(o);
      }
      return groups;
    },

    queueLength: (state) => state.offlineQueue.length,

    nextStatus: () => (order) => nextStatusFor(order),

    unpaidOrders: (state) => state.orders.filter((o) => o.payment_status !== "paid"),
  },

  actions: {
    // -------------------------------------------------------
    // Connectivity tracking — call from the layout once
    // -------------------------------------------------------
    setupConnectivityListeners() {
      if (typeof window === "undefined") return;
      window.addEventListener("online", this._onOnline);
      window.addEventListener("offline", this._onOffline);
    },

    teardownConnectivityListeners() {
      if (typeof window === "undefined") return;
      window.removeEventListener("online", this._onOnline);
      window.removeEventListener("offline", this._onOffline);
    },

    _onOnline() {
      this.isOnline = true;
      this.flushQueue();
    },

    _onOffline() {
      this.isOnline = false;
    },

    // -------------------------------------------------------
    // Fetch active orders
    // -------------------------------------------------------
    async fetchOrders({ silent = false } = {}) {
      if (!silent) this.loading = true;
      this.error = null;
      try {
        const res = await api.get("/staff/orders/");
        this.orders = Array.isArray(res.data?.results) ? res.data.results : [];
        this.lastSyncAt = new Date().toISOString();
        return this.orders;
      } catch {
        if (!silent) this.error = "Failed to load orders.";
      } finally {
        if (!silent) this.loading = false;
      }
    },

    // -------------------------------------------------------
    // Recently finished orders (last 24h) — the waiter's history view
    // -------------------------------------------------------
    async fetchRecent() {
      this.recentLoading = true;
      try {
        const res = await api.get("/staff/orders/", { params: { recent: 1 } });
        this.recentOrders = Array.isArray(res.data?.results) ? res.data.results : [];
        return this.recentOrders;
      } catch {
        /* keep last */
      } finally {
        this.recentLoading = false;
      }
    },

    // -------------------------------------------------------
    // Update order status — optimistic, offline-safe
    // -------------------------------------------------------
    async advanceStatus(orderId) {
      const order = this.orders.find((o) => o.id === orderId);
      if (!order) return;

      const next = nextStatusFor(order);
      if (!next) return;

      const prev = order.status;
      // Optimistic update
      order.status = next;
      this.updatingOrderIds = new Set([...this.updatingOrderIds, orderId]);

      if (!this.isOnline) {
        this._enqueue(orderId, next);
        this.updatingOrderIds = new Set([...this.updatingOrderIds].filter((id) => id !== orderId));
        return;
      }

      let success = false;
      try {
        await api.patch(`/owner/orders/${orderId}/status/`, { status: next });
        // On success, remove from active list if completed
        if (next === "completed") {
          this.orders = this.orders.filter((o) => o.id !== orderId);
        }
        success = true;
      } catch {
        // Revert optimistic update and queue for retry
        order.status = prev;
        this._enqueue(orderId, next);
      } finally {
        this.updatingOrderIds = new Set([...this.updatingOrderIds].filter((id) => id !== orderId));
      }
      return success;
    },

    // -------------------------------------------------------
    // Offline queue management
    // -------------------------------------------------------
    _enqueue(orderId, newStatus) {
      // Replace any existing queued update for the same order
      this.offlineQueue = [
        ...this.offlineQueue.filter((e) => e.orderId !== orderId),
        { orderId, newStatus, queuedAt: Date.now() },
      ];
    },

    // -------------------------------------------------------
    // Shift summary
    // -------------------------------------------------------
    async fetchShiftSummary(since = null) {
      this.shiftSummaryLoading = true;
      this.shiftSummaryError = null;
      try {
        const params = since ? { since } : {};
        const res = await api.get("/staff/shift-summary/", { params });
        this.shiftSummary = res.data;
        return res.data;
      } catch {
        this.shiftSummaryError = "Failed to load shift summary.";
      } finally {
        this.shiftSummaryLoading = false;
      }
    },

    // -------------------------------------------------------
    // Settle / mark paid — record cash/card collected. On a READY
    // dine-in order this completes it too (settle & close).
    // -------------------------------------------------------
    async markPaid(orderId) {
      const order = this.orders.find((o) => o.id === orderId);
      if (!order) return null;
      this.updatingOrderIds = new Set([...this.updatingOrderIds, orderId]);
      try {
        const res = await api.post(`/owner/orders/${orderId}/mark-paid/`, {
          complete: order.status === "ready",
        });
        order.payment_status = res.data.payment_status;
        if (res.data.completed) {
          // Settled & closed — drop from the active list.
          this.orders = this.orders.filter((o) => o.id !== orderId);
        }
        return res.data; // { payment_status, completed, status, ... }
      } catch {
        return null;
      } finally {
        this.updatingOrderIds = new Set([...this.updatingOrderIds].filter((id) => id !== orderId));
      }
    },

    // -------------------------------------------------------
    // Partial / full payment via the new payments ledger endpoint.
    // Returns { data, errorCode } — errorCode is the 409 `code` string or null.
    // -------------------------------------------------------
    async postPayment(orderId, method, amount) {
      this.updatingOrderIds = new Set([...this.updatingOrderIds, orderId]);
      try {
        const body = { method };
        if (amount !== null && amount !== undefined) body.amount = amount;
        // One key per payment intent: the backend short-circuits a retry of the
        // same key (5-min window), so a double-tap or timeout-retry can never
        // record the same physical payment twice.
        body.idempotency_key = (crypto.randomUUID && crypto.randomUUID()) || `${orderId}-${method}-${amount ?? 'full'}-${performance.now()}`;
        const res = await api.post(`/staff/orders/${orderId}/payments/`, body);
        // Patch the in-memory order with the updated fields from the response.
        const order = this.orders.find((o) => o.id === orderId);
        if (order && res.data) {
          order.payment_status = res.data.payment_status ?? order.payment_status;
          order.amount_paid = res.data.amount_paid;
          order.outstanding = res.data.outstanding;
          if (res.data.payments) order.payments = res.data.payments;
          if (res.data.completed) {
            this.orders = this.orders.filter((o) => o.id !== orderId);
          }
        }
        return { data: res.data, errorCode: null };
      } catch (err) {
        const code = err?.response?.data?.code ?? null;
        return { data: null, errorCode: code };
      } finally {
        this.updatingOrderIds = new Set([...this.updatingOrderIds].filter((id) => id !== orderId));
      }
    },

    // -------------------------------------------------------
    // Rate the customer — only the server who handled the order
    // (the backend enforces this via handled_by).
    // -------------------------------------------------------
    async rateCustomer(orderId, score, note = "") {
      await api.post(`/owner/orders/${orderId}/customer-rating/`, { score, note });
      const order = this.orders.find((o) => o.id === orderId);
      if (order) order.my_customer_rating = { score, note };
    },

    // -------------------------------------------------------
    // Item-level kitchen readiness — tick a single line item ready (optimistic).
    // -------------------------------------------------------
    async toggleItemReady(orderId, itemId, ready) {
      const order = this.orders.find((o) => o.id === orderId);
      const item = order?.items?.find((it) => it.id === itemId);
      if (item) item.is_ready = ready; // optimistic
      try {
        await api.patch(`/staff/order-items/${itemId}/ready/`, { ready });
        return true;
      } catch {
        if (item) item.is_ready = !ready; // revert on failure
        return false;
      }
    },

    async flushQueue() {
      if (this.isSyncing || !this.offlineQueue.length) return;
      this.isSyncing = true;
      const toFlush = [...this.offlineQueue];
      this.offlineQueue = [];
      try {
        for (const entry of toFlush) {
          try {
            await api.patch(`/owner/orders/${entry.orderId}/status/`, { status: entry.newStatus });
            if (entry.newStatus === "completed") {
              this.orders = this.orders.filter((o) => o.id !== entry.orderId);
            } else {
              const order = this.orders.find((o) => o.id === entry.orderId);
              if (order) order.status = entry.newStatus;
            }
          } catch {
            // Re-queue failed entries
            this.offlineQueue.push(entry);
          }
        }
      } finally {
        this.isSyncing = false;
      }
    },
  },
});
