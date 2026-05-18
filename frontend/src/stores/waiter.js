import { defineStore } from "pinia";
import api from "../lib/api";

const NEXT_STATUS = {
  pending: "confirmed",
  confirmed: "preparing",
  preparing: "ready",
  ready: "completed",
};

export const useWaiterStore = defineStore("waiter", {
  state: () => ({
    orders: [],
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

    nextStatus: () => (currentStatus) => NEXT_STATUS[currentStatus] ?? null,
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
    // Update order status — optimistic, offline-safe
    // -------------------------------------------------------
    async advanceStatus(orderId) {
      const order = this.orders.find((o) => o.id === orderId);
      if (!order) return;

      const next = NEXT_STATUS[order.status];
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

      try {
        await api.patch(`/owner/orders/${orderId}/status/`, { status: next });
        // On success, remove from active list if completed
        if (next === "completed") {
          this.orders = this.orders.filter((o) => o.id !== orderId);
        }
      } catch {
        // Revert optimistic update and queue for retry
        order.status = prev;
        this._enqueue(orderId, next);
      } finally {
        this.updatingOrderIds = new Set([...this.updatingOrderIds].filter((id) => id !== orderId));
      }
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
