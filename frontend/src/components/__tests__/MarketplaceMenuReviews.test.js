/**
 * Unit tests for MarketplaceMenuReviews — the customer-reviews horizontal
 * scroll rail of MarketplaceMenuPage.vue (customer menu-browsing page),
 * extracted into a standalone presentational component (RISK FE-2). This
 * component holds no cart, add-to-cart, or money logic; it only renders the
 * reviews it's given.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import MarketplaceMenuReviews from "../MarketplaceMenuReviews.vue";

const mountComp = (props = {}) =>
  mount(MarketplaceMenuReviews, {
    props: {
      reviews: [],
      ...props,
    },
  });

describe("MarketplaceMenuReviews", () => {
  it("renders the reviews title kicker", () => {
    const w = mountComp();
    expect(w.text()).toContain("mktMenu.reviewsTitle");
  });

  it("renders no review cards when the reviews list is empty", () => {
    const w = mountComp({ reviews: [] });
    expect(w.findAll(".snap-start").length).toBe(0);
  });

  it("renders one card per review with its comment and star rating", () => {
    const w = mountComp({
      reviews: [
        { score: 4, comment: "Great food, fast delivery." },
        { score: 2, comment: "Order was cold." },
      ],
    });
    const cards = w.findAll(".snap-start");
    expect(cards.length).toBe(2);
    expect(cards[0].text()).toContain("Great food, fast delivery.");
    expect(cards[1].text()).toContain("Order was cold.");
  });

  it("shows filled stars matching the score and dims the remaining stars", () => {
    const w = mountComp({ reviews: [{ score: 3, comment: "Decent." }] });
    const starWrap = w.find('[aria-label="3 stars"]');
    expect(starWrap.exists()).toBe(true);
    // 3 filled stars, then a dimmed span with the remaining 2 stars.
    expect(starWrap.text()).toBe("★★★★★");
    expect(starWrap.find(".opacity-25").text()).toBe("★★");
  });

  it("does not emit anything — this component is display-only", () => {
    const w = mountComp({ reviews: [{ score: 5, comment: "Perfect." }] });
    expect(Object.keys(w.emitted())).toEqual([]);
  });
});
