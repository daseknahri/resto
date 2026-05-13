import { defineStore } from "pinia";
import api from "../lib/api";

export const useOrderStore = defineStore("order", {
  state: () => ({
    // Last placed order (for customer status tracking)
    placedOrderNumber: null,
    placing: false,
    placeError: null,
    placeFieldErrors: {},

    // Owner order list
    orders: [],
    ordersLoading: false,
    ordersError: null,
    ordersStatusFilter: "",

    // Owner status update
    updatingOrderId: null,
  }),

  actions: {
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
    // Owner: fetch orders
    // -------------------------------------------------------
    async fetchOrders(statusFilter = "") {
      this.ordersLoading = true;
      this.ordersError = null;
      this.ordersStatusFilter = statusFilter;
      try {
        const params = statusFilter ? { status: statusFilter } : {};
        const res = await api.get("/owner/orders/", { params });
        this.orders = Array.isArray(res.data?.results) ? res.data.results : [];
        return this.orders;
      } catch (err) {
        this.ordersError = err?.response?.data?.detail || "Failed to load orders.";
      } finally {
        this.ordersLoading = false;
      }
    },

    // -------------------------------------------------------
    // Owner: update order status
    // -------------------------------------------------------
    async updateOrderStatus(orderId, payload) {
      this.updatingOrderId = orderId;
      try {
        const res = await api.patch(`/owner/orders/${orderId}/status/`, payload);
        const updated = res.data;
        const idx = this.orders.findIndex((o) => o.id === orderId);
        if (idx !== -1) {
          this.orders[idx] = { ...this.orders[idx], ...updated };
        }
        return updated;
      } catch (err) {
        throw err;
      } finally {
        this.updatingOrderId = null;
      }
    },
  },
});
