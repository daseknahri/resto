/**
 * Unit tests for OwnerKitchenNewOrderBanner — the transient new-order flash
 * banner of OwnerKitchen.vue, extracted into a standalone presentational
 * component (RISK FE-2). Display only: it renders a status banner while `show`
 * is true. The newOrderFlash trigger/timer stays in the parent.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) => k,
  }),
}));

import OwnerKitchenNewOrderBanner from "../OwnerKitchenNewOrderBanner.vue";

describe("OwnerKitchenNewOrderBanner", () => {
  it("renders nothing when show is false", () => {
    const w = mount(OwnerKitchenNewOrderBanner, { props: { show: false } });
    expect(w.find('[role="status"]').exists()).toBe(false);
  });

  it("renders the polite status banner with the alert label when show is true", () => {
    const w = mount(OwnerKitchenNewOrderBanner, { props: { show: true } });
    const banner = w.find('[role="status"]');
    expect(banner.exists()).toBe(true);
    expect(banner.attributes("aria-live")).toBe("polite");
    expect(banner.attributes("aria-atomic")).toBe("true");
    expect(w.text()).toContain("kitchen.newOrderAlert");
  });
});
