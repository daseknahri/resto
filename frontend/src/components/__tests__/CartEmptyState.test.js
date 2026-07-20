/**
 * Unit test for CartEmptyState — the empty-cart state extracted from Cart.vue
 * (RISK FE-2). Pure presentational: the empty message + a link back to the menu.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({ useI18n: () => ({ t: (k) => k }) }));
vi.mock("../AppIcon.vue", () => ({
  default: { name: "AppIcon", props: ["name"], template: "<span />" },
}));

import CartEmptyState from "../CartEmptyState.vue";

describe("CartEmptyState", () => {
  it("renders the empty message and a browse-menu link to the menu route", () => {
    const w = mount(CartEmptyState, {
      global: { stubs: { RouterLink: { name: "RouterLink", props: ["to"], template: '<a><slot /></a>' } } },
    });
    expect(w.text()).toContain("cartPage.cartEmpty");
    expect(w.text()).toContain("cartPage.cartEmptyBody");
    expect(w.text()).toContain("cartPage.browseMenu");
    expect(w.findComponent({ name: "RouterLink" }).props("to")).toEqual({ name: "menu" });
  });
});
