/**
 * Unit tests for MarketplaceMenuHeader — the restaurant header / "about"
 * section of MarketplaceMenuPage.vue (customer menu-browsing page), extracted
 * into a standalone presentational component (RISK FE-2). This component holds
 * no cart, add-to-cart, checkout, or money-mutation logic; it only renders the
 * restaurant details it's given, owns a pure UI hours-expanded toggle, and
 * forwards the share intent via the `share` emit.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import MarketplaceMenuHeader from "../MarketplaceMenuHeader.vue";

const fmtPrice = (v) => `$${v}`;
const businessIcon = () => "🍽️";

const restaurant = (overrides = {}) => ({
  name: "Chez Test",
  logo_url: "",
  tagline: "",
  is_open: true,
  rating_average: null,
  rating_count: 0,
  cuisine_type: "",
  city: "",
  delivery_enabled: false,
  delivery_fee: 0,
  delivery_minimum_order: 0,
  ...overrides,
});

const mountComp = (props = {}) =>
  mount(MarketplaceMenuHeader, {
    props: {
      restaurant: restaurant(),
      prepEta: null,
      todayHours: null,
      weeklyHours: null,
      menuLinkCopied: false,
      fmtPrice,
      businessIcon,
      ...props,
    },
  });

describe("MarketplaceMenuHeader", () => {
  it("renders the kicker and restaurant name", () => {
    const w = mountComp({ restaurant: restaurant({ name: "Sushi Bar" }) });
    expect(w.text()).toContain("mktMenu.restaurantKicker");
    expect(w.text()).toContain("Sushi Bar");
  });

  it("renders the tagline only when present", () => {
    expect(mountComp().text()).not.toContain("Fresh daily");
    const w = mountComp({ restaurant: restaurant({ tagline: "Fresh daily" }) });
    expect(w.text()).toContain("Fresh daily");
  });

  it("shows the logo image when logo_url is set and no fallback icon", () => {
    const w = mountComp({ restaurant: restaurant({ logo_url: "https://cdn/logo.png", name: "Pixel Pizza" }) });
    const img = w.find("img");
    expect(img.exists()).toBe(true);
    expect(img.attributes("src")).toBe("https://cdn/logo.png");
    expect(img.attributes("alt")).toBe("Pixel Pizza");
    expect(w.text()).not.toContain("🍽️");
  });

  it("falls back to the business icon when there is no logo", () => {
    const w = mountComp({ restaurant: restaurant({ logo_url: "" }) });
    expect(w.find("img").exists()).toBe(false);
    expect(w.text()).toContain("🍽️");
  });

  it("shows the open label when the restaurant is open, closed otherwise", () => {
    expect(mountComp({ restaurant: restaurant({ is_open: true }) }).text()).toContain("mktMenu.open");
    expect(mountComp({ restaurant: restaurant({ is_open: false }) }).text()).toContain("mktMenu.closed");
  });

  it("renders the rating chip with average and count only when a rating exists", () => {
    expect(mountComp({ restaurant: restaurant({ rating_average: null }) }).text()).not.toContain("(");
    const w = mountComp({ restaurant: restaurant({ rating_average: 4.6, rating_count: 128 }) });
    expect(w.text()).toContain("4.6");
    expect(w.text()).toContain("(128)");
  });

  it("renders the prep-ETA chip with min/max params when prepEta is present", () => {
    expect(mountComp({ prepEta: null }).text()).not.toContain("menu.etaReadyIn");
    const w = mountComp({ prepEta: { min: 10, max: 20 } });
    expect(w.text()).toContain('menu.etaReadyIn:{"min":10,"max":20}');
  });

  it("shows the delivery-fee chip using fmtPrice when a fee is charged", () => {
    const w = mountComp({ restaurant: restaurant({ delivery_enabled: true, delivery_fee: "5.00" }) });
    expect(w.text()).toContain("mktMenu.deliveryFee");
    expect(w.text()).toContain("$5.00");
    expect(w.text()).not.toContain("mktMenu.freeDelivery");
  });

  it("shows the free-delivery label when the fee is zero", () => {
    const w = mountComp({ restaurant: restaurant({ delivery_enabled: true, delivery_fee: 0 }) });
    expect(w.text()).toContain("mktMenu.freeDelivery");
  });

  it("hides delivery chips entirely when delivery is disabled", () => {
    const w = mountComp({ restaurant: restaurant({ delivery_enabled: false, delivery_fee: "5.00", delivery_minimum_order: "50" }) });
    expect(w.text()).not.toContain("mktMenu.deliveryFee");
    expect(w.text()).not.toContain("mktMenu.minOrder");
  });

  it("shows the minimum-order chip only when delivery is enabled and a minimum is set", () => {
    const none = mountComp({ restaurant: restaurant({ delivery_enabled: true, delivery_minimum_order: 0 }) });
    expect(none.text()).not.toContain("mktMenu.minOrder");
    const w = mountComp({ restaurant: restaurant({ delivery_enabled: true, delivery_minimum_order: "50" }) });
    expect(w.text()).toContain('mktMenu.minOrder:{"amount":"$50"}');
  });

  it("does not render the opening-hours disclosure when todayHours is null", () => {
    const w = mountComp({ todayHours: null });
    expect(w.find("button[aria-expanded]").exists()).toBe(false);
  });

  it("shows today's hours when open and the closed label when closed today", () => {
    const open = mountComp({ todayHours: { closed: false, open: "09:00", close: "22:00" } });
    expect(open.text()).toContain('mktMenu.hoursToday:{"open":"09:00","close":"22:00"}');
    const closed = mountComp({ todayHours: { closed: true } });
    expect(closed.text()).toContain("mktMenu.hoursClosedToday");
  });

  it("keeps the weekly hours collapsed until the toggle is clicked (local UI state)", async () => {
    const weeklyHours = [
      { key: "mon", label: "Mon", isToday: true, open: "09:00", close: "22:00" },
      { key: "tue", label: "Tue", isToday: false, open: null, close: null },
    ];
    const w = mountComp({
      todayHours: { closed: false, open: "09:00", close: "22:00" },
      weeklyHours,
    });
    const toggle = w.find("button[aria-expanded]");
    expect(toggle.attributes("aria-expanded")).toBe("false");
    expect(w.text()).not.toContain("Tue");

    await toggle.trigger("click");
    expect(toggle.attributes("aria-expanded")).toBe("true");
    expect(w.text()).toContain("Mon");
    expect(w.text()).toContain("Tue");
  });

  it("emits share when the share button is clicked, without any cart/order mutation", async () => {
    const w = mountComp();
    await w.find('[aria-label="mktMenu.shareRestaurant"]').trigger("click");
    expect(w.emitted("share")).toHaveLength(1);
    // Only the share intent leaves this presentational block — no cart/order/payment
    // events. (The bubbled native "click" is a test-utils artifact, not a declared emit.)
    const customEmits = Object.keys(w.emitted()).filter((e) => e !== "click");
    expect(customEmits).toEqual(["share"]);
  });

  it("switches the share button label to the copied state via menuLinkCopied", () => {
    expect(mountComp({ menuLinkCopied: false }).text()).toContain("mktMenu.share");
    const copied = mountComp({ menuLinkCopied: true });
    expect(copied.text()).toContain("mktMenu.linkCopied");
    expect(copied.text()).not.toContain("mktMenu.share");
  });
});
