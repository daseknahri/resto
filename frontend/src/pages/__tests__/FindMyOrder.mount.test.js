/**
 * Mount smoke test for FindMyOrder.vue (the customer order-lookup page, ~197 lines).
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined-map
 * access, a bad import, an unguarded browser API) was never caught by a test".
 * Mounting the page runs its real setup() — so any such crash fails CI here
 * instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OrderStatus.mount.test.js and
 * SuperAppHub.mount.test.js:
 *   - shallowMount + real pinia (setActivePinia(createPinia()) in beforeEach)
 *   - URL-routed lib/api mock (default { data: {} }; per-test _routes)
 *   - useI18n mocked to return deterministic keys
 *
 * IDENTIFIERS (verified against source):
 *   - useI18n destructure is { t, formatPrice, currentLocale } — the mock returns
 *     all three. formatPrice powers formatTotal(); currentLocale.value feeds
 *     Intl.DateTimeFormat in formatDate().
 *   - the api boundary is lib/api (default import) — mocked at ../../lib/api.
 *   - <RouterLink> is used in the results list (lines ~88/113) but is NOT imported
 *     from 'vue-router' (the only script-setup imports are ref, useI18n, api). It
 *     resolves as a GLOBAL component, so it is handled with a global.stubs.RouterLink
 *     pass-through — NO vi.hoisted, and NO vi.mock('vue-router') (the page imports
 *     nothing from vue-router: no useRoute, no useRouter, no RouterLink).
 *   - NOTHING fetches at mount: there is no onMounted. The single GET
 *     (/orders/by-phone/?phone=...) fires only from search() on form submit. So the
 *     default mount just renders the empty search form — still a valid smoke test.
 *   - no intervals / observers / scrollIntoView → no timer cleanup needed.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatPrice: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: the only GET is /orders/by-phone/, fired from search() on
// submit (never at mount). Default resolves empty so the untouched form renders;
// a test that drives the search sets _routes to return a found order.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import FindMyOrder from "../FindMyOrder.vue";

const mountPage = () =>
  shallowMount(FindMyOrder, {
    global: {
      // RouterLink is a GLOBAL component here (not imported) → pass-through stub so
      // the results-list <RouterLink> renders its slot content. No vi.hoisted needed
      // (the stub is not referenced inside a vi.mock factory).
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
      },
    },
  });

describe("FindMyOrder — mount smoke", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  // ── (1) default render (empty search form) ────────────────────────────────
  // The core guard: setup() must not throw, and the page's own header + search
  // form must render. Nothing fetches at mount, so this exercises the whole
  // synchronous setup (refs, the status/class/label maps, search closure) plus
  // the static template.
  it("mounts the empty search form without a setup() crash", async () => {
    let wrapper;
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // h1 heading (t("orderStatus.findMyOrderTitle")) + the submit button
    // (t("orderStatus.findMyOrderSearch")) — stable own-template anchors.
    expect(wrapper.text()).toContain("orderStatus.findMyOrderTitle");
    expect(wrapper.text()).toContain("orderStatus.findMyOrderSearch");
  });

  // ── (2) found-results state (search on submit) ────────────────────────────
  // Drives the lookup for real: set the phone ref to a valid (>= 6 digit) number,
  // route /orders/by-phone/ to a found order, and invoke search(). This runs the
  // results v-for → RouterLink card, statusLabel/statusClass/fulfillmentLabel map
  // lookups, formatDate (Intl.DateTimeFormat + currentLocale) and formatTotal
  // (formatPrice) against a real payload — the own-template paths a bare form never
  // reaches. <script setup> bindings (phone, search) are reachable via wrapper.vm.
  it("renders a found order after a submitted search", async () => {
    _routes = {
      "/orders/by-phone/": {
        data: {
          results: [
            {
              order_number: "A123",
              status: "preparing",
              fulfillment_type: "delivery",
              created_at: new Date("2026-09-06T10:00:00Z").toISOString(),
              items_count: 2,
              total: "75.00",
            },
          ],
        },
      },
    };

    const wrapper = mountPage();
    await flushPromises();

    wrapper.vm.phone = "0612345678";
    await wrapper.vm.search();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // The found order number rendered into the results card (#A123).
    expect(wrapper.text()).toContain("A123");
    // statusLabel("preparing") → t("orderStatus.statusPreparing") — proves the
    // loaded status ran through the label + class maps.
    expect(wrapper.text()).toContain("orderStatus.statusPreparing");
  });
});
