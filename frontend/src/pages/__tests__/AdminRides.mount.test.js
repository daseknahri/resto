/**
 * Mount smoke test for AdminRides.vue (the platform-admin rides page, ~434 lines).
 *
 * WHY: this is the app's recurring production bug class — an admin/money page white-screens
 * because a setup()-time error (a TDZ ReferenceError, an undefined lookup, an unguarded
 * browser API, a bad Intl currency call) throws inside <script setup> and was never caught
 * by a test. AdminRides' setup() wires three composables/stores (useI18n / useConfirmModal /
 * useToastStore), builds `fmtMoney` (an Intl.NumberFormat currency:MAD over currentLocale.value)
 * and `fmtDate` (Intl.DateTimeFormat), and runs an onMounted that fires TWO GETs across TWO
 * axios instances, registers a 20s setInterval poll, and adds a document 'visibilitychange'
 * listener. shallowMount runs the page's OWN setup() + own template (the header, the collapsible
 * ride-fares panel, the status-filter chips, and — in the loaded path — BOTH the desktop rides
 * table AND the mobile card list, each a v-for over `rides`) while auto-stubbing the only child
 * (AppIcon), so any setup-time crash fails CI here instead of shipping a blank page.
 *
 * Pattern-faithful to pages/__tests__/AdminWallet.mount.test.js (URL-routed api mock + real
 * pinia + mocked useI18n), with the page-specific differences verified against the source:
 *   1. The api boundary is BOTH `lib/api` AND `lib/adminApi` (two separate axios instances,
 *      confirmed imports at lines 255-256). At mount (onMounted, lines 419-426):
 *        api.get('/admin/rides/', { params })  (fetchRides — the rides list)
 *        adminApi.get('/admin/settings/')      (fetchFares — the ride-pricing fields)
 *      Both modules are mocked and both share one URL-routed matcher (URLs are globally
 *      distinct). Both expose get/post/put/patch/delete (the page uses api.get + adminApi.get/patch).
 *   2. The page imports NOTHING from vue-router (`grep "vue-router"` → no match) and renders NO
 *      <router-link> in its template — so there is no router module to mock and no RouterLink
 *      stub is needed.
 *
 * Left REAL (jsdom-safe, and none touched at mount):
 *   - the toast store (real Pinia); `toast.show` only fires from saveFares (a user action).
 *   - useConfirmModal (module-level ref singletons + a closure at setup; `confirm` only fires
 *     from saveFares, never at mount).
 * The page registers a 20s `setInterval(fetchRides)` and a document 'visibilitychange' listener
 * at mount, and onUnmounted clears BOTH (clearInterval + removeEventListener, lines 428-433).
 * The 20s interval never elapses within a test, and afterEach unmount runs that onUnmounted so
 * no timer/listener leaks between tests (mirrors OwnerHome.mount.test.js's afterEach).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in AdminRides is { t, currentLocale } — the mock MUST return both or the
// setup destructure throws, and fmtMoney/fmtDate read `currentLocale.value` as the locale arg of
// Intl.NumberFormat(currency:MAD) / Intl.DateTimeFormat. t echoes the key (params appended) so
// assertions can target the stable i18n keys the page's own template renders.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// One URL-routed matcher shared by BOTH mocked axios instances (lib/api + lib/adminApi). The two
// mount GETs default to `{ data: {} }` so the empty path renders (rides fetch → results falsy →
// [] → empty state; fares fetch → all fields ''); a test sets _routes to drive the loaded path.
// _routes/_match are module-level and referenced ONLY from the lazy vi.fn closures below (which
// run at CALL time, never in the hoisted factory body) → TDZ-safe. The two factories inline their
// object literal (no helper called at factory time) to mirror the proven AdminWallet.mount.test.js
// shape exactly. Both expose get/post/put/patch/delete since the page uses api.get + adminApi.get/patch.
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
vi.mock("../../lib/adminApi", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import AdminRides from "../AdminRides.vue";

const mountRides = () => shallowMount(AdminRides);

// A realistic ride row as the /admin/rides/ list ships it: nested rider/driver objects, string
// address fields, a STRING fare amount (as the API serializes decimals), a wallet/cash flag, a
// status, and created/completed ISO timestamps — the exact fields the table + card-list v-fors read.
const ride = (overrides = {}) => ({
  id: 501,
  rider: { id: 10, name: "Aicha Rider", phone: "0611223344" },
  driver: { id: 7, name: "Mohamed Driver", phone: "0622334455" },
  pickup_address: "Place Jemaa el-Fna",
  dropoff_address: "Gueliz, Marrakech",
  fare: "45.00",
  paid_with_wallet: true,
  status: "completed",
  created_at: "2026-02-01T10:00:00Z",
  completed_at: "2026-02-01T10:25:00Z",
  ...overrides,
});

describe("AdminRides — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // TRAP: the toast store is localStorage-backed (staleCache); clear it FIRST so a cache write
    // in one test can't be served as still-"fresh" to the next.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // AdminRides registers a 20s setInterval poll + a 'visibilitychange' listener at mount;
    // unmount runs onUnmounted → clearInterval + removeEventListener so neither leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default mount: empty rides list + empty fares ─────────────────────
  // The core guard: the whole setup() (three composable/store wires, fmtMoney + fmtDate, the
  // onMounted fan of two GETs across two axios instances + the interval/listener registration)
  // and the whole own-template must render with empty data and not throw. The header H1 title is
  // the always-rendered crash anchor; the empty-state key confirms the rides fetch resolved down
  // its empty branch (default { data: {} } → res.data.results falsy → rides.length 0 → empty state).
  it("mounts with empty data (two mount GETs default-empty) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountRides();
    }).not.toThrow();

    await flushPromises(); // onMounted → fetchRides (api) + fetchFares (adminApi)

    expect(wrapper.exists()).toBe(true);
    // Header H1 (always rendered, page's own template) — the crash-guard anchor.
    expect(wrapper.text()).toContain("adminRides.title");
    // Empty /admin/rides/ (default { data: {} } → results falsy → rides.length 0) → the empty-state
    // branch, confirming the rides-table path resolved without throwing.
    expect(wrapper.text()).toContain("adminRides.empty");
  });

  // ── (2) loaded mount: real rides (assigned+wallet+completed + unassigned+cash+searching) ──
  // Drives the page's OWN loaded templates (no child delegation): the desktop rides table v-for
  // AND the mobile card-list v-for over `rides` (riderLabel / driver-name-or-unassigned branch /
  // pickup+dropoff / fmtMoney(fare) Intl-currency + paymentLabel / statusClass+statusLabel /
  // fmtDate(created_at) Intl-date). These are the array-render + Intl paths that only run with a
  // non-empty rides array.
  it("mounts with a loaded rides list (assigned + unassigned rows, string fares) without a crash", async () => {
    _routes = {
      "/admin/rides/": {
        data: [
          ride({ id: 501, status: "completed", paid_with_wallet: true }),
          ride({
            id: 502,
            rider: { id: 11, phone: "0633445566" }, // no name → phone fallback in riderLabel
            driver: null, // exercises the "unassigned" v-else branch
            pickup_address: "Airport",
            dropoff_address: "Downtown",
            fare: "0.00",
            paid_with_wallet: false, // cash branch
            status: "searching",
            created_at: "2026-02-02T09:00:00Z",
            completed_at: null,
          }),
        ],
      },
    };

    expect(() => {
      wrapper = mountRides();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Header still renders.
    expect(text).toContain("adminRides.title");
    // Rider name rendered from the fetched payload (own-template v-for, not a stubbed child) —
    // the loaded discriminator (this string appears nowhere in the empty/chrome path).
    expect(text).toContain("Aicha Rider");
    // The driver-less second ride → the "unassigned" label, which renders ONLY inside the rides
    // v-for's `v-else` (never in the header/chips), proving the mixed-row array-render path ran.
    expect(text).toContain("adminRides.unassigned");
  });
});
