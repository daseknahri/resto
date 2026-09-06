/**
 * Mount smoke test for AdminDeliveryZones.vue (the platform-admin delivery-zones page, ~564 lines).
 *
 * WHY: this is the app's recurring production bug class — a page white-screens because a
 * setup()-time error (a TDZ ReferenceError, an undefined lookup, an unguarded browser API,
 * or a render over a payload shape the template didn't expect) throws inside <script setup>
 * and was never caught by a test. AdminDeliveryZones' setup() wires three things (useI18n /
 * useConfirmModal / useToastStore), registers a lazy `watch(showForm)` + a focus-trap
 * keydown handler (bound ONLY when the drawer opens) and an onBeforeUnmount cleanup, and
 * runs an onMounted that fires ONE GET (/admin/delivery-zones/). shallowMount runs the
 * page's OWN setup() + own template (the zones table/cards, the empty/error states, the
 * teleported form drawer) so any setup-time crash fails CI here instead of shipping a blank
 * page. There are NO child components (inline SVGs only), so nothing is auto-stubbed away —
 * the whole page renders for real.
 *
 * Pattern-faithful to pages/__tests__/AdminWallet.mount.test.js (URL-routed api mock + real
 * pinia + mocked useI18n), with the page-specific differences verified against the source:
 *   1. The api boundary is a SINGLE axios instance, `lib/api` (grep: no `lib/adminApi`
 *      import). The page uses api.get (mount) + api.post/patch/delete (user actions), so the
 *      mock exposes all five; only .get is URL-routed since it is the only one hit at mount.
 *   2. useI18n destructure is exactly `{ t }` (grep-verified — no currentLocale/formatDate),
 *      so the mock returns only `t` (echoing the key, params appended) — assertions target
 *      the stable i18n keys the page's own template renders.
 *   3. The page imports NOTHING from 'vue-router' and renders NO <router-link> (grep: no
 *      match) — so there is no router module to mock and no RouterLink stub is needed.
 *   4. NO Leaflet / map at mount (grep: no `leaflet`/`L.map`/`ensureLeaflet` in the page).
 *      The polygon is edited as a JSON <textarea>, not a map — so there is no fire-and-forget
 *      dynamic-import map chain to leak post-teardown. Nothing map-like to handle here.
 *
 * Left REAL (jsdom-safe, and none touched at mount):
 *   - the toast store (real Pinia); toast.show only fires from save()/deleteZone() (user
 *     actions), never at mount.
 *   - useConfirmModal (module-level ref singletons; `confirm` only resolves on a user delete
 *     click — no setup side effects).
 * The page registers NO interval / observer / WebSocket at mount. `watch(showForm)` is lazy
 * (showForm is false at mount, so its callback — which would add the document 'keydown'
 * trap — never runs), and onBeforeUnmount only removes a listener that was never added.
 * afterEach unmounts anyway to settle the in-flight mount fetch and tear down the watch.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in AdminDeliveryZones is exactly `{ t }` — the mock returns only `t`
// (echoing the key; params appended) so assertions can target the stable i18n keys the
// page's own template renders.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// URL-routed api mock for the single axios instance (lib/api). onMounted fires ONE GET:
// /admin/delivery-zones/. Default: it resolves `{ data: {} }` so the empty path renders
// (zones becomes {}, whose `.length` is undefined → the `!zones.length` empty branch); a
// test sets _routes to drive the loaded path. _routes/_match are module-level and read ONLY
// from the lazy vi.fn closure at CALL time (never in the hoisted factory body) → TDZ-safe.
// post/patch/delete are only reachable from user-action handlers (save/deleteZone), never at
// mount, so they return a static `{ data: {} }`.
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

import AdminDeliveryZones from "../AdminDeliveryZones.vue";

const mountPage = () => shallowMount(AdminDeliveryZones);

// A realistic zone row with the fields the page's own template v-for reads: id, name, city,
// approx_radius_km, is_active, and — CRITICALLY — `polygon` as an ARRAY (the template renders
// `zone.polygon.length`, so a non-array/undefined here would throw at render). fee_tiers /
// center_* are only read in openEdit (a user action), included for realism.
const zone = (overrides = {}) => ({
  id: 1,
  name: "Centre Ville",
  city: "Casablanca",
  center_lat: 33.5731,
  center_lng: -7.5898,
  approx_radius_km: 5,
  polygon: [
    { lat: 33.57, lng: -7.58 },
    { lat: 33.58, lng: -7.59 },
    { lat: 33.56, lng: -7.6 },
  ],
  fee_tiers: [
    { km_up_to: 3, fee: 2.5 },
    { km_up_to: null, fee: 5.0 },
  ],
  is_active: true,
  ...overrides,
});

describe("AdminDeliveryZones — mount smoke", () => {
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
    // Unmount settles the in-flight mount fetch and tears down the lazy watch(showForm) +
    // onBeforeUnmount cleanup so nothing leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default / empty mount ──────────────────────────────────────────────
  // The core guard: the whole setup() (three composable/store wires, the lazy watch + focus-
  // trap registration, the onMounted fetchZones GET) and the whole own-template must render
  // with empty data and not throw. The H1 title is the always-rendered crash anchor; the
  // empty-state title confirms the zones fetch resolved down its `!zones.length` empty branch.
  it("mounts with empty data (default-empty GET) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises(); // onMounted → fetchZones → GET /admin/delivery-zones/

    expect(wrapper.exists()).toBe(true);
    // Header H1 (always rendered, page's own template, outside every v-if) — crash-guard anchor.
    expect(wrapper.text()).toContain("adminZones.title");
    // Empty /admin/delivery-zones/ (default { data: {} } → zones.length falsy) → the empty-state
    // branch, confirming the fetch path resolved without throwing.
    expect(wrapper.text()).toContain("adminZones.emptyTitle");
  });

  // ── (2) loaded state with a realistic zones payload ────────────────────────
  // Drives the page's OWN loaded template (not delegated to a stubbed child): the zones v-for
  // (mobile cards + desktop table) with per-zone `zone.polygon.length`, the radiusKm/polygonPts
  // param interpolations, and the is_active status pill. res.data is assigned DIRECTLY to zones,
  // so the payload is the array itself (not wrapped in .results). This is the array-render +
  // polygon-length path that only runs with a non-empty zones array.
  it("mounts with a loaded zones payload (array with polygon points) without a crash", async () => {
    _routes = {
      "/admin/delivery-zones/": {
        data: [
          zone(),
          zone({
            id: 2,
            name: "Maarif",
            approx_radius_km: 3,
            polygon: [
              { lat: 33.58, lng: -7.61 },
              { lat: 33.59, lng: -7.62 },
              { lat: 33.57, lng: -7.63 },
            ],
            fee_tiers: [],
            is_active: false,
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
    expect(text).toContain("adminZones.title");
    // Zone rows rendered from the fetched payload (own-template v-for, not a stubbed child).
    expect(text).toContain("Centre Ville");
    expect(text).toContain("Maarif");
    // City cell from the same v-for confirms the loaded row body rendered (not just the name).
    expect(text).toContain("Casablanca");
  });
});
