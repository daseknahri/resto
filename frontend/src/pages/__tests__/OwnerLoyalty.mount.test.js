/**
 * Mount smoke test for OwnerLoyalty.vue (the owner loyalty-programme config page,
 * ~530 lines: points/earn/redeem config, tier progression, bonus events, live
 * preview computeds, and an enrollment-stats card).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, an unguarded browser
 * API) was never caught by a test". OwnerLoyalty runs real work at mount: an
 * onMounted(fetchConfig) that reads a localStorage-backed SWR cache then GETs
 * /owner/loyalty/, applyConfig() spreading the response into a reactive form, two
 * preview computeds (previewEarn / previewRedeem doing Number()/toFixed math), and
 * a template with loading/error/loaded branches plus a conditional tier section
 * and a conditional stats card (stats.total_points_issued.toLocaleString()).
 * Mounting runs all of that for real, so a crash in setup() or the initial render
 * fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerReservations.mount.test.js (the
 * no-vue-router owner-page shape — URL-routed api mock + real pinia):
 *   - shallowMount (the page imports no child components, so this is equivalent to
 *     mount here — kept for consistency with the other owner-page smoke tests)
 *   - real pinia (the toast store runs for real; it is only touched inside save(),
 *     never at mount) + a mocked lib/api
 *   - useI18n mocked to exactly { t } (the page's real destructure — verified)
 *
 * NOT mocked / left REAL because they are jsdom-safe and never crash at mount:
 *   - lib/staleCache readCache/isFresh/writeCache (try/catch localStorage — an empty
 *     cache falls through to the mocked network). localStorage.clear() in beforeEach
 *     so one test's config cache write can't leak into the next and mask its payload.
 *
 * The page imports NOTHING from 'vue-router' (verified — only useI18n, useToastStore,
 * lib/api, lib/staleCache), so vue-router is NOT mocked and no vi.hoisted RouterLink
 * stub is needed. There is no poll / interval / observer / WebSocket / scrollIntoView
 * registered at mount (onActivated is guarded and does not fire without <KeepAlive>),
 * but afterEach still unmounts as hygiene.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    // t returns the key verbatim (params, when present, are appended so the raw
    // key path is still asserted-on — the preview computeds pass params).
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// URL-routed api mock: onMounted fires GET /owner/loyalty/ (save() PATCHes the same
// URL, but that only runs on user action). Default: everything resolves { data: {} }
// so the default/empty-config path renders. Tests set _routes to drive the loaded
// path. _routes/_match are plain (not vi.hoisted): they are only read lazily inside
// the vi.fn callback when api.get is actually invoked at mount — never during the
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
    put: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import OwnerLoyalty from "../OwnerLoyalty.vue";

const mountPage = () => shallowMount(OwnerLoyalty);

// A realistic loyalty-config payload with the fields applyConfig() spreads into the
// reactive form + the optional stats card the template reads:
//   points config (points_per_unit / redeem_threshold / points_value),
//   tier progression (tier_enabled + silver/gold thresholds & multipliers),
//   bonus events (first_order / birthday), and enrollment stats.
const loyaltyConfig = (overrides = {}) => ({
  enabled: true,
  points_per_unit: 10,
  redeem_threshold: 100,
  points_value: "0.05",
  tier_enabled: true,
  tier_silver_threshold: 500,
  tier_gold_threshold: 2000,
  tier_silver_multiplier: "1.50",
  tier_gold_multiplier: "2.00",
  first_order_bonus_points: 50,
  birthday_bonus_points: 100,
  stats: { enrolled_customers: 37, total_points_issued: 12500 },
  ...overrides,
});

describe("OwnerLoyalty — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // fetchConfig writes the loaded config into the REAL localStorage-backed
    // staleCache. Clear it so test 2's write can't be served to a later run and
    // mask the /owner/loyalty/ mock payload (the cache is host+locale scoped, TTL
    // 10 min — well within a test run).
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
  // The core guard: the onMounted cache-read + fetchConfig() GET resolves empty,
  // applyConfig({}) spreads undefined over the form defaults, and the whole
  // loaded-branch template (how-it-works + settings card + preview computeds) must
  // render without throwing. stats stays null → the stats card stays hidden.
  it("mounts with empty/default config without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (always rendered, outside every v-if) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerLoyalty.title");
    expect(wrapper.text()).toContain("ownerLoyalty.kicker");
    // loading/error resolved false → the v-else content rendered (how-it-works is
    // an always-on heading inside that branch, proving the loaded path ran clean).
    expect(wrapper.text()).toContain("ownerLoyalty.howItWorksTitle");
  });

  // ── (2) loaded state with a realistic loyalty config ───────────────────────
  // Drives applyConfig() spreading a full payload into the form, the conditional
  // tier section (tier_enabled: true → the silver/gold inputs + labels render), and
  // the stats card (enrolled_customers > 0 → the count + total_points_issued
  // .toLocaleString() render) — the own-template paths that only run with a loaded,
  // tiers-on, stats-present config.
  it("mounts with a loaded loyalty config (tiers on + stats) without a crash", async () => {
    _routes = {
      "/owner/loyalty/": { data: loyaltyConfig() },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerLoyalty.title");
    // tier_enabled from the payload → the conditional tier branch rendered.
    expect(wrapper.text()).toContain("ownerLoyalty.tierSilverThresholdLabel");
    // stats card rendered the loaded enrollment count (a value straight from the
    // payload, proving applyConfig fed the template).
    expect(wrapper.text()).toContain("37");
  });
});
