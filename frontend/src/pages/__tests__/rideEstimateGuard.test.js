import { describe, it, expect } from "vitest";

// Pure mirror of RidePage.vue's estimate-readiness logic (canEstimate +
// estimateBlocked + estimateBlockedMsg computeds). Locks OWNER-DECISION #1: a
// typed pickup/drop-off never geocodes, so the auto-estimate watcher — which
// needs BOTH lat/lng — can never fire. Before the fix that left the CTA disabled
// behind a permanent "Calculating…". These functions encode the dead-end
// detection that now surfaces an actionable pin prompt instead.

// canEstimate: the user has entered *something* for each end (a pinned coord OR
// typed address text).
function canEstimate({ pickupLatLng, pickupAddress, dropoffLatLng, dropoffAddress }) {
  return Boolean(
    (pickupLatLng || (pickupAddress || "").trim()) &&
      (dropoffLatLng || (dropoffAddress || "").trim()),
  );
}

// estimateBlocked: wants a fare (canEstimate) but a required coordinate is still
// missing and nothing is in flight — the stuck state.
function estimateBlocked(state) {
  const { estimate, estimating, pickupLatLng, dropoffLatLng } = state;
  return Boolean(
    !estimate &&
      !estimating &&
      canEstimate(state) &&
      (!pickupLatLng || !dropoffLatLng),
  );
}

// The prompt names exactly which point still needs a pin.
function estimateBlockedMsg({ pickupLatLng, dropoffLatLng }) {
  const noPickup = !pickupLatLng;
  const noDropoff = !dropoffLatLng;
  if (noPickup && noDropoff) return "ridePage.needBothPins";
  if (noPickup) return "ridePage.needPickupPin";
  return "ridePage.needDropoffPin";
}

const PIN = { lat: 33.5, lng: -7.6 };

describe("ride fare — canEstimate", () => {
  it("is false with nothing entered", () => {
    expect(canEstimate({ pickupAddress: "", dropoffAddress: "" })).toBe(false);
  });

  it("is true once both ends have text (even without pins)", () => {
    expect(canEstimate({ pickupAddress: "A", dropoffAddress: "B" })).toBe(true);
  });

  it("is true with both ends pinned", () => {
    expect(canEstimate({ pickupLatLng: PIN, dropoffLatLng: PIN })).toBe(true);
  });

  it("is false when only one end is provided", () => {
    expect(canEstimate({ pickupAddress: "A", dropoffAddress: "" })).toBe(false);
    expect(canEstimate({ pickupLatLng: PIN, dropoffAddress: "   " })).toBe(false);
  });
});

describe("ride fare — estimateBlocked (the stuck-CTA dead-end)", () => {
  it("blocks when both ends are typed but neither is pinned", () => {
    const state = { pickupAddress: "A", dropoffAddress: "B", estimate: null, estimating: false };
    expect(estimateBlocked(state)).toBe(true);
    expect(estimateBlockedMsg(state)).toBe("ridePage.needBothPins");
  });

  it("blocks and points at the pickup when only the drop-off is pinned", () => {
    const state = { pickupAddress: "A", dropoffLatLng: PIN, estimate: null, estimating: false };
    expect(estimateBlocked(state)).toBe(true);
    expect(estimateBlockedMsg(state)).toBe("ridePage.needPickupPin");
  });

  it("blocks and points at the drop-off when only the pickup is pinned", () => {
    const state = { pickupLatLng: PIN, dropoffAddress: "B", estimate: null, estimating: false };
    expect(estimateBlocked(state)).toBe(true);
    expect(estimateBlockedMsg(state)).toBe("ridePage.needDropoffPin");
  });

  it("does NOT block once both ends are pinned (estimate can run)", () => {
    expect(
      estimateBlocked({ pickupLatLng: PIN, dropoffLatLng: PIN, estimate: null, estimating: false }),
    ).toBe(false);
  });

  it("does NOT block while an estimate request is in flight", () => {
    expect(
      estimateBlocked({ pickupAddress: "A", dropoffAddress: "B", estimate: null, estimating: true }),
    ).toBe(false);
  });

  it("does NOT block once an estimate has resolved", () => {
    expect(
      estimateBlocked({
        pickupAddress: "A",
        dropoffAddress: "B",
        estimate: { fare: 20 },
        estimating: false,
      }),
    ).toBe(false);
  });

  it("does NOT block before the user has entered enough to want a fare", () => {
    expect(estimateBlocked({ pickupAddress: "", dropoffAddress: "", estimate: null, estimating: false })).toBe(
      false,
    );
  });
});
