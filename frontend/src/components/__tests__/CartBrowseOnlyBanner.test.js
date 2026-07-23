/**
 * Unit test for CartBrowseOnlyBanner — the "browse-only plan" notice extracted
 * from Cart.vue (RISK FE-2). Pure presentational; the isBrowseOnlyPlan condition
 * stays in the parent.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({ useI18n: () => ({ t: (k) => k }) }));

import CartBrowseOnlyBanner from "../CartBrowseOnlyBanner.vue";

describe("CartBrowseOnlyBanner", () => {
  it("renders the ordering-disabled title + browse-only body", () => {
    const w = mount(CartBrowseOnlyBanner);
    expect(w.text()).toContain("cartPage.orderingDisabled");
    expect(w.text()).toContain("cartPage.browseOnlyBody");
  });
});
