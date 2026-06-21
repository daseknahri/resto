/**
 * Unit tests for useCustomerActivity — the shared activity aggregator behind the
 * super-app resume rail + usage-sorted grid.
 *
 * Verifies:
 *   - each source is fetched and mapped into the right shape
 *   - topVerticals is sorted by last_activity desc and drops no-activity verticals
 *   - lastOrder prefers an active order, falling back to most-recent history
 *   - hasResumable reflects active items
 *   - load() is idempotent and a single source failing never breaks the others
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("../../lib/api", () => ({
  default: { get: vi.fn() },
}));

import api from "../../lib/api";
import { useCustomerActivity } from "../useCustomerActivity";

function routeGet(map) {
  api.get.mockImplementation((url) => {
    for (const [frag, val] of Object.entries(map)) {
      if (url.includes(frag)) {
        return typeof val === "function" ? val() : Promise.resolve(val);
      }
    }
    return Promise.resolve({ data: {} });
  });
}

describe("useCustomerActivity", () => {
  beforeEach(() => {
    api.get.mockReset();
  });

  it("aggregates active items, services, and history into shape", async () => {
    routeGet({
      "/customer/services/": {
        data: {
          services: {
            food: { count: 3, last_activity: "2026-06-10T00:00:00Z", enabled: true },
            rides: { count: 1, last_activity: "2026-06-15T00:00:00Z", enabled: true },
            shops: { count: 0, last_activity: null, enabled: true },
          },
        },
      },
      "/customer/active/": {
        data: {
          orders: [{ order_number: "A1", status: "preparing", restaurant_slug: "x" }],
          ride: { id: 5, status: "accepted", dropoff_address: "Dest" },
          package: null,
        },
      },
      "/rides/history/": { data: [{ id: 9, status: "completed" }] },
      "/customer/orders/": { data: { orders: [{ order_number: "H1", status: "completed" }] } },
    });

    const a = useCustomerActivity();
    await a.load();

    // services -> topVerticals sorted by last_activity desc, no-activity dropped
    expect(a.topVerticals.value).toEqual(["rides", "food"]);
    // active items mapped
    expect(a.activeItems.value.orders).toHaveLength(1);
    expect(a.activeItems.value.ride.status).toBe("accepted");
    expect(a.hasResumable.value).toBe(true);
    // lastOrder prefers the active order over history
    expect(a.lastOrder.value.order_number).toBe("A1");
    // lastRide from history endpoint
    expect(a.lastRide.value.id).toBe(9);
  });

  it("lastOrder falls back to recent history when nothing active", async () => {
    routeGet({
      "/customer/services/": { data: { services: {} } },
      "/customer/active/": { data: { orders: [], ride: null, package: null } },
      "/rides/history/": { data: [] },
      "/customer/orders/": { data: { orders: [{ order_number: "H7", status: "completed" }] } },
    });

    const a = useCustomerActivity();
    await a.load();

    expect(a.hasResumable.value).toBe(false);
    expect(a.lastOrder.value.order_number).toBe("H7");
  });

  it("a failing source does not break the others", async () => {
    routeGet({
      "/customer/services/": () => Promise.reject(new Error("boom")),
      "/customer/active/": {
        data: { orders: [], ride: { id: 2, status: "searching" }, package: null },
      },
      "/rides/history/": () => Promise.reject(new Error("boom")),
      "/customer/orders/": () => Promise.reject(new Error("boom")),
    });

    const a = useCustomerActivity();
    await a.load();

    expect(a.serviceActivity.value).toEqual({});
    expect(a.activeItems.value.ride.id).toBe(2);
    expect(a.hasResumable.value).toBe(true);
  });

  it("load() is idempotent unless forced", async () => {
    routeGet({
      "/customer/services/": { data: { services: {} } },
      "/customer/active/": { data: { orders: [], ride: null, package: null } },
      "/rides/history/": { data: [] },
      "/customer/orders/": { data: { orders: [] } },
    });

    const a = useCustomerActivity();
    await a.load();
    const callsAfterFirst = api.get.mock.calls.length;
    await a.load();
    expect(api.get.mock.calls.length).toBe(callsAfterFirst);
    await a.load({ force: true });
    expect(api.get.mock.calls.length).toBeGreaterThan(callsAfterFirst);
  });
});
