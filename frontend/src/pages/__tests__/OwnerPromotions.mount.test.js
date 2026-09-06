/**
 * Mount smoke test for OwnerPromotions.vue (the owner promotions / marketing page,
 * ~793 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, an unguarded browser
 * API) was never caught by a test". OwnerPromotions is a busy owner surface — an
 * onMounted that fires four GETs (/owner/promotions/, /owner/flash-sales/,
 * /happy-hours/, /categories/), a localStorage-backed SWR cache read on the
 * promotions fetch, an { immediate: true } watch that hydrates the win-back +
 * referral forms from tenant.meta, i18n-driven computeds (DAYS / promoTypes /
 * HH_DAYS) evaluated as drawer props, and three list v-fors (promotions / flash
 * sales / happy-hour rules). Mounting runs all of that for real, so a crash in
 * setup() or the initial render fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerReservations.mount.test.js +
 * pages/__tests__/OwnerHome.mount.test.js (URL-routed api mock + real pinia):
 *   - shallowMount (auto-stubs the heavy children: OwnerPromotionCard,
 *     OwnerPromotionsEmptyState, OwnerFlashSaleOptInCard, OwnerHappyHourRuleCard,
 *     OwnerWinbackCard, OwnerReferralCard, and the two form drawers)
 *   - real pinia (the tenant + toast stores run for real) + a mocked lib/api
 *   - useI18n mocked to exactly { t, currentLocale } (the page's real destructure)
 *
 * NOT mocked / left REAL because they are jsdom-safe and never touched at mount:
 *   - useConfirmModal (module-level refs only; confirm() runs on user action, not
 *     at setup)
 *   - lib/staleCache readCache/writeCache (try/catch localStorage — an empty cache
 *     falls through to the mocked network). localStorage.clear() in beforeEach so
 *     one test's promotions cache write can't leak into the next and mask its
 *     /owner/promotions/ mock payload.
 *
 * The page imports NOTHING from 'vue-router' (verified via grep), so vue-router is
 * NOT mocked and no vi.hoisted RouterLink stub is needed. There is no poll /
 * interval / observer / WebSocket registered at mount, but afterEach still unmounts
 * as hygiene.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    // t returns the key verbatim (params, when present, are appended so the raw
    // key path is still asserted-on). currentLocale is the page's real destructure
    // (read by fmtFlashDate's Intl.DateTimeFormat, which only runs on child render).
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: onMounted fires GET /owner/promotions/, /owner/flash-sales/,
// /happy-hours/ and /categories/. Default: everything resolves { data: {} } so the
// empty path renders. Tests set _routes to drive the loaded path.
// _routes/_match are plain (not vi.hoisted): they are only read lazily inside the
// vi.fn callback when api.get is actually invoked at mount — never during the
// hoisted factory's own evaluation — so there is no TDZ.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import OwnerPromotions from "../OwnerPromotions.vue";

const mountPage = () => shallowMount(OwnerPromotions);

// A realistic promo row with the fields the page's own template + promoLabel read:
// id (v-for key), name, promo_type/discount_value, code, is_active, days/time/date
// window. promotions.value = res.data directly, so the payload must be an array.
const promo = (overrides = {}) => ({
  id: 1,
  name: "Summer 20%",
  description: "Twenty percent off",
  code: "SUMMER20",
  promo_type: "percentage",
  discount_value: "20",
  min_order_amount: "0",
  days: [],
  time_start: "",
  time_end: "",
  active_from: null,
  active_until: null,
  max_uses: null,
  is_active: true,
  ...overrides,
});

// A realistic platform flash-sale row (Array.isArray-guarded fetch): id (v-for key),
// name, opted_in, and the ISO window fmtFlashDate formats on child render.
const flashSale = (overrides = {}) => ({
  id: 10,
  name: "Weekend Flash",
  opted_in: false,
  starts_at: "2026-09-12T18:00:00Z",
  ends_at: "2026-09-12T22:00:00Z",
  discount_percent: 25,
  ...overrides,
});

// A realistic happy-hour rule (Array.isArray-guarded fetch): id (v-for key), name,
// percent_off, start/end_time (isOvernightRule reads these), days, category_ids.
const happyHour = (overrides = {}) => ({
  id: 5,
  name: "Afternoon Lull",
  percent_off: 20,
  start_time: "15:00",
  end_time: "17:00",
  days: [0, 1, 2],
  category_ids: [],
  is_active: true,
  ...overrides,
});

describe("OwnerPromotions — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // fetchPromotions writes the promotions list into the REAL localStorage-backed
    // staleCache. Clear it so test 1's write can't be served to test 2 and mask its
    // /owner/promotions/ mock payload.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) empty / default mount ──────────────────────────────────────────────
  // The core guard: the onMounted cache-read + four GETs, the { immediate: true }
  // tenant.meta watch, the DAYS/promoTypes/HH_DAYS computeds (evaluated as drawer
  // props), and the whole template must render with empty data and not throw.
  it("mounts with empty data (no promotions) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (always rendered, outside every v-if) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerPromotions.title");
    expect(wrapper.text()).toContain("ownerPromotions.kicker");
    // Happy Hours section header always renders (its own-template section ran).
    expect(wrapper.text()).toContain("happyHour.kicker");
    // No flash sales loaded → the platform flash-sale opt-in section is absent.
    expect(wrapper.text()).not.toContain("ownerPromotions.flashKicker");
  });

  // ── (2) loaded state with realistic payloads ───────────────────────────────
  // Drives all three list v-fors (promotions / flash sales / happy-hour rules)
  // with real rows and exercises the platform flash-sale section, whose header key
  // (ownerPromotions.flashKicker) renders from the page's OWN template only once a
  // flash sale has loaded — the loaded signal this case asserts on.
  it("mounts with loaded promotions + flash sale + happy hour without a crash", async () => {
    _routes = {
      "/owner/promotions/": {
        data: [
          promo(),
          promo({ id: 2, name: "Free Delivery Fri", promo_type: "free_delivery", code: "" }),
        ],
      },
      "/owner/flash-sales/": { data: [flashSale()] },
      "/happy-hours/": { data: [happyHour()] },
      "/categories/": { data: [{ id: 1, name: "Drinks" }] },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerPromotions.title");
    // Flash sale loaded → the opt-in section rendered from the page's own template
    // (flashSalesLoaded && flashSales.length), proving the loaded path ran clean.
    expect(wrapper.text()).toContain("ownerPromotions.flashKicker");
  });
});
