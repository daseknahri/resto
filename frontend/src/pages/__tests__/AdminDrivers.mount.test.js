/**
 * Mount smoke test for AdminDrivers.vue (the platform-admin drivers page, ~590 lines).
 *
 * WHY: this is the app's recurring production bug class — an admin/money page white-screens
 * because a setup()-time error (a TDZ ReferenceError, an undefined lookup, an unguarded
 * browser API, a bad Intl currency call) throws inside <script setup> and was never caught
 * by a test. AdminDrivers' setup() wires three composables/stores (useI18n / useConfirmModal /
 * useToastStore), builds `fmtMoney` (an Intl.NumberFormat currency:MAD over currentLocale.value)
 * and `formatDate` (Intl.DateTimeFormat), exposes four order-derived computeds
 * (onlineCount / pendingCount / sortedDrivers / totalDeliveries), and runs an onMounted that
 * fires a single GET /admin/drivers/. shallowMount runs the page's OWN setup() + own template
 * (the stats bar, the desktop drivers table AND the mobile card list — both v-for over
 * sortedDrivers, plus the earnings slide-over shell) while auto-stubbing nothing heavy (the
 * page has no child components), so any setup-time crash fails CI here instead of shipping a
 * blank page.
 *
 * Pattern-faithful to pages/__tests__/AdminWallet.mount.test.js + AdminConsole.mount.test.js
 * (URL-routed api mock + real pinia + mocked useI18n), with the page-specific differences
 * verified against the source:
 *   1. The api boundary is ONLY `lib/api` (`grep "import (api|adminApi) from"` → single hit
 *      `import api from '../lib/api'`, line 423). There is NO `lib/adminApi` on this page — so
 *      only ../../lib/api is mocked. It exposes get/post/put/patch/delete (the page uses
 *      api.get + api.post; the others are provided for shape-parity and safety).
 *   2. The page imports NOTHING from vue-router (`grep "from 'vue-router'"` → no match) and
 *      renders NO <router-link> in its template (plain <a :href> anchors only) — so there is no
 *      router module to mock and no RouterLink stub is needed.
 *
 * Left REAL (jsdom-safe, and none touched at mount):
 *   - the toast store (real Pinia).
 *   - useConfirmModal (module-level ref singletons; `confirm` only fires on a user action —
 *     payout / approve / reject / car-approve — never at mount).
 *   - newIdempotencyKey (only called from submitPayout, a user-action handler).
 * The page registers NO interval / poll / observer / WebSocket / scrollIntoView at mount — it
 * fetches once in onMounted and only re-fetches on the manual "Refresh" button — so there is
 * nothing timer-like to fake here. The earnings slide-over (a <Teleport>/<Transition>) has its
 * content behind `v-if="selected"` and `selected` is null at mount, so nothing renders inside;
 * Teleport/Transition are stubbed to render their slot inline (mirrors OwnerHome.mount.test.js)
 * purely to keep shallowMount from teleporting an inert (v-if=false) subtree to document.body.
 * afterEach unmounts to settle the in-flight mount fetch between tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in AdminDrivers is { t, currentLocale } — the mock MUST return both or
// the setup destructure throws, and fmtMoney/formatDate read `currentLocale.value` as the
// locale arg of Intl.NumberFormat(currency:MAD) / Intl.DateTimeFormat. t echoes the key
// (params appended) so assertions can target the stable i18n keys the page's own template
// renders.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed matcher for the single mocked axios instance (lib/api). The one mount GET
// (/admin/drivers/) defaults to `{ data: {} }` so the empty path renders; a test sets _routes
// to drive the loaded path. _routes/_match are module-level and referenced ONLY from the lazy
// vi.fn closures below (which run at CALL time, never in the hoisted factory body) → TDZ-safe.
// Exposes get/post/put/patch/delete since the page uses api.get + api.post.
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

import AdminDrivers from "../AdminDrivers.vue";

const mountDrivers = () =>
  shallowMount(AdminDrivers, {
    global: {
      stubs: {
        // Inert at mount (content is behind v-if="selected", selected=null) — render the slot
        // inline instead of teleporting an empty subtree to document.body.
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

// A realistic driver row as the /admin/drivers/ list ships it (owed is a STRING amount, as the
// API serializes decimals). Includes name / phone / email / approval + online state / vehicle
// + the per-row stat fields the stats bar + table + mobile list read.
const driver = (overrides = {}) => ({
  id: 1,
  name: "Mohamed Driver",
  email: "m@example.com",
  phone: "0611111111",
  approved: true,
  is_online: true,
  driver_lat: 33.57,
  driver_lng: -7.59,
  total_jobs: 20,
  completed_jobs: 18,
  avg_rating: 4.8,
  owed: "125.50",
  created_at: "2026-01-01T10:00:00Z",
  vehicle: "Dacia Logan",
  driver_vehicle_type: "car",
  ...overrides,
});

describe("AdminDrivers — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // TRAP: the toast store is localStorage-backed (staleCache); clear it FIRST so a cache
    // write in one test can't be served as still-"fresh" to the next.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // No interval/listener/WS is registered at mount, but unmount settles the in-flight
    // /admin/drivers/ mount fetch so nothing leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default mount: empty drivers list ─────────────────────────────────
  // The core guard: the whole setup() (three composable/store wires, fmtMoney + formatDate,
  // the four lazy computeds, the onMounted GET /admin/drivers/) and the whole own-template must
  // render with empty data and not throw. The header title is the always-rendered crash anchor;
  // the empty-state key confirms the drivers fetch resolved down its empty branch (default
  // { data: {} } → drivers.length falsy → empty state, and the array computeds in the v-else
  // block are never evaluated).
  it("mounts with an empty drivers list (default mount GET) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountDrivers();
    }).not.toThrow();

    await flushPromises(); // onMounted → fetchDrivers → GET /admin/drivers/

    expect(wrapper.exists()).toBe(true);
    // Header title (always rendered, page's own template) — the crash-guard anchor.
    expect(wrapper.text()).toContain("adminDrivers.title");
    // Empty /admin/drivers/ (default { data: {} } → drivers.length falsy) → the empty-state
    // branch, confirming the list path resolved without throwing.
    expect(wrapper.text()).toContain("adminDrivers.empty");
  });

  // ── (2) loaded mount: real drivers (approved+online + pending) ─────────────
  // Drives the page's OWN loaded templates (no child delegation): the stats bar
  // (onlineCount / pendingCount / totalDeliveries reduce), the desktop drivers table v-for AND
  // the mobile card list v-for over sortedDrivers (name / phone / approval + online status
  // labels / avg_rating / fmtMoney(owed) Intl-currency + formatDate(created_at) Intl-date).
  // These are the array-render + Intl paths that only run with a non-empty drivers array.
  it("mounts with a loaded drivers list (approved+online + pending, string owed) without a crash", async () => {
    _routes = {
      "/admin/drivers/": {
        data: [
          driver({ id: 1, name: "Mohamed Driver", approved: true, is_online: true }),
          driver({
            id: 2,
            name: "Sara Pending",
            email: undefined,
            phone: "0622222222",
            approved: false,
            is_online: false,
            driver_lat: null,
            driver_lng: null,
            total_jobs: 0,
            completed_jobs: 0,
            avg_rating: null,
            owed: "0.00",
            created_at: "2026-02-01T10:00:00Z",
            vehicle: "",
            driver_vehicle_type: "moto",
          }),
        ],
      },
    };

    expect(() => {
      wrapper = mountDrivers();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Header still renders.
    expect(text).toContain("adminDrivers.title");
    // Driver row rendered from the fetched payload (own-template v-for, not a stubbed child).
    expect(text).toContain("Mohamed Driver");
    // Status label from the page's own v-for: approved + is_online → statusOnline (the
    // approved-branch label). Its presence proves the sortedDrivers array-render path ran.
    expect(text).toContain("adminDrivers.statusOnline");
    // Pending driver → the !approved badge (pendingCount label), proving the mixed-state
    // sort/branch rendered too.
    expect(text).toContain("adminDrivers.pendingCount");
  });
});
