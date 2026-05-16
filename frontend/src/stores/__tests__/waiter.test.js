/**
 * Unit tests for useWaiterStore
 *
 * Covers: fetchOrders, advanceStatus (optimistic update, revert on failure,
 * offline queue), flushQueue, and connectivity helpers.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useWaiterStore } from "../waiter";

// ── api mock ──────────────────────────────────────────────────────────────────
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn(),
  },
}));
import api from "../../lib/api";

// ── helpers ───────────────────────────────────────────────────────────────────
const makeOrder = (id, status = "pending") => ({
  id,
  order_number: `ORD00${id}`,
  status,
  fulfillment_type: "table",
  table_label: `Table ${id}`,
  items: [],
  total: "10.00",
  currency: "MAD",
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
});

// ── tests ─────────────────────────────────────────────────────────────────────
describe("useWaiterStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  // ── fetchOrders ─────────────────────────────────────────────────────────────

  it("fetchOrders populates orders from results", async () => {
    const orders = [makeOrder(1), makeOrder(2, "confirmed")];
    api.get.mockResolvedValueOnce({ data: { results: orders, count: 2 } });

    const store = useWaiterStore();
    await store.fetchOrders();

    expect(store.orders).toHaveLength(2);
    expect(store.orders[0].order_number).toBe("ORD001");
  });

  it("fetchOrders sets loading to false after success", async () => {
    api.get.mockResolvedValueOnce({ data: { results: [], count: 0 } });
    const store = useWaiterStore();
    await store.fetchOrders();
    expect(store.loading).toBe(false);
  });

  it("fetchOrders sets error on failure (non-silent)", async () => {
    api.get.mockRejectedValueOnce(new Error("Network error"));
    const store = useWaiterStore();
    await store.fetchOrders();
    expect(store.error).toBeTruthy();
    expect(store.loading).toBe(false);
  });

  it("fetchOrders silent mode does not set error on failure", async () => {
    api.get.mockRejectedValueOnce(new Error("Network error"));
    const store = useWaiterStore();
    await store.fetchOrders({ silent: true });
    expect(store.error).toBeNull();
  });

  // ── advanceStatus — optimistic ─────────────────────────────────────────────

  it("advanceStatus immediately changes status optimistically", async () => {
    api.get.mockResolvedValueOnce({ data: { results: [makeOrder(1, "pending")], count: 1 } });
    api.patch.mockResolvedValueOnce({ data: {} });

    const store = useWaiterStore();
    await store.fetchOrders();

    // Don't await — just kick it off and check immediate state
    const promise = store.advanceStatus(1);
    expect(store.orders[0].status).toBe("confirmed"); // optimistic
    await promise;
    expect(store.orders[0].status).toBe("confirmed"); // still confirmed after success
  });

  it("advanceStatus reverts status on API failure", async () => {
    api.get.mockResolvedValueOnce({ data: { results: [makeOrder(1, "pending")], count: 1 } });
    api.patch.mockRejectedValueOnce(new Error("500"));

    const store = useWaiterStore();
    await store.fetchOrders();
    await store.advanceStatus(1);

    expect(store.orders[0].status).toBe("pending"); // reverted
  });

  it("advanceStatus queues entry on API failure", async () => {
    api.get.mockResolvedValueOnce({ data: { results: [makeOrder(1, "pending")], count: 1 } });
    api.patch.mockRejectedValueOnce(new Error("500"));

    const store = useWaiterStore();
    await store.fetchOrders();
    await store.advanceStatus(1);

    expect(store.offlineQueue).toHaveLength(1);
    expect(store.offlineQueue[0].orderId).toBe(1);
    expect(store.offlineQueue[0].newStatus).toBe("confirmed");
  });

  it("advanceStatus removes completed order from list on success", async () => {
    api.get.mockResolvedValueOnce({ data: { results: [makeOrder(1, "ready")], count: 1 } });
    api.patch.mockResolvedValueOnce({ data: {} });

    const store = useWaiterStore();
    await store.fetchOrders();
    await store.advanceStatus(1);

    expect(store.orders).toHaveLength(0); // completed → removed
  });

  it("advanceStatus is a no-op for unknown order id", async () => {
    api.get.mockResolvedValueOnce({ data: { results: [makeOrder(1)], count: 1 } });
    const store = useWaiterStore();
    await store.fetchOrders();
    await store.advanceStatus(999); // no-op
    expect(api.patch).not.toHaveBeenCalled();
  });

  // ── offline queue ──────────────────────────────────────────────────────────

  it("advanceStatus enqueues when offline", async () => {
    api.get.mockResolvedValueOnce({ data: { results: [makeOrder(1, "pending")], count: 1 } });

    const store = useWaiterStore();
    await store.fetchOrders();
    store.isOnline = false;

    await store.advanceStatus(1);

    expect(api.patch).not.toHaveBeenCalled();
    expect(store.offlineQueue).toHaveLength(1);
    // Status should still be optimistically updated even offline
    expect(store.orders[0].status).toBe("confirmed");
  });

  it("_enqueue deduplicates by orderId (newest wins)", () => {
    const store = useWaiterStore();
    store._enqueue(1, "confirmed");
    store._enqueue(1, "preparing"); // override

    expect(store.offlineQueue).toHaveLength(1);
    expect(store.offlineQueue[0].newStatus).toBe("preparing");
  });

  // ── flushQueue ─────────────────────────────────────────────────────────────

  it("flushQueue sends queued updates and clears the queue", async () => {
    api.patch.mockResolvedValue({ data: {} });

    const store = useWaiterStore();
    store.orders = [makeOrder(1, "pending")];
    store._enqueue(1, "confirmed");

    await store.flushQueue();

    expect(api.patch).toHaveBeenCalledWith("/owner/orders/1/status/", { status: "confirmed" });
    expect(store.offlineQueue).toHaveLength(0);
  });

  it("flushQueue re-queues entries that fail", async () => {
    api.patch.mockRejectedValueOnce(new Error("offline"));

    const store = useWaiterStore();
    store.orders = [makeOrder(1, "pending")];
    store._enqueue(1, "confirmed");

    await store.flushQueue();

    expect(store.offlineQueue).toHaveLength(1); // re-queued
  });

  it("flushQueue does nothing when queue is empty", async () => {
    const store = useWaiterStore();
    await store.flushQueue();
    expect(api.patch).not.toHaveBeenCalled();
  });

  // ── getters ────────────────────────────────────────────────────────────────

  it("pendingCount returns number of pending orders", async () => {
    api.get.mockResolvedValueOnce({
      data: {
        results: [makeOrder(1, "pending"), makeOrder(2, "pending"), makeOrder(3, "confirmed")],
        count: 3,
      },
    });
    const store = useWaiterStore();
    await store.fetchOrders();
    expect(store.pendingCount).toBe(2);
  });

  it("byStatus groups orders by status", async () => {
    api.get.mockResolvedValueOnce({
      data: {
        results: [makeOrder(1, "pending"), makeOrder(2, "ready"), makeOrder(3, "pending")],
        count: 3,
      },
    });
    const store = useWaiterStore();
    await store.fetchOrders();
    expect(store.byStatus.pending).toHaveLength(2);
    expect(store.byStatus.ready).toHaveLength(1);
    expect(store.byStatus.confirmed).toHaveLength(0);
  });

  it("nextStatus returns correct next status", () => {
    const store = useWaiterStore();
    expect(store.nextStatus("pending")).toBe("confirmed");
    expect(store.nextStatus("confirmed")).toBe("preparing");
    expect(store.nextStatus("preparing")).toBe("ready");
    expect(store.nextStatus("ready")).toBe("completed");
    expect(store.nextStatus("completed")).toBeNull();
  });

  it("queueLength reflects offlineQueue size", () => {
    const store = useWaiterStore();
    expect(store.queueLength).toBe(0);
    store._enqueue(1, "confirmed");
    expect(store.queueLength).toBe(1);
  });
});
