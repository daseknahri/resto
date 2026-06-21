import { describe, it, expect } from "vitest";

// Pure mirror of the optional courier-tip gating logic in SendPackagePage.vue's
// completed-state tip card (canTip + resolvedTipAmount computeds). Locks the
// contract: the tip card only shows for a completed trip that HAS a courier and
// has NOT been tipped (tip_amount comes back as a string, "0.00" until paid), and
// resolves a preset or custom selection into a positive number (else 0 → disabled).
// Default-off invariant: an untipped completed ride (tip_amount "0.00") still
// offers the card; a non-empty tip hides it — existing senders see no change
// unless they opt in by tipping.

function canTip(pkg) {
  if (!pkg || pkg.status !== "completed") return false;
  if (!pkg.driver) return false;
  return Number(pkg.tip_amount || 0) <= 0;
}

function resolvedTipAmount(selection, customAmount) {
  if (selection === "custom") {
    const n = Number(customAmount);
    return Number.isFinite(n) && n > 0 ? n : 0;
  }
  const n = Number(selection);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

const driver = { name: "Courier" };

describe("courier tip — canTip gating", () => {
  it("offers a tip on a completed trip with a courier and no prior tip (default-off)", () => {
    expect(canTip({ status: "completed", driver, tip_amount: "0.00" })).toBe(true);
  });

  it("hides the tip card once a tip has been paid (tip-once)", () => {
    expect(canTip({ status: "completed", driver, tip_amount: "10.00" })).toBe(false);
  });

  it("does not offer a tip before the trip is completed", () => {
    expect(canTip({ status: "in_progress", driver, tip_amount: "0.00" })).toBe(false);
  });

  it("does not offer a tip when no courier was assigned", () => {
    expect(canTip({ status: "completed", driver: null, tip_amount: "0.00" })).toBe(false);
  });

  it("is false for a missing/null package", () => {
    expect(canTip(null)).toBe(false);
  });
});

describe("courier tip — resolvedTipAmount", () => {
  it("resolves a positive preset", () => {
    expect(resolvedTipAmount(10, "")).toBe(10);
  });

  it("resolves a positive custom amount", () => {
    expect(resolvedTipAmount("custom", "7.5")).toBe(7.5);
  });

  it("returns 0 for a non-positive custom amount (button disabled)", () => {
    expect(resolvedTipAmount("custom", "0")).toBe(0);
    expect(resolvedTipAmount("custom", "-5")).toBe(0);
    expect(resolvedTipAmount("custom", "")).toBe(0);
  });

  it("returns 0 when nothing is selected", () => {
    expect(resolvedTipAmount(null, "")).toBe(0);
  });

  it("returns 0 for a non-numeric custom amount", () => {
    expect(resolvedTipAmount("custom", "abc")).toBe(0);
  });
});
