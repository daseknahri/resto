import { defineStore } from "pinia";
import api from "../lib/api";
import {
  afterFailedCheckout,
  checkoutSnapshot,
  isSameSnapshot,
  keyForCheckoutSnapshot,
} from "../lib/checkoutIdempotency";

export const useOrderStore = defineStore("order", {
  state: () => ({
    // Last placed order (for customer status tracking)
    placedOrderNumber: null,
    placing: false,
    placeError: null,
    placeFieldErrors: {},
    // Idempotency state of the retryable checkout attempt: { key, fingerprint, outcomeUnknown }
    // (null between orders). See lib/checkoutIdempotency.
    _checkoutIdem: null,

    // Owner order list — ACTIVE (hot poll path, ?mode=active, no pagination)
    orders: [],
    ordersLoading: false,
    ordersError: null,
    ordersStatusFilter: "",
    ordersTotal: 0,      // retained for backward compat (active path doesn't return count)
    ordersHasMore: false, // always false on active path
    // Re-entrancy guard for fetchOrders. Distinct from ordersLoading because
    // background polls call fetchOrders({ silent: true }), which never sets
    // ordersLoading — so ordersLoading alone can't gate overlapping silent polls.
    _ordersInFlight: false,

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
    // Idempotency (lib/checkoutIdempotency, L14): a retry of the SAME cart reuses the key, so
    // the backend replays the existing order instead of double-charging the wallet. After an
    // attempt with an UNKNOWN outcome (no response / 5xx) the key is kept even if the cart was
    // edited — that attempt may have placed and charged an order. Only after definitive 4xx
    // rejections does an edited cart get a new key. Reset after a confirmed success.
    //
    // The returned data carries `replayed_previous_cart: true` when the server replayed an
    // order placed for an EARLIER version of the cart (a lost success, then an edit): that
    // order does not contain the later edits, and the caller must say so.
    async placeOrder(payload) {
      this.placing = true;
      this.placeError = null;
      this.placeFieldErrors = {};
      this.placedOrderNumber = null;
      const snapshot = checkoutSnapshot(payload);
      this._checkoutIdem = keyForCheckoutSnapshot(this._checkoutIdem, snapshot);
      const sameCart = isSameSnapshot(this._checkoutIdem, snapshot);
      try {
        const res = await api.post("/place-order/", {
          ...payload,
          idempotency_key: this._checkoutIdem.key,
        });
        this.placedOrderNumber = res.data.order_number;
        this._checkoutIdem = null;
        return {
          ...res.data,
          replayed_previous_cart: res.data?.idempotent_replay === true && !sameCart,
        };
      } catch (err) {
        this._checkoutIdem = afterFailedCheckout(this._checkoutIdem, err);
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
      // Re-entrancy guard (mirrors fetchHistory's historyLoading check): skip a
      // call while one is already in flight, so a slow earlier response can't
      // overwrite fresher state with stale data when polls overlap. Callers that
      // read the return value already fall back to store state when it isn't an
      // array, so returning the current orders here is safe.
      if (this._ordersInFlight) return this.orders;
      this._ordersInFlight = true;
      if (!silent) this.ordersLoading = true;
      // Was an error already surfaced before this fetch cleared it? Background
      // polls call fetchOrders({ silent: true }) every 15–60s; a transient blip
      // must NOT paint the error banner over a still-correct live list. Capture
      // this so a silent poll only re-surfaces the error if one was already
      // showing (mirrors stores/waiter.js).
      const hadPriorError = this.ordersError !== null;
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
        // Surface on any non-silent load, and on a silent poll only when an error
        // was already showing or there is nothing good to display (orders empty).
        // A silent blip while orders are populated stays quiet so the live board
        // never flickers to a false error banner.
        if (!silent || hadPriorError || this.orders.length === 0) {
          this.ordersError = err?.response?.data?.detail || "Failed to load orders.";
        }
      } finally {
        this._ordersInFlight = false;
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
