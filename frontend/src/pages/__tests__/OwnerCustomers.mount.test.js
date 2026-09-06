/**
 * Mount smoke test for OwnerCustomers.vue (the owner customer-CRM page, ~739 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, an unguarded browser
 * API) was never caught by a test" (this pass already caught a real WaiterPage TDZ
 * white-screen). OwnerCustomers is a busy owner surface — an onMounted that fires
 * GET /owner/customers/, a summary/segment/tier chip trio built from computeds, a
 * debounced-search watcher, and a card v-for whose per-row helpers do real work
 * (initials(), formatAmount() via Intl.NumberFormat, formatDate() via
 * Intl.DateTimeFormat, parseFloat(wallet_balance), avg_review/trust_score
 * .toFixed(1), segment/tier class maps). Mounting runs all of that for real, so a
 * crash in setup() or the initial render fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerReservations.mount.test.js (the closest
 * proven shape: an owner page that imports NOTHING from 'vue-router'):
 *   - shallowMount (auto-stubs the only child component, AppIcon)
 *   - real pinia (the toast store runs for real) + a mocked lib/api
 *   - useI18n mocked to exactly { t } (the page's real destructure — verified: the
 *     page defines its OWN formatAmount/formatDate locally and pulls only `t`)
 *
 * NOT mocked / not needed (all verified against the source):
 *   - vue-router: the page imports nothing from it, so no mock / no vi.hoisted
 *     RouterLink stub is required (that stub is only needed when RouterLink is a
 *     static import, else the hoisted factory hits a "0 test" TDZ).
 *   - lib/adminApi: the page's only api boundary is the default export of lib/api.
 *   - No staleCache / interval / WebSocket / IntersectionObserver / scrollIntoView
 *     is touched at mount (the lone timer is the search-debounce setTimeout, armed
 *     only when searchQuery changes — never at mount). localStorage.clear() is kept
 *     as beforeEach hygiene and afterEach still unmounts, both as cheap insurance.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    // t returns the key verbatim (params, when present, are appended so the raw
    // key path is still asserted-on, e.g. ownerCustomers.resultCount).
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// URL-routed api mock: onMounted fires GET /owner/customers/. Default: everything
// resolves { data: {} } so the empty-state path renders. Tests set _routes to drive
// the loaded path. _routes/_match are plain (not vi.hoisted): they're only read
// lazily inside the vi.fn callback when api.get is invoked at mount — never during
// the hoisted factory's own evaluation — so there is no TDZ.
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

import OwnerCustomers from "../OwnerCustomers.vue";

const mountPage = () =>
  shallowMount(OwnerCustomers, {
    global: {
      // The grant-points modal lives in a <Teleport to="body">; it's closed at
      // mount so nothing teleports, but stub it to keep the render self-contained.
      stubs: { Teleport: { template: "<slot />" } },
    },
  });

// A realistic customer row with the fields the page's own template + per-row
// helpers read: name/segment/type (avatar + badge maps), order_count (tier map),
// total_spend/avg_order_value/currency (formatAmount), wallet_balance string
// (parseFloat), loyalty_points, avg_review/review_count + trust_score (.toFixed(1)),
// last_order_at (formatDate), phone/email (tel:/wa.me/mailto builders), owner_notes.
const customer = (overrides = {}) => ({
  id: 1,
  customer_id: 101,
  name: "Sara Bennani",
  type: "account",
  segment: "returning",
  phone: "+212612345678",
  email: "sara@example.com",
  order_count: 12,
  total_spend: 1450,
  avg_order_value: 120,
  currency: "MAD",
  wallet_balance: "75.50",
  loyalty_points: 340,
  avg_review: 4.5,
  review_count: 8,
  trust_score: 9.2,
  last_order_at: "2026-08-30T18:00:00Z",
  owner_notes: "Prefers spicy",
  ...overrides,
});

describe("OwnerCustomers — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
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
  // The core guard: the onMounted loadCustomers(true) GET + the whole template
  // (header, controls, tier/segment chip computeds, empty state) must render with
  // empty data ({ data: {} } → results: []) and not throw.
  it("mounts with empty data (no customers) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (always rendered, outside every v-if) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerCustomers.title");
    expect(wrapper.text()).toContain("ownerCustomers.kicker");
    // loading resolves false + no filters set → the empty-state branch renders.
    expect(wrapper.text()).toContain("ownerCustomers.emptyState");
  });

  // ── (2) loaded state with a realistic customers payload ────────────────────
  // Drives the card v-for + every per-row helper (initials, segment/tier class
  // maps, formatAmount via Intl.NumberFormat, wallet parseFloat, avg_review/
  // trust_score .toFixed, formatDate) AND the summary chip trio — the own-template
  // paths that only run with a non-empty customers array + a summary object. The
  // second row (anonymous, undefined wallet, null review/trust, order_count 1)
  // exercises the alternate branches of those same guards.
  it("mounts with a loaded customers payload without a crash", async () => {
    _routes = {
      "/owner/customers/": {
        data: {
          results: [
            customer(),
            customer({
              id: 2,
              customer_id: 102,
              name: "Youssef Alami",
              type: "anonymous",
              segment: "new",
              order_count: 1,
              total_spend: 60,
              avg_order_value: 60,
              wallet_balance: undefined,
              loyalty_points: 0,
              avg_review: null,
              review_count: 0,
              trust_score: null,
              owner_notes: "",
            }),
          ],
          has_more: false,
          summary: { total: 2, new: 1, returning: 1, at_risk: 0 },
        },
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerCustomers.title");
    // The card v-for rendered both loaded rows (proves the loaded-list path +
    // every per-row helper ran clean).
    expect(wrapper.text()).toContain("Sara Bennani");
    expect(wrapper.text()).toContain("Youssef Alami");
  });
});
