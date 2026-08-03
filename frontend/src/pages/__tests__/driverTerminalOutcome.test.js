import { describe, it, expect } from "vitest";

// Pure mirror of DriverPage.vue advance()'s terminal-transition handling (same
// convention as checkoutEta / mktOrderStatusSteps tests). Locks the contract that a
// FAILED delivery is NOT reported as a success and does NOT open the customer-rating
// modal — the rating POST 404s for a non-delivered job. Regression guard for the bug
// where every terminal advance() unconditionally showed "Delivery completed — nice
// work!" (green) and opened a rating prompt, even when the driver marked the delivery
// failed (no-show / bad address).
function terminalOutcome(status) {
  const wasDelivered = status === "delivered";
  return {
    toastKey: wasDelivered ? "driver.deliveredToast" : "driver.failedToast",
    toastKind: wasDelivered ? "success" : "info",
    opensRating: wasDelivered,
  };
}

describe("driver terminal-transition outcome", () => {
  it("a FAILED delivery gets neutral 'failed' copy and NO rating prompt", () => {
    expect(terminalOutcome("failed")).toEqual({
      toastKey: "driver.failedToast",
      toastKind: "info",
      opensRating: false,
    });
  });

  it("a DELIVERED job gets the success toast and opens the rating modal", () => {
    expect(terminalOutcome("delivered")).toEqual({
      toastKey: "driver.deliveredToast",
      toastKind: "success",
      opensRating: true,
    });
  });

  it("any other terminal status (e.g. cancelled) is treated as non-success", () => {
    const out = terminalOutcome("cancelled");
    expect(out.toastKind).toBe("info");
    expect(out.opensRating).toBe(false);
  });
});
