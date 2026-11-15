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

// ── Run 8 G4b-A (B-29 / B-30 / B-17-tables) ──────────────────────────────────
// Appended 2026-11-15. Base above untouched: the new tests only ADD coverage.
//
// B-29: bulk-generate shows the 120 cap and rejects counts above it before any
// request; a blocked print popup toasts instead of failing silently.
// B-30: the delete confirm warns about live orders (the /tables/ list carries
// no live-order data, so it warns rather than blocks).
// B-17 (tables part): the delete confirm passes danger: true.
import api from "../../lib/api";
import { useConfirmModal } from "../../composables/useConfirmModal";
import { useToastStore } from "../../stores/toast";

describe("OwnerTables — G4b-A (B-29 bulk cap + print popup / B-30 delete warning / B-17 danger)", () => {
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
    vi.restoreAllMocks();
  });

  const _buttonWith = (text) => wrapper.findAll("button").find((b) => b.text().includes(text));
  const _buttonExact = (text) =>
    wrapper.findAll("button").find((b) => b.text().trim() === text);

  // Header "Create" opens the setup dialog; the Bulk tab switches the form.
  const _openBulk = async () => {
    await _buttonExact("ownerTables.create").trigger("click");
    await flushPromises();
    await _buttonExact("ownerTables.bulkGenerate").trigger("click");
    await flushPromises();
  };

  // Bulk form number inputs, in DOM order: start, count, position_start.
  const _countInput = () => wrapper.findAll('input[type="number"]')[1];

  const _mountOneTable = async () => {
    _routes = { "/tables/": { data: [makeTable()] } };
    wrapper = mountTables();
    await flushPromises();
    await flushPromises(); // drain applyTables -> generateQrBatch (async qrcode import)
  };

  // ── B-29: bulk-generate cap ──────────────────────────────────────────────

  it("bulk form shows the 120 cap and a count of 500 is rejected before any request (B-29)", async () => {
    await _mountOneTable();
    await _openBulk();

    expect(wrapper.text()).toContain('ownerTables.countMax({"max":120})');

    await _countInput().setValue(500);
    await _buttonExact("ownerTables.generate").trigger("click");
    await flushPromises();

    expect(api.post).not.toHaveBeenCalledWith("/tables/bulk-generate/", expect.anything());
    expect(wrapper.text()).toContain('ownerTables.bulkCountMaxExceeded({"max":120})');
    expect(useToastStore().message).toContain("ownerTables.bulkCountMaxExceeded");
  });

  it("a count within the cap still generates after the confirm is approved (B-29)", async () => {
    await _mountOneTable();
    await _openBulk();

    await _countInput().setValue(12);
    await _buttonExact("ownerTables.generate").trigger("click");
    await flushPromises();
    // No POST before the owner approves the confirm dialog.
    expect(api.post).not.toHaveBeenCalledWith("/tables/bulk-generate/", expect.anything());
    useConfirmModal()._settle(true);
    await flushPromises();
    await flushPromises();

    expect(api.post).toHaveBeenCalledWith(
      "/tables/bulk-generate/",
      expect.objectContaining({ count: 12 })
    );
  });

  // ── B-29: blocked print popup ────────────────────────────────────────────

  it("a blocked print popup toasts instead of failing silently (B-29)", async () => {
    await _mountOneTable();
    const openSpy = vi.spyOn(window, "open").mockReturnValue(null);

    await _buttonWith("ownerTables.printSingle").trigger("click");
    await flushPromises();

    expect(openSpy).toHaveBeenCalled();
    expect(useToastStore().message).toContain("ownerTables.printPopupBlocked");
  });

  // ── B-30 + B-17: delete confirm ──────────────────────────────────────────

  it("delete confirm warns about live orders, is danger-styled, and deletes only after approval (B-30, B-17)", async () => {
    await _mountOneTable();

    await _buttonWith("ownerTables.delete").trigger("click");
    await flushPromises();

    const opts = useConfirmModal().options.value;
    expect(opts.title).toContain("ownerTables.deleteConfirm");
    expect(opts.body).toContain("confirmModal.defaultBody");
    expect(opts.body).toContain("ownerTables.deleteLiveOrdersWarning");
    expect(opts.danger).toBe(true);
    // No DELETE before the owner approves the confirm dialog.
    expect(api.delete).not.toHaveBeenCalled();

    useConfirmModal()._settle(true);
    await flushPromises();
    await flushPromises();
    expect(api.delete).toHaveBeenCalledWith("/tables/1/");
  });
});
