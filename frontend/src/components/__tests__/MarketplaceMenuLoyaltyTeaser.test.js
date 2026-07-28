/**
 * Unit tests for MarketplaceMenuLoyaltyTeaser — the loyalty-points teaser of
 * MarketplaceMenuPage.vue, extracted into a standalone presentational component
 * (RISK FE-2). Display only: current points (or an earn prompt), an optional
 * earn-projection / redeem hint, and a points badge. The loyaltyConfig.enabled &&
 * isAuthenticated render gate stays in the parent.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import MarketplaceMenuLoyaltyTeaser from "../MarketplaceMenuLoyaltyTeaser.vue";

const mountTeaser = (props = {}) =>
  mount(MarketplaceMenuLoyaltyTeaser, {
    props: { points: 0, earnProjection: 0, available: false, ...props },
  });

describe("MarketplaceMenuLoyaltyTeaser", () => {
  it("is a note region for assistive tech", () => {
    const w = mountTeaser();
    expect(w.find('[role="note"]').exists()).toBe(true);
  });

  it("shows the points label and the badge when points > 0", () => {
    const w = mountTeaser({ points: 120 });
    expect(w.text()).toContain('mktMenu.loyaltyTeaserPts:{"points":120}');
    // the badge span shows the raw number
    const badge = w.findAll("span").find((s) => s.text() === "120");
    expect(badge).toBeTruthy();
  });

  it("shows the earn prompt and no badge when points === 0", () => {
    const w = mountTeaser({ points: 0 });
    expect(w.text()).toContain("mktMenu.loyaltyTeaserEarn");
    expect(w.text()).not.toContain("loyaltyTeaserPts");
    const badge = w.findAll("span").find((s) => s.text() === "0");
    expect(badge).toBeFalsy();
  });

  it("shows the earn-projection line when earnProjection > 0", () => {
    const w = mountTeaser({ points: 50, earnProjection: 8 });
    expect(w.text()).toContain('mktMenu.loyaltyEarnProjection:{"points":8}');
    expect(w.text()).not.toContain("mktMenu.loyaltyTeaserRedeem");
  });

  it("falls back to the redeem hint when no projection but redemption is available", () => {
    const w = mountTeaser({ points: 50, earnProjection: 0, available: true });
    expect(w.text()).toContain("mktMenu.loyaltyTeaserRedeem");
    expect(w.text()).not.toContain("mktMenu.loyaltyEarnProjection");
  });

  it("shows neither secondary line when there is no projection and redemption is unavailable", () => {
    const w = mountTeaser({ points: 50, earnProjection: 0, available: false });
    expect(w.text()).not.toContain("mktMenu.loyaltyEarnProjection");
    expect(w.text()).not.toContain("mktMenu.loyaltyTeaserRedeem");
  });
});
