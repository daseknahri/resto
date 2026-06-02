/**
 * Unit tests for PeriodBadge — the period-over-period % change indicator.
 *
 * Locks in: null/undefined → renders nothing; positive → "+" emerald;
 * negative → "−" (U+2212) red (regression guard: the sign used to be dropped
 * for negatives, rendering "-5%" as "5%"); sub-threshold → neutral slate.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

// Deterministic i18n: label key passes through unchanged.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

import PeriodBadge from "../PeriodBadge.vue";

describe("PeriodBadge", () => {
  it("renders nothing when pct is null", () => {
    const w = mount(PeriodBadge, { props: { pct: null } });
    expect(w.find("p").exists()).toBe(false);
  });

  it("renders nothing when pct is undefined (prop omitted)", () => {
    const w = mount(PeriodBadge, { props: {} });
    expect(w.find("p").exists()).toBe(false);
  });

  it("shows a + sign and emerald color for a positive change", () => {
    const w = mount(PeriodBadge, { props: { pct: 12 } });
    expect(w.text()).toContain("+12%");
    expect(w.find("p").classes()).toContain("text-emerald-400");
  });

  it("shows a minus sign and red color for a negative change", () => {
    const w = mount(PeriodBadge, { props: { pct: -5 } });
    expect(w.text()).toContain("−5%"); // "−5%" with a real minus, not dropped
    expect(w.find("p").classes()).toContain("text-red-400");
  });

  it("uses neutral slate for a sub-threshold change", () => {
    const w = mount(PeriodBadge, { props: { pct: 0.5 } }); // < default threshold of 1
    expect(w.find("p").classes()).toContain("text-slate-500");
  });

  it("treats exactly zero as a neutral, signless badge", () => {
    const w = mount(PeriodBadge, { props: { pct: 0 } });
    expect(w.find("p").exists()).toBe(true); // 0 is a real value, still renders
    expect(w.text()).toContain("0%");
    expect(w.text()).not.toContain("+0%");
    expect(w.find("p").classes()).toContain("text-slate-500");
  });
});
