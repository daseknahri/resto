/**
 * Unit tests for useWaiterStore
 *
 * Covers: fetchOrders, advanceStatus (optimistic update, revert on failure,
 * offline queue), flushQueue (success, transient retry, permanent-drop, 409
 * conflict-refetch), localStorage persistence, and connectivity helpers.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useWaiterStore } from "../waiter";

// ── api mock ──────────────────────────────────────────────────────────────────
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
  },
}));
import api from "../../lib/api";

// ── idempotency mock ──────────────────────────────────────────────────────────
vi.mock("../../lib/idempotency", () => ({
  newIdempotencyKey: vi.fn(() => "test-idem-key-" + Math.random().toString(36).slice(2)),
}));

// ── localStorage mock ─────────────────────────────────────────────────────────
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: vi.fn((key) => store[key] ?? null),
    setItem: vi.fn((key, value) => { store[key] = String(value); }),
    removeItem: vi.fn((key) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
    _getStore: () => store,
  };
})();
Object.defineProperty(globalThis, "localStorage", { value: localStorageMock, writable: true });

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
    localStorageMock.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
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

  it("advanceStatus sends idempotency_key in the PATCH body", async () => {
    api.get.mockResolvedValueOnce({ data: { results: [makeOrder(1, "pending")], count: 1 } });
    api.patch.mockResolvedValueOnce({ data: {} });

    const store = useWaiterStore();
    await store.fetchOrders();
    await store.advanceStatus(1);

    expect(api.patch).toHaveBeenCalledWith(
      "/owner/orders/1/status/",
      expect.objectContaining({ status: "confirmed", idempotency_key: expect.any(String) })
    );
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
    expect(store.offlineQueue[0].idempotency_key).toEqual(expect.any(String));
  });

  it("advanceStatus removes completed order from list on success", async () => {
    // Pickup order: ready → completed (picked up) removes it from the active list.
    api.get.mockResolvedValueOnce({ data: { results: [{ ...makeOrder(1, "ready"), fulfillment_type: "pickup" }], count: 1 } });
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

  it("_enqueue deduplicates by orderId (newest wins, reuses idempotency key)", () => {
    const store = useWaiterStore();
    store._enqueue(1, "confirmed");
    const firstKey = store.offlineQueue[0].idempotency_key;

    store._enqueue(1, "preparing"); // override status for same order

    expect(store.offlineQueue).toHaveLength(1);
    expect(store.offlineQueue[0].newStatus).toBe("preparing");
    // The idempotency key is preserved from the first enqueue for the same order
    expect(store.offlineQueue[0].idempotency_key).toBe(firstKey);
  });

  // ── localStorage persistence ───────────────────────────────────────────────

  it("_enqueue persists queue to localStorage", () => {
    const store = useWaiterStore();
    store._enqueue(1, "confirmed");

    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      "kepoli.waiterQueue.v1",
      expect.stringContaining('"orderId":1')
    );
  });

  it("queue is rehydrated from localStorage on store init", () => {
    // Pre-populate localStorage with a serialized queue entry
    const savedQueue = [{ orderId: 42, newStatus: "confirmed", queuedAt: Date.now(), idempotency_key: "saved-key" }];
    localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(savedQueue));

    // Re-create the store (new Pinia so state() runs fresh)
    setActivePinia(createPinia());
    const store = useWaiterStore();

    expect(store.offlineQueue).toHaveLength(1);
    expect(store.offlineQueue[0].orderId).toBe(42);
    expect(store.offlineQueue[0].idempotency_key).toBe("saved-key");
  });

  it("queue rehydration is safe against corrupt JSON", () => {
    localStorageMock.getItem.mockReturnValueOnce("NOT_JSON{{{");
    setActivePinia(createPinia());
    const store = useWaiterStore();
    expect(store.offlineQueue).toHaveLength(0);
  });

  it("queue cap: drops oldest entries when exceeding QUEUE_MAX_SIZE", () => {
    const store = useWaiterStore();
    // Enqueue 52 distinct order IDs (cap is 50)
    for (let i = 1; i <= 52; i++) {
      // Directly manipulate to bypass dedup logic for different orderIds
      store.offlineQueue.push({ orderId: i, newStatus: "confirmed", queuedAt: Date.now(), idempotency_key: `key-${i}` });
    }
    // Now call _persistQueue via _enqueue for orderId 100 (triggering cap check)
    store._enqueue(100, "preparing");
    // Queue should be trimmed to 50
    expect(store.offlineQueue.length).toBeLessThanOrEqual(50);
  });

  // ── flushQueue ─────────────────────────────────────────────────────────────

  it("flushQueue sends queued updates with idempotency_key and clears the queue", async () => {
    api.patch.mockResolvedValue({ data: {} });

    const store = useWaiterStore();
    store.orders = [makeOrder(1, "pending")];
    store._enqueue(1, "confirmed");
    const savedKey = store.offlineQueue[0].idempotency_key;

    await store.flushQueue();

    expect(api.patch).toHaveBeenCalledWith(
      "/owner/orders/1/status/",
      { status: "confirmed", idempotency_key: savedKey }
    );
    expect(store.offlineQueue).toHaveLength(0);
  });

  it("flushQueue re-queues entries on transient errors (5xx)", async () => {
    vi.useFakeTimers();
    const err = Object.assign(new Error("503"), { response: { status: 503 } });
    api.patch.mockRejectedValueOnce(err);

    const store = useWaiterStore();
    store.orders = [makeOrder(1, "pending")];
    store._enqueue(1, "confirmed");

    await store.flushQueue();

    expect(store.offlineQueue).toHaveLength(1); // re-queued for retry
  });

  it("flushQueue permanently drops entry on 400 and calls onPermError", async () => {
    const err = Object.assign(new Error("400"), { response: { status: 400 } });
    api.patch.mockRejectedValueOnce(err);

    const onPermError = vi.fn();
    const store = useWaiterStore();
    store.orders = [makeOrder(1, "pending")];
    store._enqueue(1, "confirmed");

    await store.flushQueue({ onPermError });

    expect(store.offlineQueue).toHaveLength(0); // dropped, not re-queued
    expect(onPermError).toHaveBeenCalledOnce();
  });

  it("flushQueue permanently drops entry on 409, calls onPermError, and refetches orders", async () => {
    const err = Object.assign(new Error("409 conflict"), { response: { status: 409 } });
    api.patch.mockRejectedValueOnce(err);
    api.get.mockResolvedValue({ data: { results: [], count: 0 } });

    const onPermError = vi.fn();
    const onConflict = vi.fn();
    const store = useWaiterStore();
    store.orders = [makeOrder(1, "pending")];
    store.isOnline = true;
    store._enqueue(1, "confirmed");

    await store.flushQueue({ onPermError, onConflict });

    // Should have refetched to self-heal (fetchOrders({ silent: true }) → GET /staff/orders/ with no params)
    expect(api.get).toHaveBeenCalledWith("/staff/orders/");
    expect(onConflict).toHaveBeenCalledOnce();
    expect(onPermError).toHaveBeenCalledOnce();
    expect(store.offlineQueue).toHaveLength(0);
  });

  it("flushQueue does nothing when queue is empty", async () => {
    const store = useWaiterStore();
    await store.flushQueue();
    expect(api.patch).not.toHaveBeenCalled();
  });

  it("flushQueue schedules exponential backoff retry on transient error", async () => {
    vi.useFakeTimers();
    const err = Object.assign(new Error("503"), { response: { status: 503 } });
    api.patch.mockRejectedValue(err);

    const store = useWaiterStore();
    store.isOnline = true;
    store.orders = [makeOrder(1, "pending")];
    store._enqueue(1, "confirmed");

    await store.flushQueue();

    // Should have scheduled a timer for retry
    expect(store._flushDelay).toBeGreaterThan(1000); // backoff doubled
    expect(store._flushTimer).not.toBeNull();
  });

  // ── markPaid ───────────────────────────────────────────────────────────────

  it("markPaid sends idempotency_key when provided", async () => {
    api.post.mockResolvedValueOnce({ data: { payment_status: "paid", completed: false } });

    const store = useWaiterStore();
    store.orders = [makeOrder(1, "confirmed")];
    await store.markPaid(1, "my-settle-key");

    expect(api.post).toHaveBeenCalledWith(
      "/owner/orders/1/mark-paid/",
      expect.objectContaining({ idempotency_key: "my-settle-key" })
    );
  });

  it("markPaid omits idempotency_key when not provided", async () => {
    api.post.mockResolvedValueOnce({ data: { payment_status: "paid", completed: false } });

    const store = useWaiterStore();
    store.orders = [makeOrder(1, "confirmed")];
    await store.markPaid(1); // no key

    // idempotency_key should NOT be in body
    expect(api.post).toHaveBeenCalledWith(
      "/owner/orders/1/mark-paid/",
      expect.not.objectContaining({ idempotency_key: expect.anything() })
    );
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

  it("nextStatus returns correct next status (fulfillment-aware)", () => {
    const store = useWaiterStore();
    expect(store.nextStatus({ status: "pending" })).toBe("confirmed");
    expect(store.nextStatus({ status: "confirmed" })).toBe("preparing");
    expect(store.nextStatus({ status: "preparing" })).toBe("ready");
    // Pickup: ready → completed (picked up)
    expect(store.nextStatus({ status: "ready", fulfillment_type: "pickup" })).toBe("completed");
    // Delivery: ready → out_for_delivery → completed
    expect(store.nextStatus({ status: "ready", fulfillment_type: "delivery" })).toBe("out_for_delivery");
    expect(store.nextStatus({ status: "out_for_delivery", fulfillment_type: "delivery" })).toBe("completed");
    // Dine-in unpaid: finished by Settle, not a plain advance
    expect(store.nextStatus({ status: "ready", fulfillment_type: "table" })).toBeNull();
    expect(store.nextStatus({ status: "completed" })).toBeNull();
  });

  it("queueLength reflects offlineQueue size", () => {
    const store = useWaiterStore();
    expect(store.queueLength).toBe(0);
    store._enqueue(1, "confirmed");
    expect(store.queueLength).toBe(1);
  });

  // ── setFlushCallbacks ──────────────────────────────────────────────────────

  it("setFlushCallbacks registers callbacks used during flush", async () => {
    const err = Object.assign(new Error("400"), { response: { status: 400 } });
    api.patch.mockRejectedValueOnce(err);

    const onPermError = vi.fn();
    const store = useWaiterStore();
    store.setFlushCallbacks({ onPermError });
    store.orders = [makeOrder(1, "pending")];
    store._enqueue(1, "confirmed");

    // Simulate coming online — should use registered callbacks
    store.isOnline = true;
    await store.flushQueue({ onPermError: store._flushCallbacks.onPermError });

    expect(onPermError).toHaveBeenCalledOnce();
  });

  // ── autoDirtyTableIfEmpty (Wave 4 — table-turn parity) ──────────────────────

  it("autoDirtyTableIfEmpty PATCHes the table dirty when no active orders remain", async () => {
    api.patch.mockResolvedValueOnce({ data: {} });
    const store = useWaiterStore();
    store.orders = []; // last order already removed by the settle path
    const order = makeOrder(1, "ready"); // fulfillment_type "table", table_label "Table 1"

    const dirtied = await store.autoDirtyTableIfEmpty(order, { tableId: 7, enabled: true });

    expect(dirtied).toBe(true);
    expect(api.patch).toHaveBeenCalledWith("/staff/tables/7/status/", { status: "dirty" });
  });

  it("autoDirtyTableIfEmpty does NOT fire when another active order remains on the table", async () => {
    const store = useWaiterStore();
    const settled = makeOrder(1, "ready");
    const stillOpen = { ...makeOrder(2, "preparing"), table_label: "Table 1" };
    store.orders = [stillOpen]; // same table_label still active

    const dirtied = await store.autoDirtyTableIfEmpty(settled, { tableId: 7, enabled: true });

    expect(dirtied).toBe(false);
    expect(api.patch).not.toHaveBeenCalled();
  });

  // DEFAULT-PRESERVING GUARD: with the table-state feature not in use (no
  // tableId) OR explicitly disabled, the settle flow is unchanged — no PATCH.
  it("autoDirtyTableIfEmpty is a no-op without a tableId (table-state feature not in use)", async () => {
    const store = useWaiterStore();
    store.orders = [];
    const dirtied = await store.autoDirtyTableIfEmpty(makeOrder(1, "ready"), { tableId: null, enabled: true });
    expect(dirtied).toBe(false);
    expect(api.patch).not.toHaveBeenCalled();
  });

  it("autoDirtyTableIfEmpty is a no-op when disabled (enabled: false preserves behavior)", async () => {
    const store = useWaiterStore();
    store.orders = [];
    const dirtied = await store.autoDirtyTableIfEmpty(makeOrder(1, "ready"), { tableId: 7, enabled: false });
    expect(dirtied).toBe(false);
    expect(api.patch).not.toHaveBeenCalled();
  });

  it("autoDirtyTableIfEmpty ignores non-table (pickup/delivery) orders", async () => {
    const store = useWaiterStore();
    store.orders = [];
    const pickup = { ...makeOrder(1, "ready"), fulfillment_type: "pickup", table_label: null };
    const dirtied = await store.autoDirtyTableIfEmpty(pickup, { tableId: 7, enabled: true });
    expect(dirtied).toBe(false);
    expect(api.patch).not.toHaveBeenCalled();
  });

  it("autoDirtyTableIfEmpty swallows a failed PATCH and returns false (never breaks settle)", async () => {
    api.patch.mockRejectedValueOnce(new Error("500"));
    const store = useWaiterStore();
    store.orders = [];
    const dirtied = await store.autoDirtyTableIfEmpty(makeOrder(1, "ready"), { tableId: 7, enabled: true });
    expect(dirtied).toBe(false);
  });
});
