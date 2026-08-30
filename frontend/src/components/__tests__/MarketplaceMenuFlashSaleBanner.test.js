/**
 * Unit tests for MarketplaceMenuFlashSaleBanner — the flash-sale banner of
 * MarketplaceMenuPage.vue (RISK FE-2).
 *
 * As of the H-2 perf fix the banner OWNS its 1-second countdown timer: it derives
 * the countdown string from `flashSale.active_until`, ticks it down every second,
 * and emits `ended` when the sale crosses 0 so the parent can clear
 * `restaurant.flash_sale` (which reverts dish prices + checkout discount). The
 * `restaurant.flash_sale` render gate still lives in the parent.
 *
 * Contracts verified:
 *   - renders the discount-pct label
 *   - is a role=status region
 *   - derives the countdown from active_until (MM:SS < 1h, "Hh MMm" ≥ 1h)
 *   - hides the countdown line ≥ 24h out, and when active_until is absent
 *   - ticks down once per second
 *   - emits `ended` when the countdown reaches 0
 *   - clears its interval on unmount (no leaked timer)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import MarketplaceMenuFlashSaleBanner from "../MarketplaceMenuFlashSaleBanner.vue";

// active_until as an ISO string N ms ahead of the frozen clock.
const inMs = (ms) => new Date(Date.now() + ms).toISOString();

const mountBanner = (flashSale) =>
  mount(MarketplaceMenuFlashSaleBanner, { props: { flashSale } });

describe("MarketplaceMenuFlashSaleBanner", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-30T12:00:00.000Z"));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the flash-sale banner label with the discount percentage", () => {
    const w = mountBanner({ discount_pct: 20, active_until: inMs(5 * 60_000) });
    expect(w.text()).toContain('mktMenu.flashSaleBanner:{"pct":20}');
  });

  it("is a status region for assistive tech", () => {
    const w = mountBanner({ discount_pct: 20, active_until: inMs(5 * 60_000) });
    expect(w.find('[role="status"]').exists()).toBe(true);
  });

  it("derives and renders the countdown from active_until (MM:SS under 1h)", () => {
    const w = mountBanner({ discount_pct: 20, active_until: inMs(4 * 60_000 + 37_000) });
    expect(w.text()).toContain('mktMenu.flashSaleEnds:{"time":"04:37"}');
  });

  it("formats the countdown as Hh MMm when more than an hour remains", () => {
    const w = mountBanner({ discount_pct: 20, active_until: inMs(2 * 3_600_000 + 5 * 60_000) });
    expect(w.text()).toContain('mktMenu.flashSaleEnds:{"time":"2h 05m"}');
  });

  it("hides the countdown line when 24h or more remains", () => {
    const w = mountBanner({ discount_pct: 20, active_until: inMs(25 * 3_600_000) });
    expect(w.text()).not.toContain("mktMenu.flashSaleEnds");
  });

  it("hides the countdown line when there is no active_until", () => {
    const w = mountBanner({ discount_pct: 20 });
    expect(w.text()).not.toContain("mktMenu.flashSaleEnds");
  });

  it("ticks the countdown down once per second", async () => {
    const w = mountBanner({ discount_pct: 20, active_until: inMs(4 * 60_000 + 37_000) });
    expect(w.text()).toContain('{"time":"04:37"}');
    vi.advanceTimersByTime(1000);
    await Promise.resolve();
    expect(w.text()).toContain('{"time":"04:36"}');
  });

  it("emits `ended` when the countdown reaches 0", async () => {
    const w = mountBanner({ discount_pct: 20, active_until: inMs(2000) });
    expect(w.emitted("ended")).toBeUndefined();
    vi.advanceTimersByTime(2000);
    await Promise.resolve();
    expect(w.emitted("ended")).toBeTruthy();
  });

  it("clears its interval on unmount (no leaked timer)", () => {
    const w = mountBanner({ discount_pct: 20, active_until: inMs(4 * 60_000) });
    expect(vi.getTimerCount()).toBeGreaterThan(0);
    w.unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
