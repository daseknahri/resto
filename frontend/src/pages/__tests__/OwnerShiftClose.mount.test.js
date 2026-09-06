/**
 * Mount smoke test for OwnerShiftClose.vue (the owner shift-close / cash-drawer
 * reconciliation page, ~344 lines). A MONEY surface.
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined map
 * access, bad import) was never caught by a test". Mounting the page runs its real
 * setup() + onMounted(loadData) for real, so any such crash fails CI here instead
 * of in production — and this is a money page (opening float, expected vs counted
 * cash, over/short variance, pay-in/out movements, Z-report totals), so a silent
 * white-screen here is especially costly.
 *
 * Pattern-faithful to pages/__tests__/OwnerWallet.mount.test.js (money digits) +
 * pages/__tests__/OwnerHome.mount.test.js (hoisted RouterLink stub, URL-routed
 * api mock):
 *   - shallowMount (auto-stubs the one child component, AppIcon) + real pinia
 *     (setActivePinia(createPinia())) + a mocked lib/api
 *   - useI18n mocked to return deterministic keys ({ t } — the ONLY thing the page
 *     destructures; it formats money itself via Intl.NumberFormat in fmtMoney())
 *   - vue-router mocked (the page imports { RouterLink }; uses <RouterLink> twice)
 *
 * Page-specific notes (verified by reading the source, not assumed):
 *   - useI18n destructure is `{ t }` ONLY. The page formats money itself via
 *     Intl.NumberFormat in fmtMoney(), keyed off the tenant currency
 *     (tenant.resolvedMeta?.profile?.currency, which is null in jsdom → falls back
 *     to 'MAD'). So the loaded assertions check DIGITS only, never the currency
 *     symbol/placement — and all amounts are kept < 1000 so the en-US grouping
 *     separator (e.g. "1,450.00") never splits the digits being asserted.
 *   - It imports ONLY { RouterLink } from vue-router (no useRoute/useRouter, but
 *     both are mocked defensively). Two <RouterLink :to="{ name:'owner-home' }">.
 *   - onMounted(loadData) fires Promise.all([GET /owner/drawer/current/,
 *     GET /owner/z-report/]); if the drawer response has no .data.session it then
 *     GETs /owner/drawer/history/ for the most-recent closed session. Everything
 *     resolves { data: {} } by default so the fresh page renders (no drawer →
 *     "noDrawer"). Tests set _routes to drive the loaded closed-drawer path.
 *   - No intervals / poll / visibilitychange / WebSocket / observers / scrollIntoView
 *     at mount; the only lifecycle hook is onMounted. window.print() is a user-action
 *     handler (printHandover), never reached at mount — stubbed defensively anyway.
 *   - useConfirmModal + the tenant/toast stores are left REAL: they are jsdom-safe
 *     (useConfirmModal is module-level refs; confirm() is only called by the
 *     user-action closeDrawerNow) — matching the sibling mount-smoke tests.
 *   - localStorage.clear() in beforeEach: the REAL tenant store getters touch the
 *     staleCache-backed meta cache; clearing keeps tests isolated and forces the
 *     'MAD' currency fallback (hygiene parity with the sibling mount-smoke tests).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    // Not destructured by OwnerShiftClose (it formats money via Intl itself) —
    // provided defensively so the mock matches the composable's fuller shape.
    formatNumber: (v) => String(v),
    formatCurrency: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock. onMounted GETs /owner/drawer/current/ + /owner/z-report/
// (always, in parallel), then /owner/drawer/history/ only when the drawer response
// carries no .data.session. Default: everything resolves empty so the fresh page
// renders (no drawer session); tests set _routes to drive the loaded money path.
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

// OwnerShiftClose imports { RouterLink } from 'vue-router'.
// vi.hoisted: the vi.mock('vue-router') factory below is hoisted above the imports
// and runs during import evaluation — before a plain `const` in the file body would
// initialize — so referencing a plain const there hits the TDZ ("0 test" collection
// error). vi.hoisted makes the stub available to the hoisted factory.
const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import OwnerShiftClose from "../OwnerShiftClose.vue";

const mountPage = () =>
  shallowMount(OwnerShiftClose, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

describe("OwnerShiftClose — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    // printHandover calls window.print() — a user-action handler, never reached at
    // mount, but stubbed defensively so no mount path could ever hit a jsdom no-op.
    window.print = vi.fn();
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // No intervals/observers to leak, but unmount keeps teardown clean — parity
    // with the other mount-smoke tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) fresh mount: empty drawer / empty z-report ────────────────────────────
  // The core guard: setup() + the async onMounted (loadData: drawer/current +
  // z-report, then drawer/history) + the whole template must render with empty data
  // and not throw. No drawer session → the cash section shows its "noDrawer" prompt.
  it("mounts fresh (no drawer session / empty z-report) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header title (h1, always rendered) — the crash-guard anchor.
    expect(wrapper.text()).toContain("shiftClose.title");
    // Cash-drawer reconciliation section heading is always rendered.
    expect(wrapper.text()).toContain("shiftClose.cashSection");
    // No drawer session → the empty-state prompt (not the open/closed branches).
    expect(wrapper.text()).toContain("shiftClose.noDrawer");
  });

  // ── (2) loaded money path: closed drawer + movements + z-report ───────────────
  // Drives the page's own money template on real records:
  //   - drawer/current .data.session (status "closed") → the closed-session summary
  //     (opening_float / expected_total / counted_total via fmtMoney) + the
  //     over/short badge (overShortValue/overShortLabel/overShortClass computeds)
  //   - drawer/current .data.transactions → the pay-in/out movements table
  //     (kind branch, fmtMoney(amount), reason, fmtTime(at))
  //   - z-report .data → the Z-report summary card (collected/tips/voids via fmtMoney)
  // Assertions check DIGITS only (all amounts < 1000 → no grouping separator), so
  // they are robust to currency-symbol/locale differences in Intl output.
  it("mounts a closed drawer with movements + z-report and renders money without a crash", async () => {
    _routes = {
      "/owner/drawer/current/": {
        data: {
          session: {
            status: "closed",
            opening_float: "200.00",
            expected_total: "845.00",
            counted_total: "840.00",
            over_short: "-5.00",
          },
          transactions: [
            { id: 1, kind: "pay_in", amount: "50.00", reason: "Change fund", at: "2026-09-05T10:00:00Z" },
            { id: 2, kind: "pay_out", amount: "20.00", reason: "Napkins", at: "2026-09-05T14:00:00Z" },
          ],
        },
      },
      "/owner/z-report/": {
        data: {
          collected: { count: 42, total: "845.00", cash: "600.00", wallet: "245.00" },
          tips: { total: "120.00" },
          voids: { count: 2, total: "35.00" },
        },
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises(); // drain the Promise.all(drawer/current + z-report)
    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("shiftClose.title");

    // Closed-drawer summary money (fmtMoney over the session amounts, digits only).
    expect(wrapper.text()).toContain("200.00"); // opening float
    expect(wrapper.text()).toContain("840.00"); // counted total
    // The over/short badge rendered (closedDrawer branch + overShort* computeds ran).
    expect(wrapper.text()).toContain("shiftClose.overShortLabel");
    // Pay-in/out movements table rendered from drawerTransactions (own template).
    expect(wrapper.text()).toContain("Change fund");

    // Z-report summary card rendered from its own template money (fmtMoney).
    expect(wrapper.text()).toContain("shiftClose.summarySection");
    expect(wrapper.text()).toContain("120.00"); // tips total
  });
});
