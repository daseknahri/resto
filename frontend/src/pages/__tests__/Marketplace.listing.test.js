/**
 * Marketplace.vue listing correctness:
 *   - L8: an out-of-order response must never replace the results of a newer search /
 *     filter (and a stale load-more page must never be appended to a newer result set).
 *   - M12: a card says "Free delivery" only when delivery is genuinely free — a
 *     distance-priced restaurant (base + per-km) has a 0 flat fee yet charges at checkout.
 *
 * Mount approach mirrors Marketplace.loadMore.test.js (api / i18n / router / toast mocked).
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

const mockToastShow = vi.fn();
vi.mock("../../stores/toast", () => ({
  useToastStore: () => ({ show: mockToastShow }),
}));

import api from "../../lib/api";
import Marketplace from "../Marketplace.vue";

const restaurant = (slug, over = {}) => ({
  slug,
  name: `Place ${slug}`,
  cuisine_type: "",
  city: "Casablanca",
  tagline: "",
  is_open: true,
  logo_url: null,
  business_type: "restaurant",
  delivery_enabled: false,
  delivery_fee: "0",
  delivery_minimum_order: "0",
  rating_average: null,
  rating_count: 0,
  price_tier: null,
  distance_km: null,
  flash_sale_active: false,
  promo_badge: null,
  tags: [],
  business_hours_schedule: null,
  ...over,
});

const page = (restaurants, over = {}) => ({
  data: { restaurants, has_more: false, page: 1, filters: { cities: [], cuisines: [], tags: [] }, ...over },
});

const deferred = () => {
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
};

const mountWith = async (initialResponse) => {
  setActivePinia(createPinia());
  api.get.mockResolvedValueOnce(initialResponse);
  const wrapper = mount(Marketplace, {
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
      },
    },
  });
  await flushPromises();
  return wrapper;
};

describe("Marketplace — listing fetch race (L8)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("a slow response for an earlier search never replaces the newer one", async () => {
    const wrapper = await mountWith(page([restaurant("initial")]));

    const slowPiz = deferred();
    const fastPizza = deferred();
    api.get.mockReturnValueOnce(slowPiz.promise).mockReturnValueOnce(fastPizza.promise);

    // Fire two filter fetches back to back (as two debounce ticks would).
    const first = wrapper.vm.fetchRestaurants();  // "piz"
    const second = wrapper.vm.fetchRestaurants(); // "pizza"

    fastPizza.resolve(page([restaurant("pizza-place")]));
    await second;
    await flushPromises();
    expect(wrapper.text()).toContain("Place pizza-place");

    // The stale "piz" answer lands last — it must be ignored.
    slowPiz.resolve(page([restaurant("stale-piz")]));
    await first;
    await flushPromises();
    expect(wrapper.text()).toContain("Place pizza-place");
    expect(wrapper.text()).not.toContain("Place stale-piz");
    expect(wrapper.vm.loading).toBe(false);
  });

  it("keeps the spinner while the newest request is still in flight", async () => {
    const wrapper = await mountWith(page([restaurant("initial")]));
    const older = deferred();
    const newer = deferred();
    api.get.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);

    const first = wrapper.vm.fetchRestaurants();
    const second = wrapper.vm.fetchRestaurants();
    older.resolve(page([restaurant("old")]));
    await first;
    expect(wrapper.vm.loading).toBe(true); // the stale request doesn't own the spinner

    newer.resolve(page([restaurant("new")]));
    await second;
    expect(wrapper.vm.loading).toBe(false);
  });

  it("drops a load-more page that belongs to a replaced result set", async () => {
    const wrapper = await mountWith(page([restaurant("p1")], { has_more: true }));
    const page2 = deferred();
    api.get.mockReturnValueOnce(page2.promise);
    const loadMore = wrapper.vm.loadMoreRestaurants();

    api.get.mockResolvedValueOnce(page([restaurant("filtered")]));
    await wrapper.vm.fetchRestaurants(); // filters changed meanwhile
    page2.resolve(page([restaurant("old-page-2")], { page: 2 }));
    await loadMore;
    await flushPromises();

    expect(wrapper.text()).toContain("Place filtered");
    expect(wrapper.text()).not.toContain("Place old-page-2");
  });
});

describe("Marketplace — card delivery pricing (M12)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const cardText = (wrapper, slug) => {
    const card = wrapper.findAll("li").find((li) => li.text().includes(`Place ${slug}`));
    expect(card).toBeTruthy();
    return card.text();
  };

  // "Free delivery" itself (not the "Free over X" threshold note).
  const FREE_DELIVERY = /marketplace\.freeDelivery(?!Over)/;

  it("never advertises free delivery for a distance-priced restaurant", async () => {
    const wrapper = await mountWith(page([
      restaurant("kmbase", { delivery_enabled: true, delivery_fee: "0", delivery_base_fee: "8.00", delivery_per_km: "2.50", delivery_free_over: "150.00" }),
      restaurant("kmonly", { delivery_enabled: true, delivery_fee: "0", delivery_base_fee: "0", delivery_per_km: "3.00", delivery_free_over: "0" }),
      restaurant("flat", { delivery_enabled: true, delivery_fee: "15.00", delivery_base_fee: "0", delivery_per_km: "0", delivery_free_over: "100.00" }),
      restaurant("free", { delivery_enabled: true, delivery_fee: "0", delivery_base_fee: "0", delivery_per_km: "0", delivery_free_over: "0" }),
    ]));

    const kmBase = cardText(wrapper, "kmbase");
    expect(kmBase).not.toMatch(FREE_DELIVERY);
    expect(kmBase).toContain('marketplace.deliveryFrom({"amount":"8.00"})');
    expect(kmBase).toContain('marketplace.freeDeliveryOver({"amount":"150.00"})');

    const kmOnly = cardText(wrapper, "kmonly");
    expect(kmOnly).toContain("marketplace.deliveryByDistance");
    expect(kmOnly).not.toMatch(FREE_DELIVERY);

    const flat = cardText(wrapper, "flat");
    expect(flat).toContain("marketplace.deliveryFee: 15.00");
    expect(flat).toContain('marketplace.freeDeliveryOver({"amount":"100.00"})');

    const free = cardText(wrapper, "free");
    expect(free).toMatch(FREE_DELIVERY);
    expect(free).not.toContain("marketplace.freeDeliveryOver");
  });
});
