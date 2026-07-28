/**
 * Unit tests for MarketplaceMenuFlashSaleBanner — the flash-sale banner of
 * MarketplaceMenuPage.vue, extracted into a standalone presentational component
 * (RISK FE-2). Display only: it shows the discount pct and, when a countdown
 * string is supplied, the time remaining. The restaurant.flash_sale render gate
 * and the countdown timer stay in the parent.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import MarketplaceMenuFlashSaleBanner from "../MarketplaceMenuFlashSaleBanner.vue";

const mountBanner = (props = {}) =>
  mount(MarketplaceMenuFlashSaleBanner, {
    props: { flashSale: { discount_pct: 20 }, countdown: "", ...props },
  });

describe("MarketplaceMenuFlashSaleBanner", () => {
  it("renders the flash-sale banner label with the discount percentage", () => {
    const w = mountBanner({ flashSale: { discount_pct: 20 } });
    expect(w.text()).toContain('mktMenu.flashSaleBanner:{"pct":20}');
  });

  it("is a status region for assistive tech", () => {
    const w = mountBanner();
    expect(w.find('[role="status"]').exists()).toBe(true);
  });

  it("renders the countdown line when a countdown string is provided", () => {
    const w = mountBanner({ countdown: "04:37" });
    expect(w.text()).toContain('mktMenu.flashSaleEnds:{"time":"04:37"}');
  });

  it("hides the countdown line when the countdown is empty", () => {
    const w = mountBanner({ countdown: "" });
    expect(w.text()).not.toContain("mktMenu.flashSaleEnds");
  });
});
