/**
 * Unit tests for FulfillmentBreakdown — pickup/delivery/table split widget.
 *
 * Verifies the `rows` derivation: zero-count types are filtered out, remaining
 * types sort by count descending, and an empty breakdown shows the empty state.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

// Deterministic i18n: labels pass through; formatNumber returns the raw value.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k, formatNumber: (v) => String(v) }),
}));

import FulfillmentBreakdown from "../FulfillmentBreakdown.vue";

describe("FulfillmentBreakdown", () => {
  it("shows the empty state when the breakdown is empty", () => {
    const w = mount(FulfillmentBreakdown, { props: { breakdown: {} } });
    expect(w.text()).toContain("ownerHome.noOrdersYet");
    // No stacked-bar segments are rendered (segments carry a title attribute)
    expect(w.findAll("[title]").length).toBe(0);
  });

  it("filters zero-count types and sorts the rest by count descending", () => {
    const breakdown = {
      pickup:   { count: 3, revenue: 30, count_pct: 30 },
      delivery: { count: 6, revenue: 60, count_pct: 60 },
      table:    { count: 0, revenue: 0,  count_pct: 0 },
    };
    const w = mount(FulfillmentBreakdown, { props: { breakdown, currency: "USD" } });
    const txt = w.text();

    // Zero-count "table" type is filtered out entirely
    expect(txt).not.toContain("ownerHome.fulfillmentTable");

    // Delivery (6) sorts before pickup (3)
    const deliveryIdx = txt.indexOf("ownerHome.fulfillmentDelivery");
    const pickupIdx = txt.indexOf("ownerHome.fulfillmentPickup");
    expect(deliveryIdx).toBeGreaterThanOrEqual(0);
    expect(pickupIdx).toBeGreaterThan(deliveryIdx);
  });

  it("renders one stacked-bar segment per non-zero type", () => {
    const breakdown = {
      pickup:   { count: 3, revenue: 30, count_pct: 50 },
      delivery: { count: 3, revenue: 30, count_pct: 50 },
    };
    const w = mount(FulfillmentBreakdown, { props: { breakdown } });
    // Two segments, each with a title attribute
    expect(w.findAll("[title]").length).toBe(2);
  });
});
