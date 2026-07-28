/**
 * Unit tests for MarketplaceCheckoutFulfillmentType — the pickup/delivery selector
 * of the Marketplace checkout drawer (RISK FE-2). The type is a two-way model; the
 * delivery button only shows when the restaurant supports delivery.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({ useI18n: () => ({ t: (k) => k }) }));

import MarketplaceCheckoutFulfillmentType from "../MarketplaceCheckoutFulfillmentType.vue";

const mountIt = (props = {}) =>
  mount(MarketplaceCheckoutFulfillmentType, { props: { fulfillmentType: "pickup", deliveryEnabled: true, ...props } });

describe("MarketplaceCheckoutFulfillmentType", () => {
  it("shows both options when delivery is enabled and marks the active one", () => {
    const w = mountIt({ fulfillmentType: "pickup" });
    const btns = w.findAll("button");
    expect(btns).toHaveLength(2);
    expect(btns[0].attributes("aria-pressed")).toBe("true"); // pickup active
    expect(btns[1].attributes("aria-pressed")).toBe("false");
  });

  it("hides the delivery button when delivery is not enabled", () => {
    expect(mountIt({ deliveryEnabled: false }).findAll("button")).toHaveLength(1);
  });

  it("emits update:fulfillmentType when a type is picked", async () => {
    const w = mountIt({ fulfillmentType: "pickup" });
    await w.findAll("button")[1].trigger("click"); // delivery
    expect(w.emitted("update:fulfillmentType")[0]).toEqual(["delivery"]);
  });
});
