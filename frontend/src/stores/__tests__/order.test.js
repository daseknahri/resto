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
