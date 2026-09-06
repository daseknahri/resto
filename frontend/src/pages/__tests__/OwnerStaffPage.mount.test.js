/**
 * Mount smoke test for OwnerStaffPage.vue (the owner staff-management page,
 * ~683 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, an unguarded browser
 * API) was never caught by a test" (this pass already caught a real WaiterPage
 * TDZ). OwnerStaffPage runs real work at setup: an onMounted(fetchStaff) that
 * reads a localStorage-backed SWR cache then fires GET /owner/staff/, a
 * permDefs computed built from useVocabulary() nouns, per-member card helpers
 * (fmtMoney via Intl.NumberFormat, fmtTime via Intl.DateTimeFormat), and a
 * staff-list v-for. Mounting runs all of that for real, so a crash in setup() or
 * the initial render fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerReservations.mount.test.js (URL-routed
 * api mock + real pinia), which is the closest proven template — an owner page
 * with the same real-composable set and no vue-router import:
 *   - shallowMount (no heavy child components to stub; <Transition> is a Vue
 *     built-in and renders its slot, which is empty at mount since no card is
 *     expanded)
 *   - real pinia (the toast store + the tenant store behind useVocabulary run for
 *     real; businessType is `resolvedMeta?.profile?.business_type || "restaurant"`,
 *     safe with an empty store) + a mocked lib/api
 *   - useI18n mocked to exactly { t, currentLocale } (the page's real destructure;
 *     currentLocale.value feeds the Intl formatters)
 *
 * NOT mocked / left REAL because they are jsdom-safe and never touched at mount:
 *   - useVocabulary (needs only pinia + the mocked useI18n; its nouns are consumed
 *     by the permDefs computed, which is lazily evaluated and only rendered inside
 *     an expanded card — no card is expanded at mount)
 *   - useConfirmModal (module-level refs only; confirm() runs on user action)
 *   - lib/staleCache readCache/writeCache (try/catch localStorage — an empty cache
 *     falls through to the mocked network). localStorage.clear() in beforeEach so
 *     one test's default-view cache write can't leak into the next.
 *
 * The page imports NOTHING from 'vue-router' (verified — no RouterLink either, the
 * share links are plain <a> anchors), so vue-router is NOT mocked and no vi.hoisted
 * RouterLink stub is needed. No poll / interval / observer / WebSocket is registered
 * at mount (the lone setTimeout lives in a click handler), but afterEach still
 * unmounts as hygiene.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    // t returns the key verbatim (params, when present, are appended so the raw
    // key path is still asserted-on). currentLocale.value feeds Intl.*Format.
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: onMounted fires GET /owner/staff/. Default: everything
// resolves { data: {} } so the empty-list path renders (data.results ?? [] → []).
// Tests set _routes to drive the loaded path. post/patch/delete are the
// create/toggle/remove handlers (user actions, not called at mount) — stubbed for
// completeness. _routes/_match are plain (not vi.hoisted): they are only read
// lazily inside the vi.fn callback when api.get is actually invoked — never during
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

import OwnerStaffPage from "../OwnerStaffPage.vue";

const mountPage = () => shallowMount(OwnerStaffPage);

// A realistic staff row with the fields the page's own card-header template +
// computeds read at mount: id, name, email, permissions (defaulted by mapStaff),
// stats.orders_handled/revenue (t(statOrders) + fmtMoney), and shift.is_clocked_in
// / clock_in (the clocked-in badge branch + fmtTime).
const staff = (overrides = {}) => ({
  id: 1,
  name: "Sara Alami",
  email: "sara@example.com",
  permissions: { manage_orders: true, view_revenue: false, edit_menu: false, void_orders: true },
  stats: { orders_handled: 12, revenue: "450.00", last_active: "2026-09-05T13:00:00Z" },
  shift: { is_clocked_in: false, clock_in: null },
  ...overrides,
});

describe("OwnerStaffPage — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // fetchStaff writes the default 7-day view into the REAL localStorage-backed
    // staleCache. Clear it so test 1's write can't be served to test 2 and mask
    // its /owner/staff/ mock payload.
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
  // The core guard: the onMounted cache-read + fetchStaff() and the whole template
  // (header, invite form, staff list) must render with empty data and not throw.
  it("mounts with empty data (no staff) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (always rendered, outside every v-if) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerStaff.title");
    expect(wrapper.text()).toContain("ownerStaff.kicker");
    // Empty results → the staff-list empty-state renders.
    expect(wrapper.text()).toContain("ownerStaff.noStaff");
  });

  // ── (2) loaded state with a realistic staff payload ────────────────────────
  // Drives the staff-list v-for + every per-card helper (member.name/email,
  // t(statOrders) over stats.orders_handled, fmtMoney over stats.revenue, and the
  // clocked-in badge branch → fmtTime over shift.clock_in) — the own-template paths
  // that only run with a non-empty staffList.
  it("mounts with a loaded staff payload without a crash", async () => {
    _routes = {
      "/owner/staff/": {
        data: {
          results: [
            staff(),
            staff({
              id: 2,
              name: "Karim Idrissi",
              email: "karim@example.com",
              stats: { orders_handled: 34, revenue: "1280.50", last_active: null },
              shift: { is_clocked_in: true, clock_in: "2026-09-06T08:00:00Z" },
            }),
          ],
          stats_days: 7,
          currency: "MAD",
        },
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerStaff.title");
    // The v-for rendered the loaded rows (proves the loaded card path + the
    // clocked-in badge branch ran clean).
    expect(wrapper.text()).toContain("Sara Alami");
    expect(wrapper.text()).toContain("Karim Idrissi");
    expect(wrapper.text()).toContain("ownerStaff.clockedIn");
  });
});
