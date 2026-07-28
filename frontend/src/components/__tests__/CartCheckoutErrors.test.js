/**
 * Unit tests for CartCheckoutErrors — the checkout error alerts extracted from
 * Cart.vue (RISK FE-2). Display only: one red alert per non-empty error message
 * (place-order / checkout / handoff), in that order. No state, no logic.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../AppIcon.vue", () => ({
  default: { name: "AppIcon", props: ["name"], template: "<span />" },
}));

import CartCheckoutErrors from "../CartCheckoutErrors.vue";

const mountIt = (props = {}) =>
  mount(CartCheckoutErrors, {
    props: { placeOrderError: "", checkoutError: "", handoffError: "", ...props },
  });

describe("CartCheckoutErrors", () => {
  it("renders nothing when there are no errors", () => {
    const w = mountIt();
    expect(w.findAll('[role="alert"]').length).toBe(0);
  });

  it("renders one alert per non-empty error", () => {
    const w = mountIt({ placeOrderError: "place failed", handoffError: "handoff failed" });
    const alerts = w.findAll('[role="alert"]');
    expect(alerts.length).toBe(2);
    expect(w.text()).toContain("place failed");
    expect(w.text()).toContain("handoff failed");
  });

  it("keeps the place-order / checkout / handoff order", () => {
    const w = mountIt({ placeOrderError: "A", checkoutError: "B", handoffError: "C" });
    const texts = w.findAll('[role="alert"]').map((a) => a.text());
    expect(texts).toEqual(["A", "B", "C"]);
  });
});
