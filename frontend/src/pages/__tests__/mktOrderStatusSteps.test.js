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

// ── C-01: scheduled orders get a leading "scheduled" step ────────────────────
// Mirror of the FIXED MarketplaceOrderStatus.vue stepper: the step is prepended
// when the order is scheduled OR carries a scheduled_for (it was scheduled, even
// after it moves on), so a scheduled order matches a step and progress is > 0.
// (The base mirror above cannot express this — it has no order — so the fixed
// logic is mirrored here without touching the base.)
function buildStatusStepsFixed(fulfillmentType, order) {
  const steps = [];
  if (order?.status === "scheduled" || order?.scheduled_for) steps.push("scheduled");
  steps.push("pending", "confirmed", "preparing", "ready");
  if (fulfillmentType === "delivery") steps.push("out_for_delivery");
  steps.push("completed");
  return steps;
}

describe("marketplace order-status stepper — scheduled orders (C-01)", () => {
  it("a scheduled pickup order starts with a 'scheduled' step (6 steps)", () => {
    expect(
      buildStatusStepsFixed("pickup", { status: "scheduled", scheduled_for: "2026-11-17T12:00:00Z" }),
    ).toEqual(["scheduled", "pending", "confirmed", "preparing", "ready", "completed"]);
  });

  it("a scheduled delivery order starts with a 'scheduled' step (7 steps)", () => {
    expect(
      buildStatusStepsFixed("delivery", { status: "scheduled", scheduled_for: "2026-11-17T12:00:00Z" }),
    ).toEqual(["scheduled", "pending", "confirmed", "preparing", "ready", "out_for_delivery", "completed"]);
  });

  it("a scheduled pickup order reads 1/6 = 17%, not 0% (was -1 → 0% with no step)", () => {
    const steps = buildStatusStepsFixed("pickup", { status: "scheduled", scheduled_for: "2026-11-17T12:00:00Z" });
    expect(progressPercent(steps, "scheduled")).toBe(17);
  });

  it("a scheduled delivery order reads 1/7 = 14%", () => {
    const steps = buildStatusStepsFixed("delivery", { status: "scheduled", scheduled_for: "2026-11-17T12:00:00Z" });
    expect(progressPercent(steps, "scheduled")).toBe(14);
  });

  it("a scheduled_for order that moved on keeps 'scheduled' as a completed first step", () => {
    const steps = buildStatusStepsFixed("pickup", { status: "confirmed", scheduled_for: "2026-11-17T12:00:00Z" });
    expect(steps[0]).toBe("scheduled");
    // confirmed is index 2 of 6 steps (scheduled, pending, confirmed, ...) -> 3/6 = 50%
    expect(progressPercent(steps, "confirmed")).toBe(50);
  });

  it("a non-scheduled order is unchanged (no 'scheduled' step, same progress as before)", () => {
    expect(buildStatusStepsFixed("pickup", { status: "pending" })).toEqual([
      "pending", "confirmed", "preparing", "ready", "completed",
    ]);
    expect(progressPercent(buildStatusStepsFixed("pickup", { status: "pending" }), "pending")).toBe(20);
  });
});
