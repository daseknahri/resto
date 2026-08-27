import { describe, it, expect } from "vitest";

// Pure mirror of the `showEta` gate in OrderStatus.vue. The backend returns
// `estimated_ready_minutes` on EVERY order regardless of status, so the "Estimated
// ready in X min" ETA/countdown sub-block must be gated to the pre-ready lifecycle.
// Without the gate, a completed / out-for-delivery order showed a permanent stale
// ETA (the live countdown nulls out on those statuses and the static fallback then
// rendered the raw backend minutes). This locks the pre-ready allowlist and mirrors
// MarketplaceOrderStatus.vue's status gate.
const PRE_READY = ["pending", "confirmed", "preparing"];
function showEta(o) {
  return !!o?.estimated_ready_minutes && PRE_READY.includes(o?.status);
}

describe("order-status ETA visibility gate", () => {
  it("shows the ETA for the pre-ready statuses", () => {
    for (const status of PRE_READY) {
      expect(showEta({ estimated_ready_minutes: 20, status })).toBe(true);
    }
  });

  it("hides the ETA once the order is ready / out for delivery / done — even though the backend still returns the minutes", () => {
    for (const status of ["ready", "out_for_delivery", "completed", "cancelled", "scheduled"]) {
      expect(showEta({ estimated_ready_minutes: 20, status })).toBe(false);
    }
  });

  it("hides the ETA when the backend omits estimated_ready_minutes", () => {
    expect(showEta({ status: "preparing" })).toBe(false);
    expect(showEta({ estimated_ready_minutes: 0, status: "preparing" })).toBe(false);
  });

  it("is safe on a null/empty order payload", () => {
    expect(showEta(null)).toBe(false);
    expect(showEta({})).toBe(false);
  });
});
