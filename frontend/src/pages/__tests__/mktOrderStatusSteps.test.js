import { describe, it, expect } from "vitest";

// Pure mirror of MarketplaceOrderStatus.vue's fulfillment-aware stepper (same
// convention as checkoutEta.test.js). Locks the contract that pickup / dine-in
// orders never surface the delivery-only "out_for_delivery" step — and therefore
// get correct step counts and progress %. Regression guard for the bug where a
// fixed 6-step array showed a phantom "out for delivery" to pickup customers and
// skewed their progress bar (a ready-for-pickup order read 4/6 = 67%).
function buildStatusSteps(fulfillmentType) {
  const steps = ["pending", "confirmed", "preparing", "ready"];
  if (fulfillmentType === "delivery") steps.push("out_for_delivery");
  steps.push("completed");
  return steps;
}

function progressPercent(steps, status) {
  const idx = steps.indexOf(status);
  if (idx < 0) return 0;
  return Math.round(((idx + 1) / steps.length) * 100);
}

describe("marketplace order-status stepper (fulfillment-aware)", () => {
  it("delivery orders include out_for_delivery (6 steps)", () => {
    expect(buildStatusSteps("delivery")).toEqual([
      "pending", "confirmed", "preparing", "ready", "out_for_delivery", "completed",
    ]);
  });

  it("pickup orders omit out_for_delivery (5 steps)", () => {
    const steps = buildStatusSteps("pickup");
    expect(steps).not.toContain("out_for_delivery");
    expect(steps).toEqual(["pending", "confirmed", "preparing", "ready", "completed"]);
  });

  it("an unknown / absent fulfillment type defaults to the non-delivery flow", () => {
    expect(buildStatusSteps(undefined)).not.toContain("out_for_delivery");
  });

  it("a ready pickup order reads 4/5 = 80% (was 4/6 = 67% with the phantom step)", () => {
    expect(progressPercent(buildStatusSteps("pickup"), "ready")).toBe(80);
  });

  it("a completed pickup order reads 100% (no dangling delivery step ahead)", () => {
    expect(progressPercent(buildStatusSteps("pickup"), "completed")).toBe(100);
  });

  it("a delivery order out_for_delivery reads 5/6 = 83%", () => {
    expect(progressPercent(buildStatusSteps("delivery"), "out_for_delivery")).toBe(83);
  });

  it("a cancelled / unknown status reads 0%", () => {
    expect(progressPercent(buildStatusSteps("delivery"), "cancelled")).toBe(0);
  });
});
