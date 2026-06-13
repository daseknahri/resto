import { defineStore } from "pinia";
import api from "../lib/api";

export const useOrderStore = defineStore("order", {
  state: () => ({
    // Last placed order (for customer status tracking)
    placedOrderNumber: null,
    placing: false,
    placeError: null,
    placeFieldErrors: {},

    // Owner order list — ACTIVE (hot poll path, ?mode=active, no pagination)
    orders: [],
    ordersLoading: false,
    ordersError: null,
    ordersStatusFilter: "",
    ordersTotal: 0,      // retained for backward compat (active path doesn't return count)
    ordersHasMore: false, // always false on active path

    // Owner order list — HISTORY (terminal orders, paginated)
    historyOrders: [],
    historyLoading: false,
    historyError: null,
    historyHasMore: false,
    historyLimit: 50,
    historyOffset: 0,

    // Owner status update
    updatingOrderId: null,
  }),

  actions: {
    // -------------------------------------------------------
    // Customer: clear placed order (call after navigating away from order status)
    // -------------------------------------------------------
    clearPlacedOrder() {
      this.placedOrderNumber = null;
      this.placeError = null;
      this.placeFieldErrors = {};
    },

    // -------------------------------------------------------
    // Customer: place order
    // -------------------------------------------------------
    async placeOrder(payload) {
      this.placing = true;
      this.placeError = null;
      this.placeFieldErrors = {};
      this.placedOrderNumber = null;
      try {
        const res = await api.post("/place-order/", payload);
        this.placedOrderNumber = res.data.order_number;
        return res.data;
      } catch (err) {
        const data = err?.response?.data || {};
        if (typeof data === "object" && !data.detail) {
          this.placeFieldErrors = data;
        } else {
          this.placeError = data?.detail || "Order could not be placed.";
        }
        throw err;
      } finally {
        this.placing = false;
      }
    },

    // -------------------------------------------------------
    // Owner: fetch ACTIVE orders (hot poll path — ?mode=active, no COUNT)
    // -------------------------------------------------------
    // Pass { silent: true } for background polls so the loading flag is not set
    // and the orders list never flickers while already displaying data.
    async fetchOrders(statusFilter = "", { silent = false } = {}) {
      if (!silent) this.ordersLoading = true;
      this.ordersError = null;
      this.ordersStatusFilter = statusFilter;
      try {
        // When no status filter is supplied, use the fast active-mode path that
        // only returns non-terminal orders (no full-table scan, no COUNT).
        const params = statusFilter ? { status: statusFilter } : { mode: "active" };
        const res = await api.get("/owner/orders/", { params });
        this.orders = Array.isArray(res.data?.results) ? res.data.results : [];
        // The active path returns has_more: false and limit/offset: null;
        // keep ordersHasMore for any legacy code that still reads it.
        this.ordersTotal = res.data?.total ?? this.orders.length;
        this.ordersHasMore = Boolean(res.data?.has_more);
        return this.orders;
      } catch (err) {
        this.ordersError = err?.response?.data?.detail || "Failed to load orders.";
      } finally {
        if (!silent) this.ordersLoading = false;
      }
    },

    // -------------------------------------------------------
    // Owner: fetch HISTORY orders (terminal orders, paginated)
    // -------------------------------------------------------
    // Call with { reset: true } to start from the first page (e.g. when filters change).
    // Subsequent "Load more" calls pass reset: false (default).
    async fetchHistory({ reset = false, from = "", to = "", status = "" } = {}) {
      if (this.historyLoading) return;
      if (reset) {
        this.historyOrders = [];
        this.historyOffset = 0;
        this.historyHasMore = false;
        this.historyError = null;
      }
      this.historyLoading = true;
      this.historyError = null;
      try {
        const params = {
          mode: "history",
          limit: this.historyLimit,
          offset: this.historyOffset,
        };
        if (from) params.from = from;
        if (to) params.to = to;
        if (status) params.status = status;
        const res = await api.get("/owner/orders/", { params });
        const page = Array.isArray(res.data?.results) ? res.data.results : [];
        this.historyOrders = reset ? page : [...this.historyOrders, ...page];
        this.historyHasMore = Boolean(res.data?.has_more);
        this.historyOffset = (res.data?.offset ?? this.historyOffset) + page.length;
      } catch (err) {
        this.historyError = err?.response?.data?.detail || "Failed to load order history.";
      } finally {
        this.historyLoading = false;
      }
    },

    // -------------------------------------------------------
    // Owner: update order status
    // -------------------------------------------------------
    async updateOrderStatus(orderId, payload) {
      this.updatingOrderId = orderId;
      // try/finally (no catch): let the error propagate to the caller while
      // still clearing the updating flag. The previous catch only re-threw.
      try {
        const res = await api.patch(`/owner/orders/${orderId}/status/`, payload);
        const updated = res.data;
        // Patch active orders list
        const idx = this.orders.findIndex((o) => o.id === orderId);
        if (idx !== -1) {
          this.orders[idx] = { ...this.orders[idx], ...updated };
        }
        // Patch history list too (if the order is in there)
        const hidx = this.historyOrders.findIndex((o) => o.id === orderId);
        if (hidx !== -1) {
          this.historyOrders[hidx] = { ...this.historyOrders[hidx], ...updated };
        }
        return updated;
      } finally {
        this.updatingOrderId = null;
      }
    },
  },
});
