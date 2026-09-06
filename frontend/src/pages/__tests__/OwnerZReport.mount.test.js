/**
 * Mount smoke test for OwnerZReport.vue (the owner Z-report / end-of-day close,
 * ~668 lines). A MONEY / reporting surface: sales totals, payment-method
 * breakdown (cash / wallet), tips, refunds, discounts, voids, comps, by-staff,
 * food-cost, labor, and cash-drawer reconciliation.
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined-map
 * access, an unguarded browser API) was never caught by a test". Mounting runs
 * the real setup() + onMounted(fetchReport) — which fires two GETs
 * (/owner/z-report/ + /owner/drawer/history/), then renders a dozen money
 * computeds/formatters and several v-for tables — so a crash in any of it fails
 * CI here instead of white-screening the owner's day-close in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerWallet.mount.test.js (the sibling
 * money page: URL-routed lib/api mock + real pinia + a page-local Intl money
 * formatter, so loaded assertions check money DIGITS, never symbol placement):
 *   - shallowMount (auto-stubs the one child component, AppIcon) + real pinia
 *   - useI18n mocked to exactly { t } (the page's real destructure — verified)
 *   - Transition stubbed to render its slot, so the voids/comps/labor tables
 *     (each collapsible section is wrapped in <Transition>) render synchronously
 *     and a crash inside them is caught too.
 *
 * NOT mocked / left REAL because they are jsdom-safe and never touched at mount:
 *   - useConfirmModal (module-level refs only; confirm() runs on user action,
 *     inside closeShiftAndPrint — never at setup)
 *   - the tenant + toast stores (real pinia). fmtMoney reads
 *     tenant.resolvedMeta?.profile?.currency (optional-chained → null in jsdom →
 *     falls back to 'MAD'), matching the OwnerWallet precedent.
 *   - localStorage.clear() in beforeEach is hygiene parity with the sibling
 *     mount-smoke tests (the tenant store getters touch the staleCache-backed
 *     meta cache).
 *
 * The page imports NOTHING from 'vue-router' (verified — no import, no
 * <router-link>), so vue-router is NOT mocked and no vi.hoisted RouterLink stub
 * is needed. No interval / poll / visibilitychange / WebSocket / observer is
 * registered at mount (onMounted only calls fetchReport); afterEach still
 * unmounts as hygiene. window.print is referenced only in user-action handlers
 * (printReport / closeShiftAndPrint), never on a mount path — it's stubbed
 * defensively so a future mount-path refactor can't hit jsdom's unimplemented
 * window.print.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    // t returns the key verbatim (params, when present, are appended so the raw
    // key path is still asserted-on). The page defines its own money formatter
    // (fmtMoney via Intl.NumberFormat), so no formatCurrency is destructured.
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// URL-routed lib/api mock. onMounted → fetchReport fires:
//   GET /owner/z-report/       (the report; report.value = resp.data)
//   GET /owner/drawer/history/ (drawer sessions; drawerSessions = data.sessions ?? [])
// Default resolves { data: {} }. NOTE: for the z-report route, { data: {} } would
// set report.value = {} (truthy) and the template's `report.window.service_day`
// would then throw — {} is not a realistic API response. The genuine "no data"
// state is `report` staying falsy, so the empty case routes z-report to
// { data: null }. _routes/_match are plain (not vi.hoisted): read lazily inside
// the vi.fn only when api.get runs at mount — never during a hoisted factory — so
// there is no TDZ.
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

import OwnerZReport from "../OwnerZReport.vue";

const mountReport = () =>
  shallowMount(OwnerZReport, {
    global: {
      stubs: {
        // The voids / comps / labor collapsible sections are each wrapped in a
        // <Transition name="ui-fade">; render the slot directly so their content
        // (and the fmtMoney calls inside them) appears deterministically.
        Transition: { template: "<slot />" },
      },
    },
  });

// A realistic, fully-populated Z-report payload — every field the template reads
// under v-if="report", so the loaded render path runs end-to-end with no missing
// access. Amounts are strings (the backend's decimal serialization) and < 1000 so
// Intl adds no grouping separators, keeping DIGIT assertions locale-robust.
const zReportPayload = {
  window: {
    service_day: "2026-09-05",
    cutover_hour: 3, // > 0 → the cutover-hour span renders
    start: "2026-09-05T03:00:00Z",
    end: "2026-09-06T03:00:00Z",
  },
  collected: { cash: "312.50", wallet: "200.25", total: "512.75" },
  tips: { total: "45.00" },
  refunds: { total: "18.00", count: 2 },
  discounts: { total: "22.00", promo: "15.00", loyalty: "7.00" }, // parseFloat > 0 → card renders
  net_cash_position: "339.50",
  net: "487.25",
  voids: {
    count: 1,
    total: "24.00",
    items: [
      { order_number: "A120", dish_name: "Grilled Sea Bass", qty: 1, line_total: "24.00", reason: "Sent back", voided_by: "Amine Tazi" },
    ],
  },
  comps: {
    count: 1,
    total: "16.00",
    items: [
      { order_number: "A121", dish_name: "Chocolate Fondant", qty: 2, line_total: "16.00", reason: "Manager comp", comped_by: "Nadia Rifai" },
    ],
  },
  by_staff: [
    { name: "Amine Tazi", orders: 12, collected_cash: "180.00", collected_wallet: "90.00" },
    { name: "Nadia Rifai", orders: 8, collected_cash: "132.50", collected_wallet: "110.25" },
  ],
  food_cost: { total: "154.00", food_cost_pct: "30.0" },
  labor: {
    total_hours: "16.5",
    total_labor_cost: "247.50",
    labor_pct: "22.0",
    shifts: [
      { user_name: "Amine Tazi", hours: "8.0", labor_cost: "120.00" },
      { user_name: "Nadia Rifai", hours: null, labor_cost: null }, // still-open shift branch ('—' / laborStillOpen)
    ],
  },
};

// Drawer sessions for the service day. One open (→ the amber close-shift card +
// openDrawerSession computed) and one closed (→ the over/short badge, which does
// Number(over_short) + fmtMoney) so the reconciliation card renders both branches.
const drawerPayload = {
  sessions: [
    { id: 1, status: "closed", over_short: "-5.50", opened_at: "2026-09-05T08:00:00Z", opening_float: "100.00", expected_total: "312.50", counted_total: "307.00" },
    { id: 2, status: "open", over_short: null, opened_at: "2026-09-05T16:00:00Z", opening_float: "150.00", expected_total: null, counted_total: null },
  ],
};

describe("OwnerZReport — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    // Defensive: no mount path calls window.print (printReport / closeShiftAndPrint
    // are user-action handlers), but jsdom leaves window.print unimplemented, so
    // stub it so any future mount-path refactor can't throw here.
    window.print = vi.fn();
    vi.clearAllMocks();
  });

  afterEach(() => {
    // No intervals/observers to leak (onMounted only calls fetchReport), but
    // unmount keeps teardown clean — parity with the other mount-smoke tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) empty / no-data mount ──────────────────────────────────────────────
  // The core guard: setup() + the async onMounted (fetchReport → z-report GET +
  // fetchDrawerSessions GET) and the whole template must render with no data and
  // not throw. z-report → { data: null } keeps `report` falsy → the empty-state
  // article renders (zReport.noData); drawer history default → sessions = [] → no
  // drawer card.
  it("mounts with no report data without a setup() crash", async () => {
    _routes = { "/owner/z-report/": { data: null } };

    expect(() => {
      wrapper = mountReport();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (h1 + kicker, always rendered outside every v-if) — the crash-guard anchor.
    expect(wrapper.text()).toContain("zReport.title");
    expect(wrapper.text()).toContain("zReport.kicker");
    // No report + not loading + no error → the empty-state block renders.
    expect(wrapper.text()).toContain("zReport.noData");
  });

  // ── (2) loaded report: totals, payment breakdown, voids/comps/staff/labor ──
  // Drives the page's own money template on real records: the money KPI grid
  // (fmtMoney over collected cash/wallet/total, tips, refunds, discounts,
  // net-cash, net), the by-staff v-for, the voids/comps tables (fmtMoney on each
  // line_total, expanded by default + rendered via the Transition stub), the
  // food-cost + labor sections, and the drawer reconciliation card. Assertions
  // check money DIGITS + plain-string labels from the page's own template.
  it("mounts a fully-loaded report and renders money without a crash", async () => {
    _routes = {
      "/owner/z-report/": { data: zReportPayload },
      "/owner/drawer/history/": { data: drawerPayload },
    };

    expect(() => {
      wrapper = mountReport();
    }).not.toThrow();

    await flushPromises(); // drain z-report + drawer-history GETs (Promise.all)

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Header still there.
    expect(text).toContain("zReport.title");
    // Report loaded → the service-day banner rendered (v-if="report" branch ran).
    expect(text).toContain("2026-09-05");
    // Money formatting ran: total-collected via the page's own fmtMoney (digits only).
    expect(text).toContain("512.75");
    // The by-staff v-for rendered real rows (proves that loaded table path ran).
    expect(text).toContain("Amine Tazi");
    // A Transition-wrapped section (voids) rendered its table + fmtMoney(line_total).
    expect(text).toContain("Grilled Sea Bass");
  });
});
