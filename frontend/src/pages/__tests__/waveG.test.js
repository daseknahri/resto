/**
 * Wave G targeted tests (2026-11-24): POS-UX-8/18/19/21/22/23/30/42/47/50.
 * P2-11 is backend-only (backend/tests/test_admin_wallet_bonus_readback.py).
 *
 * Two layers, as in Waves E/F:
 *   (1) i18n VALUE tests — import the real messages-en/fr/ar and assert the
 *       user-facing strings say the plain words. These lock the wording
 *       itself, which a mocked-t mount test cannot see.
 *   (2) Mount tests — mocked useI18n (t returns the key verbatim) + a
 *       URL-routed api mock + real pinia. They lock the structure: one filter
 *       band on the board, the due-soon text folded into the scheduled badge,
 *       money lines shown once, a cancel path for started orders, one settle
 *       label everywhere, per-table open-order chips + a counted delete
 *       warning, and the per-column import guide.
 *
 * NOT covered by a mount here: WaiterPage itself (POS-UX-8) — mounting the
 * waiter page pulls the waiter/menu/session stores, live polling and the
 * wake lock, none of which the one-line banner condition touches. The
 * condition is locked textually from the component source instead (same
 * rationale as Wave F scoping out Menu.vue).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import en from "../../i18n/messages-en.js";
import fr from "../../i18n/messages-fr.js";
import ar from "../../i18n/messages-ar.js";
import WaiterPageRaw from "../WaiterPage.vue?raw";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatDateTime: (v) => String(v),
    formatNumber: (v) => String(v),
    formatCurrency: (v) => String(v),
    itemCountLabel: (v) => `${v} items`,
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock (same pattern as the Wave E/F mount tests).
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    default: {
      get: vi.fn((url) => Promise.resolve(_match(url))),
      post: vi.fn(() => Promise.resolve({ data: {} })),
      patch: vi.fn(() => Promise.resolve({ data: {} })),
      put: vi.fn(() => Promise.resolve({ data: {} })),
      delete: vi.fn(() => Promise.resolve({ data: {} })),
    },
  };
});

vi.mock("../../composables/useOwnerRealtime", () => ({
  useOwnerRealtime: () => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    connected: { value: false },
    connectionState: { value: "polling" },
  }),
}));

// Fixed clock for the due-soon math (DUE_SOON_WINDOW_MIN = 30).
const FIXED_NOW = new Date("2026-11-24T12:00:00Z").getTime();
vi.mock("../../composables/useNowTicker", () => ({
  useNowTicker: () => ({ now: { value: FIXED_NOW } }),
}));

const confirmMock = vi.fn(() => Promise.resolve(false));
vi.mock("../../composables/useConfirmModal", () => ({
  useConfirmModal: () => ({ confirm: confirmMock }),
}));

vi.mock("../../composables/usePrintTicket", () => ({
  usePrintTicket: () => ({ printTicket: vi.fn() }),
}));

const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import OwnerOrders from "../OwnerOrders.vue";
import OwnerTables from "../OwnerTables.vue";
import OwnerMenuBuilder from "../OwnerMenuBuilder.vue";
import { useOrderStore } from "../../stores/order";

// ── (1) i18n values ─────────────────────────────────────────────────────────
describe("Wave G — i18n values", () => {
  // POS-UX-21: the board says what Home says ("Start now").
  it("says Start now on the board, matching Home, in every locale (POS-UX-21)", () => {
    expect(en.ownerOrders.releaseNow).toBe("Start now");
    expect(en.ownerHome.upcomingStartNow).toBe("Start now");
    expect(fr.ownerOrders.releaseNow).toBe("Lancer maintenant");
    expect(fr.ownerHome.upcomingStartNow).toBe("Lancer maintenant");
    expect(ar.ownerOrders.releaseNow).toBe("ابدأ الآن");
    expect(ar.ownerHome.upcomingStartNow).toBe("ابدأ الآن");
  });

  // POS-UX-30: per-column import guide exists, and the separator hint says
  // commas (the backend splits tags/allergens on commas — semicolons stored
  // one mangled tag). The old mono line is gone from the template (mount test).
  it("explains every import column and says commas, not semicolons (POS-UX-30)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      for (const key of [
        "importColCategory", "importColDish", "importColDescription",
        "importColPrice", "importColTags", "importColAllergens",
      ]) {
        expect(m.ownerMenuBuilder[key], `${name}.ownerMenuBuilder.${key}`).toBeTruthy();
      }
    }
    expect(en.ownerMenuBuilder.importHint2).toContain("commas");
    expect(en.ownerMenuBuilder.importHint2).not.toContain("semicolon");
    expect(fr.ownerMenuBuilder.importHint2).toContain("virgules");
    expect(fr.ownerMenuBuilder.importHint2).not.toContain("points-virgules");
    expect(ar.ownerMenuBuilder.importHint2).toContain("فواصل");
    expect(en.ownerMenuBuilder.importColPrice).toContain("12.50");
    expect(en.ownerMenuBuilder.importColTags).toContain("vegetarian");
    expect(en.ownerMenuBuilder.importColTags).toContain("commas");
    expect(en.ownerMenuBuilder.importColAllergens).toContain("gluten");
    expect(fr.ownerMenuBuilder.importColCategory).toContain("groupe");
    expect(ar.ownerMenuBuilder.importColDish).toContain("الطبق");
  });

  // POS-UX-42/47: open-order keys exist; the counted warning says the orders stay.
  it("names open-order counts for tables and the delete warning (POS-UX-42/47)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      for (const key of ["openOrders", "openOrdersTotal", "deleteLiveOrdersWarningWithCount"]) {
        expect(m.ownerTables[key], `${name}.ownerTables.${key}`).toBeTruthy();
      }
    }
    expect(en.ownerTables.openOrdersTotal).toContain("Open orders");
    expect(en.ownerTables.deleteLiveOrdersWarningWithCount).toContain("stay on the Orders board");
    expect(en.ownerTables.deleteLiveOrdersWarningWithCount).toContain("{count}");
    expect(fr.ownerTables.deleteLiveOrdersWarningWithCount).toContain("tableau des commandes");
    expect(ar.ownerTables.deleteLiveOrdersWarningWithCount).toContain("لوحة الطلبات");
  });

  // POS-UX-50: settleAndClose is gone everywhere; Mark paid is the one label.
  it("drops settleAndClose and keeps Mark paid in every locale (POS-UX-50)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      expect(m.ownerOrders.settleAndClose, `${name}.ownerOrders.settleAndClose`).toBeUndefined();
      expect(m.ownerOrders.markPaid, `${name}.ownerOrders.markPaid`).toBeTruthy();
    }
    expect(en.ownerOrders.markPaid).toBe("Mark paid");
    expect(fr.ownerOrders.markPaid).toBe("Marquer paye");
    expect(ar.ownerOrders.markPaid).toBe("تحديد كمدفوع");
  });

  // FR convention: new French values stay accent-free.
  it("keeps the new French values accent-free (FR file convention)", () => {
    const accented = /[àâäéèêëîïôöùûüç]/;
    for (const key of [
      "importColCategory", "importColDish", "importColDescription",
      "importColPrice", "importColTags", "importColAllergens",
      "openOrders", "openOrdersTotal", "deleteLiveOrdersWarningWithCount",
    ]) {
      const section = key.startsWith("importCol") ? fr.ownerMenuBuilder : fr.ownerTables;
      expect(section[key], `fr.${key}`).not.toMatch(accented);
    }
    expect(fr.ownerMenuBuilder.importHint2).not.toMatch(accented);
  });
});

// ── (2a) OwnerOrders — one filter band (POS-UX-22) ──────────────────────────
describe("Wave G — OwnerOrders one filter band (POS-UX-22)", () => {
  let wrapper;
  const order = (over) => ({
    id: 1, order_number: "G-1", status: "pending", fulfillment_type: "pickup",
    source: "direct", payment_status: "unpaid", total: 100, currency: "MAD",
    items_count: 2, items: [], created_at: new Date(FIXED_NOW - 5 * 60000).toISOString(),
    customer_name: "Test", tip_amount: 0, wallet_amount_paid: 0, amount_paid: 0,
    outstanding: 100, delivery_fee: 0, ...over,
  });
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

  const mountWith = async (orders) => {
    wrapper = shallowMount(OwnerOrders);
    await flushPromises();
    useOrderStore().orders = orders;
    await flushPromises();
    await wrapper.vm.$nextTick();
    return wrapper;
  };

  it("puts Active/Past and the status chips in one row, no standalone tab bar", async () => {
    await mountWith([order({})]);
    const activeBtn = wrapper.findAll("button").find((b) => b.text().includes("ownerOrders.tabActive"));
    const historyBtn = wrapper.findAll("button").find((b) => b.text().includes("ownerOrders.tabHistory"));
    expect(activeBtn.exists()).toBe(true);
    expect(historyBtn.exists()).toBe(true);
    // Same parent row, and that row is the chips scroll row.
    expect(activeBtn.element.parentElement).toBe(historyBtn.element.parentElement);
    expect(activeBtn.element.parentElement.className).toContain("ui-scroll-row");
    // The old standalone tab bar (segmented container) is gone.
    const oldBar = wrapper.findAll("div").find((d) => d.classes().includes("bg-slate-950/50") && d.attributes("role") === "tablist");
    expect(oldBar?.exists() ?? false).toBe(false);
    // The status chips are in that same row.
    const pendingChip = wrapper.findAll("button").find((b) => b.text().includes("ownerOrders.statusPending"));
    expect(pendingChip.exists()).toBe(true);
    expect(pendingChip.element.parentElement).toBe(activeBtn.element.parentElement);
  });

  it("folds due-soon into the scheduled badge instead of a second badge (POS-UX-18)", async () => {
    const due = order({
      id: 2, order_number: "G-2", status: "scheduled",
      scheduled_for: new Date(FIXED_NOW + 10 * 60000).toISOString(),
    });
    const later = order({
      id: 3, order_number: "G-3", status: "scheduled",
      scheduled_for: new Date(FIXED_NOW + 90 * 60000).toISOString(),
    });
    await mountWith([due, later]);
    const dueIso = new Date(FIXED_NOW + 10 * 60000).toISOString();
    const laterIso = new Date(FIXED_NOW + 90 * 60000).toISOString();
    // The merged badge is the one pill carrying BOTH the fire time and the
    // due-soon text (the inner "· Due soon" span nests inside it, and the
    // upcoming strip also prints the fire time in a plain span, so a bare
    // text search would over-count).
    const isPill = (s) => s.classes().includes("rounded-full");
    const dueBadges = wrapper.findAll("span").filter((s) => isPill(s) && s.text().includes(dueIso) && s.text().includes("ownerOrders.dueSoonBadge"));
    expect(dueBadges).toHaveLength(1);
    expect(dueBadges[0].classes()).toContain("bg-amber-500/20");
    // The not-due order's scheduled badge stays violet with no due-soon text.
    const laterBadges = wrapper.findAll("span").filter((s) => isPill(s) && s.text().includes(laterIso));
    expect(laterBadges).toHaveLength(1);
    expect(laterBadges[0].text()).not.toContain("ownerOrders.dueSoonBadge");
    expect(laterBadges[0].classes()).toContain("bg-violet-500/15");
  });

  it("shows the marketplace source as plain text, not a badge (POS-UX-18)", async () => {
    await mountWith([order({ source: "marketplace" })]);
    const badges = wrapper.findAll("span").filter((s) => s.text().includes("ownerOrders.sourceMarketplace"));
    expect(badges).toHaveLength(1);
    expect(badges[0].classes()).not.toContain("rounded-full");
    expect(badges[0].classes()).toContain("text-slate-500");
  });

  it("shows tip / wallet-paid / paid-so-far once, in the header totals (POS-UX-19)", async () => {
    await mountWith([order({
      tip_amount: 5, wallet_amount_paid: 20, amount_paid: 30, delivery_fee: 8,
    })]);
    const grid = wrapper.findAll("div").find((d) => d.classes().includes("sm:grid-cols-2"));
    expect(grid.exists()).toBe(true);
    expect(grid.text()).toContain("ownerOrders.deliveryFee");
    expect(grid.text()).not.toContain("ownerOrders.tip");
    expect(grid.text()).not.toContain("ownerOrders.walletPaid");
    expect(grid.text()).not.toContain("waiterPage.paidSoFar");
    const totals = wrapper.findAll("div").find((d) => d.classes().includes("text-end"));
    expect(totals.exists()).toBe(true);
    expect(totals.text()).toContain("ownerOrders.tip");
    expect(totals.text()).toContain("ownerOrders.walletPaid");
    expect(totals.text()).toContain("waiterPage.paidSoFar");
  });

  it("offers cancel on started orders, not just early ones (POS-UX-23)", async () => {
    await mountWith([
      order({ id: 11, order_number: "G-11", status: "preparing" }),
      order({ id: 12, order_number: "G-12", status: "ready" }),
      order({ id: 13, order_number: "G-13", status: "out_for_delivery", fulfillment_type: "delivery" }),
    ]);
    const cancels = wrapper.findAll("button").filter((b) => b.text().includes("ownerOrders.cancel"));
    expect(cancels.length).toBe(3);
  });

  it("labels the settle button Mark paid on a ready order (POS-UX-50)", async () => {
    await mountWith([order({ status: "ready", payment_status: "unpaid" })]);
    expect(wrapper.text()).not.toContain("ownerOrders.settleAndClose");
    const settle = wrapper.findAll("button").find((b) => b.text().includes("ownerOrders.markPaid"));
    expect(settle.exists()).toBe(true);
  });

  it("says Start now on the scheduled order's board button (POS-UX-21)", async () => {
    await mountWith([order({ status: "scheduled" })]);
    const btn = wrapper.findAll("button").find((b) => b.text().includes("ownerOrders.releaseNow"));
    expect(btn.exists()).toBe(true);
    expect(btn.text()).not.toContain("Release now");
  });
});

// ── (2b) OwnerTables — open-order chips + counted delete warning (42/47) ───
describe("Wave G — OwnerTables open orders (POS-UX-42/47)", () => {
  let wrapper;
  const busy = { id: 1, label: "Table 1", slug: "t1", is_active: true, position: 0, open_orders: 2 };
  const quiet = { id: 2, label: "Table 2", slug: "t2", is_active: true, position: 0, open_orders: 0 };
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = { "/tables/": { data: [busy, quiet] } };
    vi.clearAllMocks();
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  const mountTables = async () => {
    wrapper = shallowMount(OwnerTables);
    const deadline = Date.now() + 5000;
    let deletes = [];
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 100));
      await flushPromises();
      deletes = wrapper.findAll("button").filter((b) => b.text().includes("ownerTables.delete"));
      // Two tables × (mobile details + desktop row) = 4 Delete buttons.
      if (deletes.length === 4) break;
    }
    expect(deletes).toHaveLength(4);
    return wrapper;
  };

  it("shows the per-table count and the header total (POS-UX-42)", async () => {
    await mountTables();
    expect(wrapper.text()).toContain('ownerTables.openOrders({"count":2})');
    expect(wrapper.text()).toContain('ownerTables.openOrdersTotal({"count":2})');
    // The quiet table gets no chip: exactly one openOrders chip.
    const chips = wrapper.findAll("span").filter((s) => s.text().includes("ownerTables.openOrders({"));
    expect(chips).toHaveLength(1);
  });

  it("names the live count in the delete confirm (POS-UX-47)", async () => {
    await mountTables();
    const deletes = wrapper.findAll("button").filter((b) => b.text().includes("ownerTables.delete"));
    // deletes[0] = busy table (mobile), deletes[2] = quiet table (mobile).
    await deletes[0].trigger("click");
    await flushPromises();
    expect(confirmMock).toHaveBeenCalledTimes(1);
    const opts = confirmMock.mock.calls[0][0];
    expect(opts.body).toContain('ownerTables.deleteLiveOrdersWarningWithCount({"count":2})');
    confirmMock.mockClear();
    await deletes[2].trigger("click");
    await flushPromises();
    expect(confirmMock).toHaveBeenCalledTimes(1);
    expect(confirmMock.mock.calls[0][0].body).toContain("ownerTables.deleteLiveOrdersWarning");
    expect(confirmMock.mock.calls[0][0].body).not.toContain("WithCount");
  });
});

// ── (2c) OwnerMenuBuilder — per-column import guide (POS-UX-30) ─────────────
describe("Wave G — OwnerMenuBuilder import guide (POS-UX-30)", () => {
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
    document.body.innerHTML = "";
    _routes = {};
  });

  it("lists every column with its explanation, no bare mono line", async () => {
    wrapper = shallowMount(OwnerMenuBuilder, {
      global: { stubs: { Teleport: true, Transition: true } },
    });
    await flushPromises();
    const importBtn = wrapper.findAll("button").find((b) => b.text().includes("ownerMenuBuilder.importCsv"));
    expect(importBtn.exists()).toBe(true);
    await importBtn.trigger("click");
    await flushPromises();
    const terms = wrapper.findAll("dt").map((d) => d.text());
    expect(terms).toEqual(["category_name", "dish_name", "description", "price", "tags", "allergens"]);
    for (const key of [
      "ownerMenuBuilder.importColCategory", "ownerMenuBuilder.importColDish",
      "ownerMenuBuilder.importColDescription", "ownerMenuBuilder.importColPrice",
      "ownerMenuBuilder.importColTags", "ownerMenuBuilder.importColAllergens",
    ]) {
      expect(wrapper.text()).toContain(key);
    }
    expect(wrapper.text()).not.toContain("category_name, dish_name, description, price, tags, allergens");
  });
});

// ── (2d) WaiterPage — install banner waits for first-run (POS-UX-8) ─────────
// Textual lock (see the file header for why there is no mount here).
describe("Wave G — WaiterPage banner order (POS-UX-8)", () => {
  it("shows the install banner only once the first-run banner is gone", () => {
    expect(WaiterPageRaw).toContain("v-if=\"!isStandalone && !installDismissed && waiterFirstRunSeen\"");
    expect(WaiterPageRaw).not.toContain("v-if=\"!isStandalone && !installDismissed\"");
  });
});
