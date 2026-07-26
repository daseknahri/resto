/**
 * Unit tests for MarketplaceCheckoutDelivery — the delivery-details block of the
 * Marketplace checkout drawer (RISK FE-2). Presentational: the parent keeps
 * geolocation + saved-address logic + the fee computeds; here we verify the
 * saved-address list, the address/save-address models, the locate affordance, and
 * the fee-hint branches.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));
vi.mock("../AppIcon.vue", () => ({
  default: { name: "AppIcon", props: ["name"], template: '<span class="app-icon" />' },
}));

import MarketplaceCheckoutDelivery from "../MarketplaceCheckoutDelivery.vue";

const base = {
  deliveryAddress: "", saveAddress: false, saveAddressLabel: "",
  isAuthenticated: false, savedAddresses: [], locating: false, locateError: "",
  hasLocation: false, outOfRange: false, radiusKm: 5, feeIsDistance: false,
  deliveryFee: 0, distanceKm: 0, perKm: 0, fmtPrice: (n) => `$${Number(n).toFixed(2)}`,
};
const mountIt = (props = {}) => mount(MarketplaceCheckoutDelivery, { props: { ...base, ...props } });

describe("MarketplaceCheckoutDelivery", () => {
  it("lists saved addresses only when signed in and some exist; apply/delete emit", async () => {
    expect(mountIt({ isAuthenticated: false, savedAddresses: [{ id: 1, address: "A" }] }).text()).not.toContain("mktMenu.savedAddresses");
    const addr = { id: 7, label: "Home", address: "12 St" };
    const w = mountIt({ isAuthenticated: true, savedAddresses: [addr] });
    expect(w.text()).toContain("Home");
    const rowBtns = w.findAll(".space-y-1 button");
    await rowBtns[0].trigger("click"); // apply
    await rowBtns[1].trigger("click"); // delete
    expect(w.emitted("applyAddress")[0]).toEqual([addr]);
    expect(w.emitted("deleteAddress")[0]).toEqual([7]);
  });

  it("emits update:deliveryAddress as the textarea is typed", async () => {
    const w = mountIt();
    await w.find("textarea").setValue("45 Rue X");
    expect(w.emitted("update:deliveryAddress")[0]).toEqual(["45 Rue X"]);
  });

  it("shows the save-address checkbox only when signed in with an address, and the label input when checked", () => {
    expect(mountIt({ isAuthenticated: true, deliveryAddress: "" }).find('input[type="checkbox"]').exists()).toBe(false);
    const w = mountIt({ isAuthenticated: true, deliveryAddress: "45 Rue X", saveAddress: true });
    expect(w.find('input[type="checkbox"]').exists()).toBe(true);
    expect(w.find('input[type="text"]').exists()).toBe(true); // the label input (saveAddress true)
  });

  it("emits locate, disables the button + shows the spinner while locating, and reflects hasLocation", async () => {
    const idle = mountIt({ hasLocation: false });
    const locateBtn = idle.findAll("button").find((b) => b.text().includes("mktMenu.useMyLocation"));
    await locateBtn.trigger("click");
    expect(idle.emitted("locate")).toBeTruthy();
    expect(mountIt({ hasLocation: true }).text()).toContain("mktMenu.locationSet");
    const busy = mountIt({ locating: true });
    expect(busy.find(".animate-spin").exists()).toBe(true);
    expect(busy.findAll("button").find((b) => b.text().includes("mktMenu.locating")).attributes("disabled")).toBeDefined();
  });

  it("renders the right fee hint per state (out-of-range / distance / needs-location)", () => {
    expect(mountIt({ outOfRange: true, radiusKm: 8 }).text()).toContain('mktMenu.deliveryOutOfRange:{"km":8}');
    expect(mountIt({ feeIsDistance: true, deliveryFee: 12, distanceKm: 3 }).text()).toContain('mktMenu.deliveryFeeDistance:{"fee":"$12.00","km":3}');
    expect(mountIt({ perKm: 2 }).text()).toContain("mktMenu.deliveryNeedsLocation");
  });
});
