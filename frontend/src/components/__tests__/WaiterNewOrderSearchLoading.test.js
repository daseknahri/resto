/**
 * WAITER-SEARCH-LOADING — the dish search must not flash a false "No results"
 * while a category is still lazy-loading.
 *
 * Regression for the daily-use bug where a waiter searching for a real dish that
 * lives in a not-yet-loaded category briefly saw "No matching dishes" and could
 * wrongly conclude the dish isn't on the menu. WaiterNewOrder.vue now sets a
 * `searchLoading` flag while onSearch's background category loads are in flight
 * and gates the empty state on it. The genuine "nothing matched" case (search
 * done, full menu loaded) is preserved.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { ref } from "vue";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Deterministic i18n + Teleport stub so the modal renders inline in jsdom.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k, currentLocale: ref("en") }),
}));

vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(async () => ({ data: [] })),
    post: vi.fn(async () => ({ data: {} })),
  },
}));

vi.mock("../../lib/idempotency", () => ({ newIdempotencyKey: () => "idem-key" }));

import api from "../../lib/api";
import WaiterNewOrder from "../WaiterNewOrder.vue";
import { useMenuStore } from "../../stores/menu";

const STEAK = { slug: "steak", name: "Steak", price: 50, currency: "MAD", options: [], option_groups: [] };
const SALAD = { slug: "salad", name: "Salad", price: 10, currency: "MAD", options: [], option_groups: [] };

const mountModal = (props = {}) =>
  mount(WaiterNewOrder, {
    props,
    global: { stubs: { Teleport: true, AppIcon: true } },
  });

describe("WaiterNewOrder — search lazy-load loading state", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    api.get.mockReset();
    api.get.mockResolvedValue({ data: [] });
    localStorage.clear();
  });

  it("suppresses the false 'No results' the instant a search needs a lazy load", async () => {
    const menu = useMenuStore();
    menu.categories = [
      { slug: "mains", name: "Mains", course: 0 },
      { slug: "starters", name: "Starters", course: 0 },
    ];
    // Only 'mains' preloaded; 'starters' must be lazy-fetched during search.
    menu.dishes = { mains: [STEAK] };

    const w = mountModal();
    await flushPromises();

    // Waiter searches for a dish that lives in the not-yet-loaded category.
    w.vm.search = "Salad";
    w.vm.onSearch();

    // Synchronous guard: loading is on before the debounce even fires, so the
    // empty state can't flash while the real match is still on the wire.
    expect(w.vm.searchLoading).toBe(true);
    await w.vm.$nextTick();
    expect(w.text()).not.toContain("waiterPage.noResults");
  });

  it("clears the flag and reveals the match once the lazy load resolves", async () => {
    const menu = useMenuStore();
    menu.categories = [
      { slug: "mains", name: "Mains", course: 0 },
      { slug: "starters", name: "Starters", course: 0 },
    ];
    menu.dishes = { mains: [STEAK] };
    api.get.mockImplementation((url, cfg) => {
      if (url === "/dishes/" && cfg?.params?.category === "starters") {
        return Promise.resolve({ data: [SALAD] });
      }
      return Promise.resolve({ data: [] });
    });

    const w = mountModal();
    await flushPromises();

    w.vm.search = "Salad";
    w.vm.onSearch();
    expect(w.vm.searchLoading).toBe(true);

    // Let the 200ms debounce fire, then flush the fetch + the allSettled it awaits.
    await new Promise((r) => setTimeout(r, 250));
    await flushPromises();

    // Flag is not stuck true; the freshly-loaded dish now shows.
    expect(w.vm.searchLoading).toBe(false);
    expect(w.text()).toContain("Salad");
    expect(w.text()).not.toContain("waiterPage.noResults");
  });

  it("still shows the genuine 'No results' when the full menu is loaded and nothing matches", async () => {
    const menu = useMenuStore();
    menu.categories = [{ slug: "mains", name: "Mains", course: 0 }];
    menu.dishes = { mains: [STEAK] };   // fully loaded — nothing to lazy-load

    const w = mountModal();
    await flushPromises();

    w.vm.search = "nothing-here";
    w.vm.onSearch();

    // No background load needed → flag stays off → the honest empty state shows.
    expect(w.vm.searchLoading).toBe(false);
    await w.vm.$nextTick();
    expect(w.text()).toContain("waiterPage.noResults");
  });
});
