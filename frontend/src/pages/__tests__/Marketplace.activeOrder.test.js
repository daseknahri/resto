/**
 * Marketplace.vue — the "track your order" active-order strip must survive a TRANSIENT
 * validation failure. For an anonymous customer this localStorage strip is their ONLY
 * re-entry to order tracking, so a 5xx / network blip on mount must NOT wipe it; only a
 * real 404 (the order is genuinely gone) clears it.
 *
 * Mocks mirror Marketplace.loadMore.test.js (the proven-clean mount setup for this page):
 * api / useI18n / vue-router / businessHours / services / toast.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

vi.mock("../../lib/api", () => ({
  default: { get: vi.fn() },
}));

vi.mock("vue-router", () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

vi.mock("../../lib/businessHours", () => ({
  getNextOpenInfo: () => null,
}));

vi.mock("../../lib/services", () => ({
  SERVICES: [],
}));

vi.mock("../../stores/toast", () => ({
  useToastStore: () => ({ show: vi.fn() }),
}));

import api from "../../lib/api";
import Marketplace from "../Marketplace.vue";

// Payload for the fetchRestaurants() call that fires alongside validateActiveOrder() at mount.
const RESTAURANTS_OK = {
  data: {
    restaurants: [],
    has_more: false,
    page: 1,
    filters: { cities: [], cuisines: [], tags: [] },
  },
};

const seedActiveOrder = () => {
  localStorage.setItem("mktLastOrderNumber", "X123");
  localStorage.setItem("mktLastOrderAt", String(Date.now())); // within the 2 h window
  localStorage.setItem("mktLastOrderSlug", "demo");
};

const mountMarketplace = () =>
  mount(Marketplace, {
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
      },
    },
  });

describe("Marketplace — active-order strip transient-error resilience", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("keeps the strip's localStorage on a transient (500) validation failure", async () => {
    seedActiveOrder();
    api.get.mockImplementation((url) =>
      String(url).includes("/order/")
        ? Promise.reject({ response: { status: 500 } })
        : Promise.resolve(RESTAURANTS_OK),
    );

    mountMarketplace();
    await flushPromises();

    // A blip must NOT wipe the anonymous customer's only re-entry to order tracking.
    expect(localStorage.getItem("mktLastOrderNumber")).toBe("X123");
    expect(localStorage.getItem("mktLastOrderSlug")).toBe("demo");
  });

  it("clears the strip only on a real 404 (the order is gone)", async () => {
    seedActiveOrder();
    api.get.mockImplementation((url) =>
      String(url).includes("/order/")
        ? Promise.reject({ response: { status: 404 } })
        : Promise.resolve(RESTAURANTS_OK),
    );

    mountMarketplace();
    await flushPromises();

    expect(localStorage.getItem("mktLastOrderNumber")).toBeNull();
    expect(localStorage.getItem("mktLastOrderSlug")).toBeNull();
  });
});
