/**
 * Unit tests for MarketplaceCheckoutCartItems — the cart line-item list of the
 * Marketplace checkout drawer, a PRESENTATIONAL child (RISK FE-2). It renders each
 * cart line + a qty stepper and emits decrement/increment carrying the tapped line's
 * COMPOSITE KEY (`${slug}::${optionSig}`); the parent keeps the cart + its key-based
 * mutation handlers.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

import MarketplaceCheckoutCartItems from "../MarketplaceCheckoutCartItems.vue";

const cart = [
  { slug: "burger", name: "Burger", qty: 2, price: 50, unitPrice: 55, options: [{ name: "Large" }] },
  { slug: "fries", name: "Fries", qty: 1, price: 20 },
];

const mountIt = (props = {}) =>
  mount(MarketplaceCheckoutCartItems, {
    props: { cart, unavailableSlugs: new Set(), fmtPrice: (n) => `$${Number(n).toFixed(2)}`, ...props },
  });

describe("MarketplaceCheckoutCartItems", () => {
  it("renders a row per cart item with name, options, line total and unit price", () => {
    const w = mountIt();
    expect(w.findAll("article")).toHaveLength(2);
    expect(w.text()).toContain("Burger");
    expect(w.text()).toContain("Large"); // chosen option
    expect(w.text()).toContain("$110.00"); // 55 * 2 line total
    expect(w.text()).toContain("$55.00"); // unit price
  });

  it("falls back to price when unitPrice is absent", () => {
    expect(mountIt().text()).toContain("$20.00"); // fries: price 20, no unitPrice
  });

  it("flags and strikes through unavailable items", () => {
    const w = mountIt({ unavailableSlugs: new Set(["burger"]) });
    expect(w.text()).toContain("mktMenu.cartItemUnavailable");
    expect(w.find(".line-through").exists()).toBe(true);
  });

  it("emits decrement with the line's composite key from the − button", async () => {
    const w = mountIt();
    // First article's first stepper button is the decrement. The burger line has no
    // valid option ids, so its key resolves to `burger::`.
    await w.findAll("article")[0].findAll("button")[0].trigger("click");
    expect(w.emitted("decrement")[0]).toEqual(["burger::"]);
  });

  it("emits increment with the line's composite key from the ＋ button", async () => {
    const w = mountIt();
    await w.findAll("article")[0].findAll("button")[1].trigger("click");
    expect(w.emitted("increment")[0]).toEqual(["burger::"]);
  });

  it("prefers an explicit line `key` field and steps the EXACT tapped line (two configs of one dish)", async () => {
    // Two configurations of one dish coexist as separate lines, keyed by their
    // composite key (PR #248). The stepper must target the row the user tapped, not
    // the first line of that slug.
    const twoConfigs = [
      { key: "pizza::1", slug: "pizza", name: "Pizza", qty: 1, price: 80, unitPrice: 80, options: [{ id: 1, name: "Cheese" }] },
      { key: "pizza::2", slug: "pizza", name: "Pizza", qty: 3, price: 80, unitPrice: 90, options: [{ id: 2, name: "Pepperoni" }] },
    ];
    const w = mountIt({ cart: twoConfigs });
    const rows = w.findAll("article");
    expect(rows).toHaveLength(2);
    // Tap the SECOND row's increment → its composite key, not the first line's.
    await rows[1].findAll("button")[1].trigger("click");
    expect(w.emitted("increment")[0]).toEqual(["pizza::2"]);
    // Tap the SECOND row's decrement → same line's key.
    await rows[1].findAll("button")[0].trigger("click");
    expect(w.emitted("decrement")[0]).toEqual(["pizza::2"]);
  });
});
