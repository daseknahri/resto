/**
 * Unit tests for pickupLabelKey — the (businessType, variant) → i18n-key mapping
 * that keeps every customer/driver/admin surface using identical pickup-location
 * wording. Locks in the vertical branching so a pharmacy customer never reads
 * "the restaurant" and a grocery never reads "the kitchen".
 */
import { describe, it, expect } from "vitest";
import { pickupLabelKey } from "../deliveryVocab";

describe("pickupLabelKey", () => {
  it("maps pharmacy to the pharmacy keys for every variant", () => {
    expect(pickupLabelKey("pharmacy", "at")).toBe("deliveryVocab.atPickupPharmacy");
    expect(pickupLabelKey("pharmacy", "preparing")).toBe("deliveryVocab.preparingPharmacy");
    expect(pickupLabelKey("pharmacy", "collect")).toBe("deliveryVocab.collectPharmacy");
  });

  it("maps store types (retail / grocery / bakery) to the store keys", () => {
    for (const bt of ["retail", "grocery", "bakery"]) {
      expect(pickupLabelKey(bt, "at")).toBe("deliveryVocab.atPickupStore");
      expect(pickupLabelKey(bt, "preparing")).toBe("deliveryVocab.preparingStore");
      expect(pickupLabelKey(bt, "collect")).toBe("deliveryVocab.collectStore");
    }
  });

  it("falls back to restaurant wording for restaurant, cafe, unknown, and missing types", () => {
    // 'cafe' is a kitchen-prep food business → deliberately restaurant wording.
    for (const bt of ["restaurant", "cafe", "weird-future-type", "", null, undefined]) {
      expect(pickupLabelKey(bt, "at")).toBe("deliveryVocab.atPickupRestaurant");
      expect(pickupLabelKey(bt, "preparing")).toBe("deliveryVocab.preparingRestaurant");
      expect(pickupLabelKey(bt, "collect")).toBe("deliveryVocab.collectRestaurant");
    }
  });

  it("is case-insensitive on the business type", () => {
    expect(pickupLabelKey("PHARMACY", "at")).toBe("deliveryVocab.atPickupPharmacy");
    expect(pickupLabelKey("Grocery", "collect")).toBe("deliveryVocab.collectStore");
  });

  it("falls back to atPickupRestaurant for an unknown variant", () => {
    expect(pickupLabelKey("pharmacy", "bogus")).toBe("deliveryVocab.atPickupRestaurant");
    expect(pickupLabelKey("grocery", undefined)).toBe("deliveryVocab.atPickupRestaurant");
  });
});
