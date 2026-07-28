/**
 * Unit tests for DriverPagePerformanceStats — the driver performance stats strip
 * (avg rating / acceptance rate / completion rate) of DriverPage.vue, extracted
 * into a standalone presentational component (RISK FE-2). Display only: it renders
 * the three headline figures from the driver's `earnings` summary, with no emits,
 * no API calls, and no mutation. The `earnings && earnings.total_deliveries > 0`
 * render gate stays in the parent, so `earnings` is always present here.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import DriverPagePerformanceStats from "../DriverPagePerformanceStats.vue";

const earnings = (overrides = {}) => ({
  avg_rating: 4.8,
  acceptance_rate: 92,
  completion_rate: 97,
  ...overrides,
});

const mountStrip = (props = {}) =>
  mount(DriverPagePerformanceStats, {
    props: { earnings: earnings(), ...props },
  });

describe("DriverPagePerformanceStats", () => {
  it("renders the three stat labels", () => {
    const w = mountStrip();
    expect(w.text()).toContain("driver.avgRating");
    expect(w.text()).toContain("driver.acceptanceRate");
    expect(w.text()).toContain("driver.completionRate");
  });

  it("sets the aria-label on the strip", () => {
    const w = mountStrip();
    expect(w.find('[aria-label="driver.statsCard"]').exists()).toBe(true);
  });

  it("renders the average rating with a leading star when present", () => {
    const w = mountStrip({ earnings: earnings({ avg_rating: 4.8 }) });
    expect(w.text()).toContain("★ 4.8");
  });

  it("renders an em-dash for a null average rating", () => {
    const w = mountStrip({ earnings: earnings({ avg_rating: null }) });
    expect(w.text()).not.toContain("★");
    expect(w.text()).toContain("—");
  });

  it("renders the acceptance rate as a percentage when present", () => {
    const w = mountStrip({ earnings: earnings({ acceptance_rate: 92 }) });
    expect(w.text()).toContain("92%");
  });

  it("renders an em-dash for a null acceptance rate", () => {
    const w = mountStrip({ earnings: earnings({ acceptance_rate: null }) });
    expect(w.text()).toContain("—");
  });

  it("renders the completion rate as a percentage when present", () => {
    const w = mountStrip({ earnings: earnings({ completion_rate: 97 }) });
    expect(w.text()).toContain("97%");
  });

  it("renders an em-dash for a null completion rate", () => {
    const w = mountStrip({ earnings: earnings({ completion_rate: null }) });
    expect(w.text()).toContain("—");
  });

  it("shows an em-dash for every metric when all are null", () => {
    const w = mountStrip({
      earnings: earnings({ avg_rating: null, acceptance_rate: null, completion_rate: null }),
    });
    // three cells, all em-dash, no star / percentage
    expect(w.text()).not.toContain("★");
    expect(w.text()).not.toContain("%");
    expect((w.text().match(/—/g) || []).length).toBe(3);
  });
});
