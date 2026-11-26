/**
 * Mount smoke test for WaiterPage.vue (the waiter / dine-in service page, ~2637 lines).
 *
 * WHY: this is one of the largest, busiest staff surfaces and it had NO mount
 * test. The app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined map access, bad import) was never
 * caught by a test". WaiterPage is especially exposed: an async onMounted that
 * awaits Promise.all([waiter.fetchOrders(), loadTableStatuses(), loadMyShift()]),
 * a menu-prefetch, a 15s background poll, a visibilitychange listener, three
 * focus-trap watchers, and a dozen order-derived computeds + template v-fors
 * (table grouping, floor tiles, tabs). The page's EXTRACTED CHILD components
 * (WaiterOrderCard, WaiterSettleSheet, …) and the waiter STORE each have tests,
 * but nothing mounted the PAGE's own setup() until this file. shallowMount runs
 * WaiterPage's real setup() while auto-stubbing the heavy children, so a crash in
 * any of it fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js +
 * SuperAppHub.mount.test.js (URL-routed api mock). WaiterPage imports NOTHING
 * from vue-router (it uses plain <a> links), so vue-router is intentionally NOT
 * mocked and no route param is supplied.
 *
 * The install-prompt / wake-lock / now-ticker / confirm-modal composables are
 * left REAL: they are jsdom-safe (feature-detected navigator APIs, optional-
 * chained window.matchMedia), and each of the two setInterval timers (the 15s
 * page poll + useNowTicker's 30s ticker) is cleared on unmount — so afterEach
 * unmounts to keep timers from leaking between tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// WaiterPage destructures exactly { t, formatDateTime, currentLocale } from
// useI18n(). `currentLocale` MUST be a ref-like ({ value }) — the page reads
// currentLocale.value inside fmtOrderPrice / billDateTime / shiftRevenue. The
// mocked `t` returns its key verbatim (param-less) so own-template headings are
// assertable by key.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatDateTime: () => "",
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: onMounted fires several GETs (/staff/orders/, /staff/tables/,
// /staff/my-shift/, plus menu.fetchCategories → /categories/). Default: everything
// resolves empty so the no-orders path renders. Tests set _routes to drive the
// loaded path. _match / _routes are read ONLY inside the lazy vi.fn closures.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  // shared canonical extractor (added to lib/api; mock returns the fallback)
  extractApiErrorMessage: (err, fallback = "") => fallback,
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// idempotency is imported transitively by the waiter store.
vi.mock("../../lib/idempotency", () => ({
  newIdempotencyKey: () => "test-idem-key",
}));

// qrcode is a node_modules dep — Vitest externalizes it, so vi.mock('qrcode')
// cannot intercept the lazy import (same as the S2 leaflet observation).
// The loadQRCode seam in lib/qr.js is the mockable point instead.
vi.mock("../../lib/qr", () => ({
  loadQRCode: vi.fn(),
}));

import WaiterPage from "../WaiterPage.vue";

const mountPage = () =>
  shallowMount(WaiterPage, {
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

const tableOrder = (overrides = {}) => ({
  id: 1,
  order_number: "A100",
  status: "pending",
  fulfillment_type: "table",
  table_label: "Table 5",
  currency: "MAD",
  total: "120.00",
  items: [],
  created_at: new Date().toISOString(),
  status_updated_at: new Date().toISOString(),
  ...overrides,
});

describe("WaiterPage — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // localStorage FIRST: the page (firstRun / sound keys) and menu.fetchCategories'
    // staleCache are localStorage-backed, so a leaked write from a prior test would
    // change what this test's fresh mount sees.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // onMounted arms a 15s poll setInterval and useNowTicker a 30s ticker;
    // unmount runs onUnmounted → clearInterval so no timer leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) no orders: the core setup()/onMounted crash guard ─────────────────
  // The async onMounted (fetchOrders + loadTableStatuses + loadMyShift + the
  // poll/visibility wiring) and the whole template must render with empty data
  // and not throw.
  it("mounts and runs the real setup() + onMounted wiring without throwing", async () => {
    // The white-screen bug class throws synchronously inside setup(), so mount()
    // itself would throw — this assertion is the guard.
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    // Let onMounted's fetchOrders / loadTableStatuses / loadMyShift settle.
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // With no orders the page's OWN template renders the empty state (default tab
    // is "needs_action", not "recent"). The mocked t() returns the key verbatim.
    expect(wrapper.text()).toContain("waiterPage.noActiveOrders");
  });

  // ── (2) loaded, table-grouped board ───────────────────────────────────────
  // Two active dine-in orders on the same table drive the table-grouping computed
  // + own-template group header (label, tableStatus badge, order count, total via
  // fmtOrderPrice/settleOutstanding) — the exact own-template paths that only run
  // with a non-empty orders array. Both statuses (pending/ready) fall in the
  // default "needs_action" tab, so they are visible immediately.
  it("renders a loaded, table-grouped board without crashing", async () => {
    _routes = {
      "/staff/orders/": {
        data: {
          count: 2,
          results: [
            tableOrder({ id: 1, order_number: "A100", status: "pending" }),
            tableOrder({ id: 2, order_number: "A101", status: "ready", total: "80.00" }),
          ],
        },
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    const text = wrapper.text().replace(/\u00A0/g, " "); // Intl MAD uses NBSP
    // Own-template group header (NOT text inside the stubbed WaiterOrderCard).
    expect(text).toContain("Table 5");
    expect(text).toContain("waiterPage.tableTotal");
    // The empty state must be gone once orders are present.
    expect(text).not.toContain("waiterPage.noActiveOrders");
  });
});

// ── S3-A appends ─────────────────────────────────────────────────────────────
// One describe per gap. Each has its OWN isolation beforeEach/afterEach — the
// base describe's hooks do NOT run for appended describes (S2 lesson).
// Helpers that reach the mocked api / toast stores use dynamic import so the
// base file above stays an exact prefix (no new top-level imports).

describe("WaiterPage S3-A — B-33 table grouping keys on the slug", () => {
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

  // Group-header label spans: the only own-template spans whose text is exactly
  // the table label (order cards are stubbed, so no card text leaks in).
  const labelSpans = () =>
    wrapper.findAll("span").filter((w) => w.text() === "T1");

  it("keeps two same-label tables in different sections as two groups when their slugs differ", async () => {
    _routes = {
      "/staff/orders/": {
        data: {
          count: 2,
          results: [
            tableOrder({ id: 1, order_number: "A100", status: "pending", table_label: "T1", table_slug: "t1-north" }),
            tableOrder({ id: 2, order_number: "A101", status: "pending", table_label: "T1", table_slug: "t1-south" }),
          ],
        },
      },
    };
    wrapper = mountPage();
    await flushPromises();
    // One <section> per table group (line 342 is the only group section in
    // list view), each headed by its own "T1" label.
    expect(wrapper.findAll("section").length).toBe(2);
    expect(labelSpans().length).toBe(2);
  });

  it("still merges same-label orders into one group when no slug is present (label fallback)", async () => {
    _routes = {
      "/staff/orders/": {
        data: {
          count: 2,
          results: [
            tableOrder({ id: 1, order_number: "A100", status: "pending", table_label: "T1" }),
            tableOrder({ id: 2, order_number: "A101", status: "pending", table_label: "T1" }),
          ],
        },
      },
    };
    wrapper = mountPage();
    await flushPromises();
    expect(wrapper.findAll("section").length).toBe(1);
    expect(labelSpans().length).toBe(1);
  });
});

describe("WaiterPage S3-A — B-32 merge picker eligibility + error mapping", () => {
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

  const findButton = (label) => {
    const hits = wrapper.findAll("button").filter((b) => b.text() === label);
    return hits.length ? hits.at(0) : null;
  };

  const mountWithMergeOrders = async () => {
    _routes = {
      "/staff/orders/": {
        data: {
          count: 4,
          results: [
            tableOrder({ id: 1, order_number: "A100", status: "pending" }),
            tableOrder({ id: 2, order_number: "A101", status: "pending" }),
            tableOrder({ id: 3, order_number: "A102", status: "pending", payment_status: "paid" }),
            tableOrder({ id: 4, order_number: "A103", status: "pending", amount_paid: "40.00" }),
          ],
        },
      },
    };
    wrapper = mountPage();
    await flushPromises();
  };

  // Drive overflow sheet → Merge button for the FIRST card's order (A100,
  // the destination). @overflow="overflowOrder = order" ignores the payload,
  // so emitting on the first card is enough.
  const openMergeModal = async () => {
    const card = wrapper.findComponent({ name: "WaiterOrderCard" });
    expect(card.exists()).toBe(true);
    await card.vm.$emit("overflow");
    await flushPromises();
    const mergeBtn = findButton("waiterPage.mergeBtn");
    expect(mergeBtn).not.toBeNull();
    await mergeBtn.trigger("click");
    await flushPromises();
  };

  const mergeSelect = () =>
    wrapper.find('select[aria-label="waiterPage.mergeSrcLabel"]');

  const submitMergeRejecting = async (code) => {
    const api = (await import("../../lib/api")).default;
    api.post.mockRejectedValueOnce({ response: { data: { code } } });
    const select = mergeSelect();
    select.element.value = "2";
    await select.trigger("change");
    const confirmBtn = findButton("waiterPage.mergeConfirm");
    expect(confirmBtn).not.toBeNull();
    await confirmBtn.trigger("click");
    await flushPromises();
  };

  it("offers only the eligible unpaid source — paid and partially-paid orders are excluded", async () => {
    await mountWithMergeOrders();
    await openMergeModal();
    const select = mergeSelect();
    expect(select.exists()).toBe(true);
    // Placeholder "" + the one eligible source (A101, id 2). A102 is paid,
    // A103 carries a 40.00 partial — both would be 409s from the backend.
    const values = select.findAll("option").map((o) => o.attributes("value"));
    expect(values).toEqual(["", "2"]);
  });

  it("maps a 409 already_paid rejection to mergeSrcAlreadyPaid (inline + toast)", async () => {
    await mountWithMergeOrders();
    await openMergeModal();
    await submitMergeRejecting("already_paid");
    expect(wrapper.text()).toContain("waiterPage.mergeSrcAlreadyPaid");
    const { useToastStore } = await import("../../stores/toast");
    const toast = useToastStore();
    expect(toast.message).toBe("waiterPage.mergeSrcAlreadyPaid");
    expect(toast.type).toBe("error");
  });

  it("maps a 409 bad_status rejection to mergeBadStatus", async () => {
    await mountWithMergeOrders();
    await openMergeModal();
    await submitMergeRejecting("bad_status");
    expect(wrapper.text()).toContain("waiterPage.mergeBadStatus");
  });
});

describe("WaiterPage S3-A — B-34 auto-dirty toggle", () => {
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

  const openFloorView = async () => {
    const tabBar = wrapper.findComponent({ name: "WaiterStatusTabBar" });
    expect(tabBar.exists()).toBe(true);
    await tabBar.vm.$emit("update:floor-view", true);
    await flushPromises();
    await wrapper.vm.$nextTick();
  };

  const dirtySwitch = () => wrapper.find('button[role="switch"]');

  it("shows the toggle ON by default in the floor view and flips it off on tap (persisted)", async () => {
    _routes = { "/staff/orders/": { data: { count: 0, results: [] } } };
    wrapper = mountPage();
    await flushPromises();
    await openFloorView();
    expect(dirtySwitch().exists()).toBe(true);
    expect(dirtySwitch().attributes("aria-checked")).toBe("true");
    expect(dirtySwitch().text()).toContain("waiterPage.autoDirtyOn");
    await dirtySwitch().trigger("click");
    await flushPromises();
    expect(dirtySwitch().attributes("aria-checked")).toBe("false");
    expect(localStorage.getItem("waiter:auto-dirty:localhost")).toBe("off");
  });

  it("starts OFF when a previous choice was stored", async () => {
    localStorage.setItem("waiter:auto-dirty:localhost", "off");
    _routes = { "/staff/orders/": { data: { count: 0, results: [] } } };
    wrapper = mountPage();
    await flushPromises();
    await openFloorView();
    expect(dirtySwitch().attributes("aria-checked")).toBe("false");
  });
});

describe("WaiterPage S3-A — B-48 bill vs settle outstanding agree", () => {
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

  const mountBillOrder = async (overrides) => {
    _routes = {
      "/staff/orders/": {
        data: {
          count: 1,
          results: [
            tableOrder({ id: 1, order_number: "A100", status: "pending", total: "120.00", ...overrides }),
          ],
        },
      },
    };
    wrapper = mountPage();
    await flushPromises();
  };

  // Open the bill for the single loaded order via overflow → Bill.
  const openBill = async () => {
    const card = wrapper.findComponent({ name: "WaiterOrderCard" });
    expect(card.exists()).toBe(true);
    await card.vm.$emit("overflow");
    await flushPromises();
    // Bill button text is "🧾 waiterPage.billBtn" (emoji span + label) — match
    // by inclusion, not exact equality.
    const hits = wrapper.findAll("button").filter((b) => b.text().includes("waiterPage.billBtn"));
    expect(hits.length).toBeGreaterThan(0);
    await hits.at(0).trigger("click");
    await flushPromises();
  };

  it("uses the server outstanding (30.00) in both the group total and the bill when cash + legacy wallet partials coexist", async () => {
    // Cash partial 40 (ledger) + legacy wallet settle 50 (no ledger row) on a
    // 120 total: the old bill formula read 120 - 40 = 80, the old settle
    // fallback read 120 - 50 = 70. Both must now read the server's 30.
    await mountBillOrder({
      amount_paid: "40.00",
      wallet_amount_paid: "50.00",
      payments: [{ method: "cash", amount: "40.00" }],
      outstanding: "30.00",
    });
    await openBill();
    const text = wrapper.text().replace(/\u00A0/g, " "); // Intl MAD uses NBSP
    expect(text).toContain("MAD 30.00");
    expect(text).not.toContain("MAD 80.00");
    expect(text).not.toContain("MAD 70.00");
  });

  it("falls back to ledger + wallet-not-in-ledger when the server outstanding is absent", async () => {
    // Same mixed partials, no `outstanding` field: 120 - 40 (ledger) - 50
    // (wallet, not in the ledger) = 30.
    await mountBillOrder({
      amount_paid: "40.00",
      wallet_amount_paid: "50.00",
      payments: [{ method: "cash", amount: "40.00" }],
    });
    await openBill();
    const text = wrapper.text().replace(/\u00A0/g, " "); // Intl MAD uses NBSP
    expect(text).toContain("MAD 30.00");
    expect(text).not.toContain("MAD 80.00");
  });

  it("never understates what is owed when no payments breakdown is available", async () => {
    // No `outstanding`, no `payments` array: the wallet may already sit inside
    // the ledger, so only the larger signal is credited — 120 - 50 = 70, never
    // the double-credited 30 and never the old bill's 80.
    await mountBillOrder({ amount_paid: "40.00", wallet_amount_paid: "50.00" });
    await openBill();
    const text = wrapper.text().replace(/\u00A0/g, " "); // Intl MAD uses NBSP
    expect(text).toContain("MAD 70.00");
    expect(text).not.toContain("MAD 30.00");
    expect(text).not.toContain("MAD 80.00");
  });
});

describe("WaiterPage S3-A — B-10 table QR failure toasts instead of silently doing nothing", () => {
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

  it("toasts ownerTables.qrGenerateFailed when QR generation throws", async () => {
    // Fail QR generation at the mockable seam: lib/qr.js wraps the lazy
    // `qrcode` import, which Vitest cannot intercept (externalized dep).
    const { loadQRCode } = await import("../../lib/qr");
    loadQRCode.mockRejectedValueOnce(new Error("qrcode unavailable"));
    _routes = {
      "/staff/orders/": {
        data: {
          count: 1,
          results: [
            tableOrder({ id: 1, order_number: "A100", status: "pending", table_label: "Table 5", table_slug: "t1" }),
          ],
        },
      },
    };
    wrapper = mountPage();
    await flushPromises();
    const tabBar = wrapper.findComponent({ name: "WaiterStatusTabBar" });
    expect(tabBar.exists()).toBe(true);
    await tabBar.vm.$emit("update:floor-view", true);
    await flushPromises();
    const grid = wrapper.findComponent({ name: "WaiterFloorTileGrid" });
    expect(grid.exists()).toBe(true);
    const tiles = grid.props("tiles");
    expect(tiles.length).toBeGreaterThan(0);
    await grid.vm.$emit("toggle", tiles[0]);
    await flushPromises();
    const hits = wrapper.findAll("button").filter((b) => b.attributes("aria-label") === "waiterPage.showQR");
    expect(hits.length).toBeGreaterThan(0);
    await hits.at(0).trigger("click");
    await flushPromises();
    const { useToastStore } = await import("../../stores/toast");
    const toast = useToastStore();
    expect(toast.message).toBe("ownerTables.qrGenerateFailed");
    expect(toast.type).toBe("error");
  });
});

// ── S3-B (B-08 shift re-fetch, B-09 password confirm, B-13 reason codes) ────
// Appended, not rewritten: the base "mount smoke" describe above is untouched.
// Own isolation: this describe has its OWN beforeEach (localStorage.clear +
// setActivePinia(createPinia) + _routes reset + vi.clearAllMocks + the api
// mock implementations re-seeded) and its OWN afterEach (unmount, so the 15s
// poll / 30s ticker never leak). The base describe's hooks do NOT run here.
//
// Drive notes (shallowMount stubs): the tab bar / shift panel / order card /
// new-order sheet are auto-stubbed, so state is driven by emitting on the
// stubs (e.g. tabBar emits "new-order" / "update:activeTab" / "clock") and
// asserted via stub props (currentShift, shiftLoadError, pwForm). The void /
// comp sheets are the page's OWN template (Teleport is stubbed to <slot />),
// so their preset chips + submit buttons are real DOM. The mocked t() returns
// the key verbatim — which is exactly what makes the B-13 assertions work: a
// localized label would post "waiterPage.voidReasonWrongItem", the fixed code
// posts the bare key "voidReasonWrongItem".
describe("WaiterPage — S3-B", () => {
  let wrapper;
  let api;

  const shift = (overrides = {}) => ({ id: 9, clock_in: new Date().toISOString(), ...overrides });
  const tabBar = () => wrapper.findComponent({ name: "WaiterStatusTabBar" });
  const panel = () => wrapper.findComponent({ name: "WaiterShiftPanel" });
  const myShiftCalls = () => api.get.mock.calls.filter((c) => String(c[0]).includes("/staff/my-shift/"));
  const postsTo = (frag) => api.post.mock.calls.filter((c) => String(c[0]).includes(frag));

  // Mount-time /staff/my-shift/ fails; everything else resolves via _routes.
  const failShift = () =>
    api.get.mockImplementation((url) =>
      url.includes("/staff/my-shift/") ? Promise.reject(new Error("shift down")) : Promise.resolve(_match(url))
    );
  // /staff/my-shift/ succeeds with an open shift; everything else via _routes.
  const okShift = () =>
    api.get.mockImplementation((url) =>
      url.includes("/staff/my-shift/") ? Promise.resolve({ data: shift() }) : Promise.resolve(_match(url))
    );
  const openShiftTab = async () => {
    await tabBar().vm.$emit("update:activeTab", "shift");
    await flushPromises();
    await wrapper.vm.$nextTick();
  };
  const orderWithItem = (item) => {
    _routes = {
      "/staff/orders/": { data: { count: 1, results: [tableOrder({ id: 1, items: [item] })] } },
    };
  };

  beforeEach(async () => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    api = (await import("../../lib/api")).default;
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
    api.post.mockImplementation(() => Promise.resolve({ data: {} }));
    api.patch.mockImplementation(() => Promise.resolve({ data: {} }));
    api.delete.mockImplementation(() => Promise.resolve({ data: {} }));
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── B-08: shift-load failure must not block a clocked-in waiter ──────────
  it("B-08: re-fetches the shift before blocking a new order when the first load failed", async () => {
    failShift();
    wrapper = mountPage();
    await flushPromises();

    // Mount-time load failed: no shift, one my-shift call.
    expect(tabBar().props("currentShift")).toBeNull();
    expect(myShiftCalls()).toHaveLength(1);

    // The backend recovers; the guard tap re-fetches instead of refusing.
    okShift();
    await tabBar().vm.$emit("new-order");
    await flushPromises();
    await wrapper.vm.$nextTick();

    expect(myShiftCalls()).toHaveLength(2);
    expect(tabBar().props("currentShift")).toEqual(expect.objectContaining({ id: 9 }));
    expect(wrapper.findComponent({ name: "WaiterNewOrder" }).exists()).toBe(true);
  });

  it("B-08: still blocks the new order when the re-fetch also finds no shift", async () => {
    failShift();
    wrapper = mountPage();
    await flushPromises();

    await tabBar().vm.$emit("new-order");
    await flushPromises();
    await wrapper.vm.$nextTick();

    // The guard DID re-fetch (mount + one guard call) and still refused.
    expect(myShiftCalls()).toHaveLength(2);
    expect(wrapper.findComponent({ name: "WaiterNewOrder" }).exists()).toBe(false);
  });

  it("B-08: passes the shift-load error to the shift panel and Retry recovers", async () => {
    failShift();
    wrapper = mountPage();
    await flushPromises();
    await openShiftTab();

    expect(panel().props("shiftLoadError")).toBe("waiterPage.shiftLoadError");

    okShift();
    await panel().vm.$emit("retryShift");
    await flushPromises();
    await wrapper.vm.$nextTick();

    expect(panel().props("shiftLoadError")).toBe("");
    expect(tabBar().props("currentShift")).toEqual(expect.objectContaining({ id: 9 }));
  });

  it("B-08: clock-in tap re-checks the shift instead of posting a second clock-in", async () => {
    failShift();
    wrapper = mountPage();
    await flushPromises();

    okShift();
    await tabBar().vm.$emit("clock", "in");
    await flushPromises();
    await wrapper.vm.$nextTick();

    expect(postsTo("/staff/clock-in/")).toHaveLength(0);
    expect(tabBar().props("currentShift")).toEqual(expect.objectContaining({ id: 9 }));
  });

  // ── B-09: password change needs a matching confirm ───────────────────────
  it("B-09: a mismatched confirm blocks the password change and shows the mismatch error", async () => {
    wrapper = mountPage();
    await flushPromises();
    await openShiftTab();

    const form = panel().props("pwForm");
    form.current = "old-pass";
    form.next = "new-pass-1";
    form.confirm = "new-pass-2";
    await panel().vm.$emit("submitPassword");
    await flushPromises();

    expect(postsTo("/staff/change-password/")).toHaveLength(0);
    expect(panel().props("pwForm").error).toBe("staffPassword.confirmMismatch");
  });

  it("B-09: matching new + confirm posts the change and clears all three fields", async () => {
    wrapper = mountPage();
    await flushPromises();
    await openShiftTab();

    const form = panel().props("pwForm");
    form.current = "old-pass";
    form.next = "brand-new";
    form.confirm = "brand-new";
    await panel().vm.$emit("submitPassword");
    await flushPromises();

    const calls = postsTo("/staff/change-password/");
    expect(calls).toHaveLength(1);
    expect(calls[0][1]).toEqual({ current_password: "old-pass", new_password: "brand-new" });
    const cleared = panel().props("pwForm");
    expect(cleared.current).toBe("");
    expect(cleared.next).toBe("");
    expect(cleared.confirm).toBe("");
    expect(cleared.error).toBe("");
  });

  // ── B-13: void/comp reasons are stored as codes, not localized labels ────
  it("B-13: voiding with a preset sends the preset KEY, not the localized label", async () => {
    const item = { id: 7, dish_name: "Soup", subtotal: "30.00", unit_price: "30.00", qty: 1 };
    orderWithItem(item);
    wrapper = mountPage();
    await flushPromises();

    const card = wrapper.findComponent({ name: "WaiterOrderCard" });
    expect(card.exists()).toBe(true);
    await card.vm.$emit("void-item", item);
    await wrapper.vm.$nextTick();

    const chip = wrapper.findAll("button").find((b) => b.text() === "waiterPage.voidReasonWrongItem");
    expect(chip.exists()).toBe(true);
    await chip.trigger("click");
    const submit = wrapper.findAll("button").find((b) => b.text() === "waiterPage.voidItem");
    await submit.trigger("click");
    await flushPromises();

    const calls = postsTo("/void/");
    expect(calls).toHaveLength(1);
    expect(calls[0][0]).toContain("/staff/orders/1/items/7/void/");
    // The KEY, not the mocked-t label "waiterPage.voidReasonWrongItem".
    expect(calls[0][1]).toEqual({ reason: "voidReasonWrongItem" });
  });

  it("B-13: comping with a preset sends the preset KEY, not the localized label", async () => {
    const item = { id: 7, dish_name: "Soup", subtotal: "30.00", unit_price: "30.00", qty: 1 };
    orderWithItem(item);
    wrapper = mountPage();
    await flushPromises();

    const card = wrapper.findComponent({ name: "WaiterOrderCard" });
    await card.vm.$emit("comp-item", item);
    await wrapper.vm.$nextTick();

    const chip = wrapper.findAll("button").find((b) => b.text() === "waiterPage.compReasonGoodwill");
    expect(chip.exists()).toBe(true);
    await chip.trigger("click");
    const submit = wrapper.findAll("button").find((b) => b.text() === "waiterPage.compItem");
    await submit.trigger("click");
    await flushPromises();

    const calls = postsTo("/comp/");
    expect(calls).toHaveLength(1);
    expect(calls[0][0]).toContain("/staff/orders/1/items/7/comp/");
    expect(calls[0][1]).toEqual({ reason: "compReasonGoodwill" });
  });

  it("B-13: voiding with 'Other' still sends the typed free text verbatim", async () => {
    const item = { id: 7, dish_name: "Soup", subtotal: "30.00", unit_price: "30.00", qty: 1 };
    orderWithItem(item);
    wrapper = mountPage();
    await flushPromises();

    const card = wrapper.findComponent({ name: "WaiterOrderCard" });
    await card.vm.$emit("void-item", item);
    await wrapper.vm.$nextTick();

    const chip = wrapper.findAll("button").find((b) => b.text() === "waiterPage.voidReasonOther");
    expect(chip.exists()).toBe(true);
    await chip.trigger("click");
    const input = wrapper.find('input[aria-label="waiterPage.voidReasonOtherPlaceholder"]');
    expect(input.exists()).toBe(true);
    await input.setValue("Guest is allergic");
    const submit = wrapper.findAll("button").find((b) => b.text() === "waiterPage.voidItem");
    await submit.trigger("click");
    await flushPromises();

    expect(postsTo("/void/")).toHaveLength(1);
    expect(postsTo("/void/")[0][1]).toEqual({ reason: "Guest is allergic" });
  });
});

// ── Wave M M-21: Cash-full ignores a stale splitAmount ───────────────────────
// Appended, not rewritten. Own isolation (same pattern as the S3-A appends):
// the settle sheet is stubbed by shallowMount, so the flow is driven by
// emitting on the stubs — card emits "settle", sheet emits "pay-cash".
describe("WaiterPage M-21 — Cash-full ignores a stale splitAmount", () => {
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

  const mountSettleOrder = async () => {
    _routes = {
      "/staff/orders/": {
        data: {
          count: 1,
          results: [tableOrder({ id: 1, order_number: "A100", status: "pending", total: "120.00" })],
        },
      },
      // A live shift, or payCash refuses at the clock-in guard.
      "/staff/my-shift/": { data: { id: 9, clock_in: new Date().toISOString() } },
    };
    wrapper = mountPage();
    await flushPromises();
    const card = wrapper.findComponent({ name: "WaiterOrderCard" });
    expect(card.exists()).toBe(true);
    await card.vm.$emit("settle");
    await flushPromises();
    const sheet = wrapper.findComponent({ name: "WaiterSettleSheet" });
    expect(sheet.exists()).toBe(true);
    return sheet;
  };

  const spyPostPayment = async () => {
    const { useWaiterStore } = await import("../../stores/waiter");
    const waiter = useWaiterStore();
    return vi.spyOn(waiter, "postPayment").mockResolvedValue({ data: { completed: true }, errorCode: null });
  };

  it("posts a FULL cash payment (null amount) on pay-cash 'full' despite a typed splitAmount", async () => {
    const sheet = await mountSettleOrder();
    // Type a partial amount, then close the accordion (the stale value stays).
    await sheet.vm.$emit("update:splitAmount", "20.00");
    await sheet.vm.$emit("update:splitSectionOpen", false);
    await flushPromises();
    const postPayment = await spyPostPayment();
    await sheet.vm.$emit("pay-cash", "full");
    await flushPromises();
    expect(postPayment).toHaveBeenCalledTimes(1);
    expect(postPayment.mock.calls[0][0]).toBe(1); // order id
    expect(postPayment.mock.calls[0][1]).toBe("cash");
    expect(postPayment.mock.calls[0][2]).toBeNull(); // FULL — the stale "20.00" was ignored
  });

  it("posts the typed partial on pay-cash with no payload", async () => {
    const sheet = await mountSettleOrder();
    await sheet.vm.$emit("update:splitAmount", "20.00");
    await flushPromises();
    const postPayment = await spyPostPayment();
    await sheet.vm.$emit("pay-cash");
    await flushPromises();
    expect(postPayment).toHaveBeenCalledTimes(1);
    expect(postPayment.mock.calls[0][2]).toBe(20);
  });
});
