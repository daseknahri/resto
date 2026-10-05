/**
 * Unit tests for useOrderStore — focused on the fetchOrders re-entrancy guard.
 *
 * Owner/waiter order lists hot-poll fetchOrders({ silent: true }) in the
 * background. Without a guard, a slow earlier response could resolve AFTER a
 * newer one and overwrite fresh state with stale data. fetchOrders now skips a
 * call while one is already in flight (mirroring fetchHistory's historyLoading
 * check), using a dedicated _ordersInFlight flag because silent polls never set
 * ordersLoading.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useOrderStore } from "../order";

vi.mock("../../lib/api", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}));
import api from "../../lib/api";

vi.mock("../../lib/idempotency", () => ({
  newIdempotencyKey: vi.fn(() => "test-idem-key"),
}));
import { newIdempotencyKey } from "../../lib/idempotency";

const deferred = () => {
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
};

describe("useOrderStore.fetchOrders re-entrancy guard", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("skips a second call while the first is still in flight (no duplicate request)", async () => {
    const first = deferred();
    api.get.mockReturnValueOnce(first.promise);

    const store = useOrderStore();
    const p1 = store.fetchOrders("", { silent: true });   // in flight, not awaited
    const r2 = await store.fetchOrders("", { silent: true }); // must skip

    expect(api.get).toHaveBeenCalledTimes(1); // second call never hit the network
    expect(r2).toBe(store.orders);            // skipped call returns current state

    first.resolve({ data: { results: [{ id: 1, status: "pending" }] } });
    await p1;

    expect(store.orders).toEqual([{ id: 1, status: "pending" }]);
  });

  it("clears the in-flight flag so a later call proceeds", async () => {
    api.get.mockResolvedValueOnce({ data: { results: [{ id: 1 }] } });
    const store = useOrderStore();
    await store.fetchOrders();
    expect(store._ordersInFlight).toBe(false);

    api.get.mockResolvedValueOnce({ data: { results: [{ id: 2 }] } });
    await store.fetchOrders();
    expect(api.get).toHaveBeenCalledTimes(2);
    expect(store.orders).toEqual([{ id: 2 }]);
  });

  it("clears the in-flight flag even when the request fails", async () => {
    api.get.mockRejectedValueOnce(new Error("Network error"));
    const store = useOrderStore();
    await store.fetchOrders();
    expect(store._ordersInFlight).toBe(false);
    expect(store.ordersError).toBeTruthy();
  });
});

// L14: the checkout idempotency key identifies ONE cart snapshot.
describe("useOrderStore.placeOrder idempotency key", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    let n = 0;
    newIdempotencyKey.mockImplementation(() => `key-${++n}`);
  });

  const cartPayload = (qty = 1) => ({ items: [{ slug: "burger", qty }], fulfillment_type: "pickup", use_wallet: true });
  const sentKey = (call) => api.post.mock.calls[call][1].idempotency_key;
  const lostResponse = () => api.post.mockRejectedValueOnce(new Error("Network Error"));

  it("retries the SAME cart with the same key (server replays, no double charge)", async () => {
    const store = useOrderStore();
    lostResponse();
    await expect(store.placeOrder(cartPayload())).rejects.toThrow();
    api.post.mockResolvedValueOnce({ data: { order_number: "ORD-1", idempotent_replay: true } });
    const result = await store.placeOrder(cartPayload());

    expect(sentKey(1)).toBe(sentKey(0));
    // The replay flag is handed to the caller so it can say the order had already gone through.
    expect(result.idempotent_replay).toBe(true);
  });

  it("an edited cart after a failed / unknown attempt gets a NEW key", async () => {
    const store = useOrderStore();
    lostResponse();
    await expect(store.placeOrder(cartPayload(1))).rejects.toThrow();
    api.post.mockResolvedValueOnce({ data: { order_number: "ORD-2" } });
    await store.placeOrder(cartPayload(2));

    expect(sentKey(1)).not.toBe(sentKey(0));
  });

  it("mints a fresh key for the next order after a confirmed success", async () => {
    const store = useOrderStore();
    api.post.mockResolvedValueOnce({ data: { order_number: "ORD-1" } });
    await store.placeOrder(cartPayload());
    api.post.mockResolvedValueOnce({ data: { order_number: "ORD-2" } });
    await store.placeOrder(cartPayload());

    expect(sentKey(1)).not.toBe(sentKey(0));
    expect(store._checkoutIdem).toBeNull();
  });
});
