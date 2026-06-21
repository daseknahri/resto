import { describe, it, expect } from "vitest";

// Pure mirror of the pre-order ETA composition used in Cart.vue's checkoutEta /
// deliveryTravelMin computeds. The backend owns the prep range (prep_eta_min/max);
// the FE only adds the delivery travel leg using the same road-distance + average
// speed the backend tenancy/routing._eta_minutes uses. This locks that contract.
const AVG_SPEED_KMH = 22;

function travelMin(km) {
  if (km == null || km <= 0) return 0;
  return Math.max(1, Math.round((km / AVG_SPEED_KMH) * 60));
}

function checkoutEta({ prepMin, prepMax, fulfillment, km }) {
  if (prepMin == null || prepMax == null) return null;
  if (fulfillment === "delivery") {
    const t = travelMin(km);
    return { type: "delivery", min: prepMin + t, max: prepMax + t };
  }
  return { type: "pickup", min: prepMin, max: prepMax };
}

describe("checkout pre-order ETA composition", () => {
  it("returns null when the backend prep range is absent", () => {
    expect(checkoutEta({ prepMin: null, prepMax: null, fulfillment: "pickup" })).toBeNull();
  });

  it("pickup shows the prep range unchanged", () => {
    expect(checkoutEta({ prepMin: 15, prepMax: 30, fulfillment: "pickup" })).toEqual({
      type: "pickup",
      min: 15,
      max: 30,
    });
  });

  it("delivery adds travel minutes to BOTH ends of the range", () => {
    // 11 km / 22 km/h = 0.5 h = 30 min travel.
    expect(checkoutEta({ prepMin: 15, prepMax: 30, fulfillment: "delivery", km: 11 })).toEqual({
      type: "delivery",
      min: 45,
      max: 60,
    });
  });

  it("delivery with unknown/zero distance adds no travel (prep only)", () => {
    expect(checkoutEta({ prepMin: 20, prepMax: 35, fulfillment: "delivery", km: null })).toEqual({
      type: "delivery",
      min: 20,
      max: 35,
    });
    expect(checkoutEta({ prepMin: 20, prepMax: 35, fulfillment: "delivery", km: 0 })).toEqual({
      type: "delivery",
      min: 20,
      max: 35,
    });
  });

  it("travel minutes are floored at 1 for a tiny non-zero distance", () => {
    expect(travelMin(0.1)).toBe(1);
  });
});
