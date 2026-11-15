/**
 * Mount test for OwnerDashboardInsights.vue — G4b-E (B-37).
 *
 * WHY: when the primary /owner/dashboard/ fetch failed but the fallback
 * /analytics/summary/ succeeded, the component updated its own tiles but never
 * emitted "data" — so OwnerAnalytics.onInsightsData never fired and the parent
 * KPI grid rendered a false "0 / MAD 0" with no error flag. Mounting the REAL
 * component exercises the primary-fails → fallback-succeeds path end to end.
 *
 * Pattern-faithful to components/__tests__/OwnerDashboardDishPanel.mount.test.js:
 *   - mount (children AppIcon + PeriodBadge stubbed) + real pinia + mocked lib/api
 *   - useI18n mocked (key verbatim → assertions read the raw key)
 *   - staleCache left REAL (jsdom-safe, localStorage-backed); beforeEach clears
 *     localStorage so no cached payload leaks between tests.
 *   - useVocabulary mocked (the real one reads the tenant store; the test only
 *     needs stable catalog/item labels).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatNumber: (v) => String(v),
    formatCurrency: (v, c) => `${v} ${c}`,
  }),
}));

vi.mock("../../composables/useVocabulary", () => ({
  useVocabulary: () => ({
    catalog: { value: "Menu" },
    itemSingular: { value: "dish" },
    itemPlural: { value: "dishes" },
  }),
}));

vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import api from "../../lib/api";
import OwnerDashboardInsights from "../OwnerDashboardInsights.vue";

const fallbackPayload = {
  analytics_summary: {
    counts: { menu_view: 10, dish_view: 5, order_handoff_click: 2, checkout_click: 1 },
    prev_counts: {},
    top_categories: [],
    top_dishes: [],
    interaction_rate_pct: 12.5,
  },
};

const mountInsights = () =>
  mount(OwnerDashboardInsights, {
    global: {
      stubs: {
        AppIcon: { template: "<span />" },
        PeriodBadge: { template: "<span />" },
      },
    },
  });

describe("OwnerDashboardInsights — G4b-E (B-37 fallback emit)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    api.get.mockImplementation(() => Promise.resolve({ data: {} }));
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // B-37: primary down + fallback up → the fallback payload IS emitted (with
  // partial: true), the component's own tiles show the real counts, and no
  // "error" is emitted — the parent's onInsightsData fires instead of the KPI
  // grid false-zeroing.
  it("emits the fallback payload (partial) when primary fails but /analytics/summary/ succeeds", async () => {
    api.get.mockImplementation((url) =>
      url.includes("/owner/dashboard/")
        ? Promise.reject(new Error("dashboard down"))
        : url.includes("/analytics/summary/")
          ? Promise.resolve({ data: fallbackPayload })
          : Promise.resolve({ data: {} }),
    );

    wrapper = mountInsights();
    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const dataEmits = wrapper.emitted("data");
    expect(dataEmits).toBeTruthy();
    expect(dataEmits.length).toBeGreaterThan(0);
    const payload = dataEmits[0][0];
    expect(payload.partial).toBe(true);
    expect(payload.analytics_summary.counts.menu_view).toBe(10);
    expect(wrapper.emitted("error")).toBeFalsy();
    // The component's own tiles render the fallback counts (not zeros).
    expect(wrapper.text()).toContain("10");
    expect(wrapper.text()).not.toContain("ownerHome.analyticsLoadError");
  });

  // Regression guard: primary AND fallback both down (no cache) → the error
  // emit + error UI still fire, exactly as before.
  it("emits error (and shows the error UI) when primary AND fallback both fail", async () => {
    api.get.mockImplementation(() => Promise.reject(new Error("all down")));

    wrapper = mountInsights();
    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.emitted("error")).toBeTruthy();
    expect(wrapper.emitted("data")).toBeFalsy();
    expect(wrapper.text()).toContain("ownerHome.analyticsLoadError");
  });

  // Regression guard: primary success → "data" is emitted WITHOUT the partial
  // marker, so the parent treats it as complete revenue data.
  it("emits complete (non-partial) data when the primary fetch succeeds", async () => {
    api.get.mockImplementation((url) =>
      url.includes("/owner/dashboard/")
        ? Promise.resolve({
            data: {
              analytics_summary: fallbackPayload.analytics_summary,
              revenue_summary: { currency: "MAD", daily: [] },
            },
          })
        : Promise.resolve({ data: {} }),
    );

    wrapper = mountInsights();
    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const dataEmits = wrapper.emitted("data");
    expect(dataEmits).toBeTruthy();
    expect(dataEmits.length).toBeGreaterThan(0);
    expect(dataEmits[0][0].partial).toBeUndefined();
    expect(wrapper.emitted("error")).toBeFalsy();
  });
});
