/**
 * Mount smoke test for AdminFlashSales.vue (the platform-admin flash-sales page,
 * ~281 lines — platform-sponsored, cross-tenant discount campaigns restaurants opt
 * into: a create form + a list with schedule/discount/status + activate/pause/delete).
 *
 * WHY: this is the app's recurring production bug class — an admin page white-screens
 * because a setup()-time error (a TDZ ReferenceError, an undefined lookup, an unguarded
 * browser API, a bad Intl call) throws inside <script setup> and was never caught by a
 * test. AdminFlashSales' setup() wires two composables/stores (useI18n / useToastStore),
 * builds `fmtDate` (an Intl.DateTimeFormat over currentLocale.value), a reactive create
 * `form`, and runs onMounted(fetchSales) → api.get('/admin/flash-sales/'). shallowMount
 * runs the page's OWN setup() + own template (the header, the create panel, and — once
 * loaded — the flash-sales v-for with its discount chip, live/paused/scheduled status
 * pills, fmtDate schedule line and redemption counter), auto-stubbing the only child
 * (AppIcon), so any setup-time crash fails CI here instead of shipping a blank page.
 *
 * Pattern-faithful to pages/__tests__/AdminCustomers.mount.test.js +
 * OwnerReservations.mount.test.js (URL-routed api mock + real pinia + mocked useI18n),
 * with the page-specific differences verified against the source:
 *   1. The api boundary is ONLY `lib/api` (`import api from '../lib/api'` — grep for
 *      `adminApi` on this page returns NO match, so there is no second module to mock).
 *      The page uses api.get (mount) + api.post/patch/delete (user actions only);
 *      get/post/put/patch/delete are all exposed for shape-parity. The single mount GET
 *      is /admin/flash-sales/; its empty tolerance is
 *      `Array.isArray(res.data) ? res.data : (res.data?.results || [])`, so the default
 *      `{ data: {} }` → not an array → `results` undefined → `[]` → the empty state.
 *   2. The page imports NOTHING from vue-router (`grep "from 'vue-router'"` → no match)
 *      and renders NO <router-link> — so there is no router module to mock and no
 *      vi.hoisted RouterLink stub is needed.
 *
 * Left REAL (jsdom-safe, and none touched at mount):
 *   - the toast store (real Pinia; `toast.show` only fires from create/toggle/delete
 *     user-action handlers, never at mount).
 * The page registers NO interval / poll / observer / WebSocket / scrollIntoView / Teleport
 * at mount — it fetches once in onMounted and only re-fetches on the manual "Refresh"
 * button. The lone <Transition> wraps the inline delete-confirm, whose content is behind
 * `v-if="deleteConfirmId === fs.id"` (null at mount) — nothing renders inside it — so no
 * Transition/Teleport stub is required. afterEach unmounts to settle the in-flight mount
 * fetch between tests. localStorage.clear() in beforeEach is cheap hygiene for the
 * staleCache-backed-store convention (the toast store here is not cache-backed, but the
 * clear keeps this test uniform with the other admin mount smokes and future-proofs it).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in AdminFlashSales is { t, currentLocale } — the mock MUST return
// both or the setup destructure throws, and fmtDate reads `currentLocale.value` as the
// locale arg of Intl.DateTimeFormat. t echoes the key (params appended as JSON) so
// assertions can target the stable i18n keys the page's own template renders.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// One URL-routed matcher for the single mocked axios instance (lib/api). The mount GET
// (/admin/flash-sales/) defaults to `{ data: {} }` so the empty path renders; a test sets
// _routes to drive the loaded path. _routes/_match are module-level and referenced ONLY
// from the lazy vi.fn closures below (which run at CALL time, never in the hoisted factory
// body) → TDZ-safe. get/post/put/patch/delete are all exposed (the page uses
// api.get/post/patch/delete).
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

import AdminFlashSales from "../AdminFlashSales.vue";

const mountPage = () => shallowMount(AdminFlashSales);

// A realistic flash-sale row with the fields the page's own list template reads:
// id, name, discount_value, is_live / is_active (drive the status pill), description,
// active_from/active_until (fmtDate → Intl.DateTimeFormat), redemption_count/max_redemptions.
const flashSale = (overrides = {}) => ({
  id: 1,
  name: "Weekend 15% off",
  discount_value: 15,
  is_live: true,
  is_active: true,
  description: "All restaurants, Fri-Sun.",
  active_from: "2026-09-05T00:00:00Z",
  active_until: "2026-09-08T00:00:00Z",
  redemption_count: 42,
  max_redemptions: 500,
  ...overrides,
});

describe("AdminFlashSales — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // Cheap hygiene for the staleCache-backed-store convention (clear before each mount).
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Unmount settles the in-flight /admin/flash-sales/ mount fetch so nothing leaks
    // between tests. No interval/listener/WS/Teleport is registered at mount.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default mount: empty flash-sales list ─────────────────────────────
  // The core guard: the whole setup() (two composable/store wires, fmtDate, the reactive
  // create form, the onMounted GET /admin/flash-sales/) and the whole own-template must
  // render with empty data and not throw. `loading` starts true (skeletons render first);
  // after flushPromises the mount fetch resolves down its empty branch (default { data: {} }
  // → not an array → results undefined → sales=[] → loading=false), so the empty-state
  // panel renders. The header title is the always-rendered crash anchor.
  it("mounts with an empty flash-sales list (default mount GET) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises(); // onMounted → fetchSales → GET /admin/flash-sales/

    expect(wrapper.exists()).toBe(true);
    // Header title (always rendered, outside every v-if) — the crash-guard anchor.
    expect(wrapper.text()).toContain("adminFlashSales.title");
    // Create panel heading (also always rendered) — confirms the form scaffold mounted.
    expect(wrapper.text()).toContain("adminFlashSales.createTitle");
    // Empty /admin/flash-sales/ (default { data: {} } → sales=[]) → the empty-state branch,
    // confirming the list fetch resolved without throwing.
    expect(wrapper.text()).toContain("adminFlashSales.empty");
  });

  // ── (2) loaded mount: realistic flash-sales payload (live + paused) ───────
  // Drives the page's OWN loaded template (not delegated to a stubbed child): the
  // flash-sales v-for, exercising the discount chip, the mixed status branches
  // (is_live → live pill; !is_active → paused pill; else → scheduled), fmtDate over
  // active_from/active_until (Intl.DateTimeFormat over currentLocale.value) and the
  // redemptions counter (t with { count, max } params, max || '∞'). These are the
  // array-render + Intl paths that only run with a non-empty sales array.
  it("mounts with a loaded flash-sales list (live + paused, string/null max) without a crash", async () => {
    _routes = {
      "/admin/flash-sales/": {
        data: [
          flashSale({ id: 1, name: "Weekend 15% off", is_live: true, is_active: true }),
          flashSale({
            id: 2,
            name: "Ramadan Special",
            discount_value: 25,
            is_live: false,
            is_active: false,
            description: "",
            active_from: "2026-03-01T00:00:00Z",
            active_until: "2026-03-30T00:00:00Z",
            redemption_count: 0,
            max_redemptions: null,
          }),
        ],
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Header still renders.
    expect(text).toContain("adminFlashSales.title");
    // Flash-sale rows rendered from the fetched payload (own-template v-for, not a child).
    expect(text).toContain("Weekend 15% off");
    expect(text).toContain("Ramadan Special");
    // Status pills from the page's own v-for: is_live → live pill, !is_active → paused pill.
    // Their presence proves the mixed-state sales array-render path ran clean.
    expect(text).toContain("adminFlashSales.live");
    expect(text).toContain("adminFlashSales.paused");
  });
});
