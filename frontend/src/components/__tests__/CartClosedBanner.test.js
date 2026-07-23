/**
 * Unit test for CartClosedBanner — the "restaurant closed" notice extracted from
 * Cart.vue (RISK FE-2). Pure presentational; the visibility condition stays in
 * the parent.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({ useI18n: () => ({ t: (k) => k }) }));

import CartClosedBanner from "../CartClosedBanner.vue";

describe("CartClosedBanner", () => {
  it("renders the closed title + body as a status region", () => {
    const w = mount(CartClosedBanner);
    expect(w.find('[role="status"]').exists()).toBe(true);
    expect(w.text()).toContain("cartPage.restaurantClosed");
    expect(w.text()).toContain("cartPage.restaurantClosedBody");
  });
});
