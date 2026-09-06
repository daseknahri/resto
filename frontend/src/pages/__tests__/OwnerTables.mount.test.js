/**
 * Mount smoke test for OwnerTables.vue (owner dine-in table + QR management, ~1072 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, unguarded browser API,
 * bad import) was never caught by a test". Mounting the page runs its real setup()
 * for real — the async onMounted (fetchTables → applyTables → generateQrBatch, which
 * dynamically imports qrcode), the two onMounted/onUnmounted keydown listeners, the
 * useFocusTrap watch, and a dozen table-derived computeds + the grid v-for — so any
 * such crash fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js +
 * pages/__tests__/SuperAppHub.mount.test.js (URL-routed api mock):
 *   - shallowMount (auto-stubs the heavy children: AppIcon, OwnerFloorSections)
 *   - real pinia (toast / tenant stores run for real) + a mocked lib/api
 *   - useI18n mocked → { t, currentLocale } (the exact destructure the page uses)
 *   - NO vue-router mock: the page imports nothing from vue-router and uses no
 *     <RouterLink> in its template (grep-confirmed), so none is needed.
 *   - qrcode mocked: onMounted → fetchTables → generateQrBatch does
 *     `(await import("qrcode")).default.toDataURL(...)`. qrcode is a leaf dep and
 *     every toDataURL call is already try/caught in the page, so mocking it is
 *     deterministic (no canvas) and changes nothing about the page's own crash
 *     coverage.
 *
 * Left REAL (jsdom-safe, exercises more real setup): staleCache (falls through to
 * the mocked network on an empty/cleared cache), escape, useConfirmModal (a lazy
 * module-level singleton), and useFocusTrap (its watch(openSignal) stays inert while
 * the setup dialog is closed at mount).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// qrcode is dynamically imported inside generateQrBatch (the onMounted path). Mock
// the default export's toDataURL so the QR batch is deterministic and canvas-free.
vi.mock("qrcode", () => ({
  default: { toDataURL: vi.fn().mockResolvedValue("data:image/png;base64,AAAA") },
}));

// URL-routed api mock. onMounted → fetchTables GETs /tables/, which returns a BARE
// ARRAY (not a paginated { results } object). Default: everything resolves
// { data: {} } — the page coerces a non-array to [] and renders the empty state.
// Tests set _routes to drive the loaded path.
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
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import OwnerTables from "../OwnerTables.vue";

const mountTables = () =>
  shallowMount(OwnerTables, {
    global: {
      stubs: {
        // The setup dialog is wrapped in <Teleport to="body">; render inline so
        // its (v-if-gated) content stays inside wrapper for assertions.
        Teleport: { template: "<slot />" },
      },
    },
  });

const makeTable = (overrides = {}) => ({
  id: 1,
  label: "Table 1",
  slug: "table-1",
  is_active: true,
  position: 0,
  ...overrides,
});

describe("OwnerTables — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // fetchTables() uses the REAL staleCache (localStorage-backed). Without this
    // clear, test 1's empty-list write is served (still "fresh" within the 5-min
    // TTL) to test 2, so test 2 never sees its /tables/ mock payload.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // The page adds a document "keydown" listener on mount (onSetupEscape) and
    // useFocusTrap registers onBeforeUnmount cleanup; unmount runs onUnmounted so
    // no listener leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) fresh owner: no tables ────────────────────────────────────────────
  // The core guard: the async onMounted (fetchTables → applyTables →
  // generateQrBatch's dynamic qrcode import) and the whole template must render
  // with empty data and not throw.
  it("mounts with no tables (empty state) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountTables();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (always rendered) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerTables.title");
    expect(wrapper.text()).toContain("ownerTables.kicker");
    // No tables + not loading → the empty-state article renders its own heading.
    expect(wrapper.text()).toContain("ownerTables.noLinks");
  });

  // ── (2) loaded: active + disabled tables ──────────────────────────────────
  // Drives the grid v-for + the per-table computeds/branches (filteredTables,
  // activeTablesCount, the status-pill ternary, tableShortUrl/tableFullMenuUrl,
  // tableQrSrc) — the own-template paths that only run with a non-empty array.
  it("mounts with active + disabled tables and renders them without a crash", async () => {
    _routes = {
      "/tables/": {
        data: [
          makeTable({ id: 1, label: "Table 1", slug: "table-1", is_active: true }),
          makeTable({ id: 2, label: "Patio 2", slug: "patio-2", is_active: false }),
        ],
      },
    };

    expect(() => {
      wrapper = mountTables();
    }).not.toThrow();

    await flushPromises();
    await flushPromises(); // drain applyTables → generateQrBatch (async qrcode import)

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerTables.title");
    // Table labels render from the page's OWN template (grid v-for over the fetch).
    expect(wrapper.text()).toContain("Table 1");
    expect(wrapper.text()).toContain("Patio 2");
    // The per-table status-pill ternary ran both branches.
    expect(wrapper.text()).toContain("ownerTables.active");
    expect(wrapper.text()).toContain("ownerTables.disabledState");
  });
});
