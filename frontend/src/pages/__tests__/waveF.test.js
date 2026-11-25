/**
 * Wave F targeted tests (2026-11-23): QR-2/QR-3, POS-UX-5/7/9/13/14/17/25/26/
 * 34/36/37/40/43/44/45.
 *
 * Two layers, as in Wave E:
 *   (1) i18n VALUE tests — import the real messages-en/fr/ar and assert the
 *       user-facing strings say the plain words. These lock the wording
 *       itself, which a mocked-t mount test cannot see.
 *   (2) Mount tests — mocked useI18n (t returns the key verbatim) + a
 *       URL-routed api mock + real pinia. They lock the structure: the cash
 *       hint sits under the field, the compact settle button shows its label,
 *       the Wallet page links the Z-report, the Focus button carries its hint,
 *       the flash lasts 15s and dismisses, the KDS buttons carry titles, the
 *       date picker defaults to today, the counted hint shows while empty,
 *       Delete sits apart from the copy buttons, and only one Refresh remains.
 *
 * NOT covered here: Menu.vue itself (QR-2 dead banner + QR-3 sign-in hint) —
 * mounting the customer menu needs the route table slug + customer store and
 * is covered by the i18n values + `npm run build` + `npm run lint` instead.
 * The QR-3 hint and the dead banner are plain template blocks behind
 * v-if="tableContextBanner" / v-if="tableContextDead".
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import en from "../../i18n/messages-en.js";
import fr from "../../i18n/messages-fr.js";
import ar from "../../i18n/messages-ar.js";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatDateTime: (v) => String(v),
    formatNumber: (v) => String(v),
    formatCurrency: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock (same pattern as the Wave E mount tests).
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

const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import OwnerKitchen from "../OwnerKitchen.vue";
import OwnerHome from "../OwnerHome.vue";
import OwnerWallet from "../OwnerWallet.vue";
import OwnerZReport from "../OwnerZReport.vue";
import OwnerTables from "../OwnerTables.vue";
import WaiterSettleSheet from "../../components/WaiterSettleSheet.vue";
import WaiterOrderCard from "../../components/WaiterOrderCard.vue";
import { useOrderStore } from "../../stores/order";

// ── (1) i18n values ─────────────────────────────────────────────────────────
describe("Wave F — i18n values", () => {
  // QR-2: the dead-table copy exists and is plain in every locale.
  it("has the dead-table banner copy in every locale (QR-2)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      for (const key of ["tableDeadTitle", "tableDeadBody", "tableDeadHint"]) {
        expect(m.menu[key], `${name}.menu.${key}`).toBeTruthy();
      }
    }
    expect(en.menu.tableDeadTitle).toBe("This table code doesn't work anymore");
    expect(en.menu.tableDeadBody).toContain("ask staff for a new code");
    expect(en.menu.tableDeadHint).toContain("browse the menu");
    expect(fr.menu.tableDeadTitle).toBe("Ce code de table ne fonctionne plus");
    expect(ar.menu.tableDeadTitle).toBe("رمز الطاولة هذا لم يعد يعمل");
  });

  // QR-3: the sign-in hint says why signing in matters (link the order,
  // order from home later, or leave a phone to reclaim it).
  it("has the table sign-in hint in every locale (QR-3)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      expect(m.menu.tableSignInHint, `${name}.menu.tableSignInHint`).toBeTruthy();
      expect(m.menu.tableSignInLink, `${name}.menu.tableSignInLink`).toBeTruthy();
    }
    expect(en.menu.tableSignInHint).toContain("order from home later");
    expect(en.menu.tableSignInHint).toContain("leave your phone");
    expect(en.menu.tableSignInLink).toBe("Sign in");
    expect(fr.menu.tableSignInLink).toBe("Se connecter");
    expect(ar.menu.tableSignInLink).toBe("تسجيل الدخول");
  });

  // POS-UX-37 + POS-UX-40: the Wallet page signposts takings and explains the float.
  it("signposts takings from the Wallet page and explains the float (POS-UX-37/40)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      expect(m.ownerWallet.takingsLink, `${name}.ownerWallet.takingsLink`).toBeTruthy();
    }
    expect(en.ownerWallet.takingsLink).toContain("Z-report");
    expect(en.ownerWallet.floatSubtitle).toContain("not today's takings");
    expect(en.ownerWallet.floatSubtitle).not.toContain("Funded by the platform");
    expect(fr.ownerWallet.floatSubtitle).toContain("Ce ne sont pas les recettes du jour");
    expect(ar.ownerWallet.floatSubtitle).toContain("ليست إيرادات اليوم");
  });

  // POS-UX-5: the cash hint says the field only works out the change.
  it("explains Cash received only works out the change (POS-UX-5)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      expect(m.waiterPage.cashReceivedHint, `${name}.waiterPage.cashReceivedHint`).toBeTruthy();
    }
    expect(en.waiterPage.cashReceivedHint).toContain("Only works out the change");
    expect(en.waiterPage.cashReceivedHint).toContain("full amount");
    expect(fr.waiterPage.cashReceivedHint).toContain("Calcule seulement la monnaie");
    expect(ar.waiterPage.cashReceivedHint).toContain("يحسب الباقي فقط");
  });

  // POS-UX-7: take-money and add-money no longer share a phrase.
  it("names the two opposite wallet directions differently (POS-UX-7)", () => {
    expect(en.waiterPage.chargeWalletBtn).toBe("Take wallet payment");
    expect(en.ownerWallet.topupBtn).toBe("Top up wallet");
    expect(fr.waiterPage.chargeWalletBtn).toBe("Encaisser par portefeuille");
    expect(fr.ownerWallet.topupBtn).toBe("Recharger le portefeuille");
    // AR was already distinct — locked so a later "harmonisation" can't merge them.
    expect(ar.waiterPage.chargeWalletBtn).toBe("خصم من المحفظة");
    expect(ar.ownerWallet.topupBtn).toBe("شحن المحفظة");
  });

  // POS-UX-13 + POS-UX-14: Focus and the plan-mode chip explain themselves.
  it("explains Focus mode and the plan-mode chip (POS-UX-13/14)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      expect(m.ownerHome.focusHint, `${name}.ownerHome.focusHint`).toBeTruthy();
    }
    expect(en.ownerHome.focusHint).toContain("one next action at a time");
    expect(en.ownerHome.checkoutEnabled).toBe("Online checkout on");
    expect(en.ownerHome.whatsappEnabled).toBe("WhatsApp ordering on");
    expect(en.ownerHome.browseOnly).toBe("Browse only — no ordering");
    expect(fr.ownerHome.checkoutEnabled).toBe("Paiement en ligne actif");
    expect(fr.ownerHome.browseOnly).toBe("Navigation seule — pas de commande");
    expect(ar.ownerHome.checkoutEnabled).toBe("الطلب والدفع عبر الإنترنت مفعّل");
    expect(ar.ownerHome.browseOnly).toBe("تصفح فقط — بدون طلب");
  });

  // POS-UX-25 + POS-UX-26: the KDS hints and the Live/Polling rewording.
  it("explains All-day / Include held and rewords Live / Polling (POS-UX-25/26)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      expect(m.kitchen.allDayHint, `${name}.kitchen.allDayHint`).toBeTruthy();
      expect(m.kitchen.includeHeldHint, `${name}.kitchen.includeHeldHint`).toBeTruthy();
    }
    expect(en.kitchen.allDayHint).toContain("across all orders today");
    expect(en.kitchen.includeHeldHint).toContain("hasn't started yet");
    expect(en.kitchen.live).toBe("Live updates");
    expect(en.kitchen.pollingMode).toBe("Checking for updates");
    expect(fr.kitchen.live).toBe("Mises a jour en direct");
    expect(fr.kitchen.pollingMode).toBe("Verification des nouveautes");
    expect(ar.kitchen.live).toBe("تحديثات مباشرة");
    expect(ar.kitchen.pollingMode).toBe("جارٍ التحقق من التحديثات");
  });

  // POS-UX-36: the counted-empty hint says what enables the close button.
  it("explains the close button waits for the counted total (POS-UX-36)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      expect(m.zReport.countedEmptyHint, `${name}.zReport.countedEmptyHint`).toBeTruthy();
    }
    expect(en.zReport.countedEmptyHint).toContain("Enter the counted total");
    expect(fr.zReport.countedEmptyHint).toContain("Saisissez le total compte");
    expect(ar.zReport.countedEmptyHint).toContain("أدخل الإجمالي المحسوب");
  });

  // POS-UX-43 + POS-UX-45: the QR copy toast and the Position rewording.
  it("rewords the QR copy toast and the Position fields (POS-UX-43/45)", () => {
    expect(en.ownerTables.qrCopied).toBe("QR image copied");
    expect(en.ownerTables.qrCopied).not.toContain("data");
    expect(fr.ownerTables.qrCopied).toBe("Image QR copiee");
    expect(ar.ownerTables.qrCopied).toBe("تم نسخ صورة QR");
    expect(en.ownerTables.position).toBe("Sort order");
    expect(en.ownerTables.positionFrom).toBe("Sort order starts at");
    expect(fr.ownerTables.position).toBe("Ordre de tri");
    expect(fr.ownerTables.positionFrom).toBe("Ordre de tri a partir de");
    // AR was already plain — locked.
    expect(ar.ownerTables.position).toBe("الترتيب");
    expect(ar.ownerTables.positionFrom).toBe("الترتيب يبدأ من");
  });

  // FR convention: no accented letters in the new/changed French values.
  it("keeps the new French values accent-free (FR file convention)", () => {
    const accented = /[àáâäèéêëìíîïòóôöùúûüýÿçñ]/;
    const values = [
      en && fr.menu.tableDeadTitle, fr.menu.tableDeadBody, fr.menu.tableDeadHint,
      fr.menu.tableSignInHint, fr.menu.tableSignInLink,
      fr.ownerWallet.takingsLink, fr.ownerWallet.floatSubtitle,
      fr.waiterPage.cashReceivedHint, fr.waiterPage.chargeWalletBtn, fr.ownerWallet.topupBtn,
      fr.ownerHome.focusHint, fr.ownerHome.checkoutEnabled, fr.ownerHome.browseOnly,
      fr.kitchen.allDayHint, fr.kitchen.includeHeldHint, fr.kitchen.live, fr.kitchen.pollingMode,
      fr.zReport.countedEmptyHint,
      fr.ownerTables.qrCopied, fr.ownerTables.position, fr.ownerTables.positionFrom,
    ];
    for (const v of values) expect(v, v).not.toMatch(accented);
  });
});

// ── (2a) WaiterSettleSheet — POS-UX-5 ───────────────────────────────────────
describe("Wave F — WaiterSettleSheet cash hint (POS-UX-5)", () => {
  it("shows the change-only hint under the Cash received field", () => {
    const wrapper = shallowMount(WaiterSettleSheet, {
      props: {
        order: { id: 1, currency: "MAD" },
        settleOutstanding: () => 100,
        fmtOrderPrice: (v) => `${v} MAD`,
        seatGroupLabel: () => "",
      },
    });
    expect(wrapper.find("#waiter-cash-received").exists()).toBe(true);
    expect(wrapper.text()).toContain("waiterPage.cashReceivedHint");
    wrapper.unmount();
  });
});

// ── (2b) WaiterOrderCard — POS-UX-9 ─────────────────────────────────────────
describe("Wave F — WaiterOrderCard compact settle (POS-UX-9)", () => {
  const fn = () => "";
  const boolFn = () => false;
  const mountCard = () =>
    shallowMount(WaiterOrderCard, {
      props: {
        order: {
          id: 1,
          order_number: "A1",
          status: "confirmed",
          payment_status: "unpaid",
          fulfillment_type: "dine-in",
          items: [],
          created_at: new Date().toISOString(),
        },
        canManage: true,
        waiter: { nextStatus: () => "ready", updatingOrderIds: new Set() },
        itemReadyStatuses: new Set(["preparing"]),
        terminalStatuses: new Set(["done"]),
        appendableTableStatuses: new Set(["confirmed"]),
        statusCardClass: fn,
        orderHeadline: (o) => `Order ${o.order_number}`,
        timeUrgencyClass: fn,
        timeAgo: () => "now",
        formatScheduledFor: fn,
        waiterDjChipClass: fn,
        waiterDjChipLabel: fn,
        statusChipClass: fn,
        statusBorderClass: fn,
        isItemHeld: boolFn,
        canCompPaidOrder: boolFn,
        canVoidPaidOrder: boolFn,
        fmtOrderPrice: fn,
        actionBtnClass: fn,
        actionLabel: () => "Advance",
        lowestHeldCourse: () => null,
        orderElapsedLabel: fn,
        orderElapsedClass: fn,
      },
    });

  it("shows the visible Settle label on the compact button, not just the icon", () => {
    const wrapper = mountCard();
    // The compact settle button exists (next status + unpaid) and its
    // aria-label is the same key as the full-width button's label.
    const compact = wrapper.find('button[aria-label="ownerOrders.markPaid"]');
    expect(compact.exists()).toBe(true);
    // The 💵 is still there, but now the words are visible too.
    expect(compact.text()).toContain("💵");
    expect(compact.text()).toContain("ownerOrders.markPaid");
    wrapper.unmount();
  });
});

// ── (2c) OwnerWallet — POS-UX-37 ────────────────────────────────────────────
describe("Wave F — OwnerWallet takings link (POS-UX-37)", () => {
  let wrapper;
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = { "/owner/wallet/float/": { data: { float_balance: "250.00" } } };
    vi.clearAllMocks();
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  it("links today's takings to the Z-report from under the float card", async () => {
    wrapper = shallowMount(OwnerWallet, {
      global: { stubs: { RouterLink: RouterLinkStub } },
    });
    await flushPromises();
    expect(wrapper.text()).toContain("ownerWallet.takingsLink");
    const link = wrapper
      .findAllComponents({ name: "RouterLink" })
      .find((c) => c.text().includes("ownerWallet.takingsLink"));
    expect(link.exists()).toBe(true);
    expect(link.props("to")).toStrictEqual({ name: "owner-z-report" });
  });
});

// ── (2d) OwnerHome — POS-UX-13 + POS-UX-17 ──────────────────────────────────
describe("Wave F — OwnerHome focus hint + flash (POS-UX-13/17)", () => {
  let wrapper;
  const mountHome = () =>
    shallowMount(OwnerHome, {
      global: {
        stubs: {
          RouterLink: RouterLinkStub,
          Transition: { template: "<slot />" },
          Teleport: { template: "<slot />" },
        },
      },
    });
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {
      "/owner/dashboard/": {
        data: {
          revenue_summary: {
            marketplace: { order_count: 3, revenue: "120.00", commission_total: "12.00" },
            daily: [],
          },
        },
      },
    };
    vi.clearAllMocks();
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    vi.useRealTimers();
  });

  const triggerFlash = async () => {
    const orderStore = useOrderStore();
    // First assignment only seeds the known IDs — no flash.
    orderStore.orders = [{ id: 1, status: "pending", created_at: new Date().toISOString() }];
    await flushPromises();
    expect(wrapper.text()).not.toContain("ownerHome.newOrderArrived");
    // A genuinely new pending order triggers the flash + timer.
    orderStore.orders = [
      { id: 1, status: "pending", created_at: new Date().toISOString() },
      { id: 2, status: "pending", created_at: new Date().toISOString() },
    ];
    await flushPromises();
    expect(wrapper.text()).toContain("ownerHome.newOrderArrived");
  };

  it("explains Focus mode on the button itself (POS-UX-13)", async () => {
    wrapper = mountHome();
    await flushPromises();
    expect(wrapper.find('button[title="ownerHome.focusHint"]').exists()).toBe(true);
  });

  it("dismisses the new-order flash with the × button (POS-UX-17)", async () => {
    wrapper = mountHome();
    await flushPromises();
    await triggerFlash();
    const dismiss = wrapper.find('button[aria-label="common.dismiss"]');
    expect(dismiss.exists()).toBe(true);
    await dismiss.trigger("click");
    expect(wrapper.text()).not.toContain("ownerHome.newOrderArrived");
  });

  it("keeps the flash up for 15 seconds, not 6 (POS-UX-17)", async () => {
    vi.useFakeTimers();
    wrapper = mountHome();
    await flushPromises();
    await triggerFlash();
    // At 6s — the old timeout — the banner is still up.
    vi.advanceTimersByTime(6000);
    await flushPromises();
    expect(wrapper.text()).toContain("ownerHome.newOrderArrived");
    // At 15s it goes away on its own.
    vi.advanceTimersByTime(9000);
    await flushPromises();
    expect(wrapper.text()).not.toContain("ownerHome.newOrderArrived");
  });
});

// ── (2e) OwnerKitchen — POS-UX-25 ───────────────────────────────────────────
describe("Wave F — OwnerKitchen hints (POS-UX-25)", () => {
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

  it("titles the All-day toggle and the Include-held toggle", async () => {
    wrapper = shallowMount(OwnerKitchen);
    await flushPromises();
    expect(wrapper.find('button[title="kitchen.allDayHint"]').exists()).toBe(true);
    // Include-held lives in the all-day section — open it first.
    const allDayBtn = wrapper.find('button[aria-label="kitchen.allDay"]');
    expect(allDayBtn.exists()).toBe(true);
    await allDayBtn.trigger("click");
    await flushPromises();
    expect(wrapper.find('button[title="kitchen.includeHeldHint"]').exists()).toBe(true);
  });
});

// ── (2f) OwnerZReport — POS-UX-34 + POS-UX-36 ───────────────────────────────
describe("Wave F — OwnerZReport date default + counted hint (POS-UX-34/36)", () => {
  let wrapper;
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {
      "/owner/z-report/": { data: null },
      "/owner/drawer/history/": {
        data: { sessions: [{ id: 1, status: "open", expected_total: "120.00" }] },
      },
    };
    vi.clearAllMocks();
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  it("defaults the date picker to today and explains the disabled close button", async () => {
    wrapper = shallowMount(OwnerZReport);
    await flushPromises();
    // POS-UX-34: the picker shows today's date instead of starting blank.
    const dateInput = wrapper.find('input[type="date"]');
    expect(dateInput.exists()).toBe(true);
    expect(dateInput.element.value).toBe(new Date().toISOString().slice(0, 10));
    // POS-UX-36: with an open drawer and an empty counted field, the hint
    // shows and the close button is disabled.
    expect(wrapper.text()).toContain("zReport.countedEmptyHint");
    const closeBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("zReport.closeDrawerBtn"));
    expect(closeBtn.exists()).toBe(true);
    expect(closeBtn.attributes("disabled")).toBeDefined();
  });
});

// ── (2g) OwnerTables — POS-UX-44 + POS-UX-45 ────────────────────────────────
describe("Wave F — OwnerTables delete demotion + single refresh (POS-UX-44/45)", () => {
  let wrapper;
  const table = { id: 1, label: "Table 1", slug: "t1", is_active: true, position: 0 };
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = { "/tables/": { data: [table] } };
    vi.clearAllMocks();
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  it("keeps Delete out of both action grids and shows one Refresh", async () => {
    wrapper = shallowMount(OwnerTables);
    // The cards render only after fetchTables + the lazy QR batch finish
    // (dynamic import("qrcode") is real async work, not just microtasks),
    // so wait until the Delete buttons appear instead of one flushPromises.
    const deadline = Date.now() + 5000;
    let deletes = [];
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 100));
      await flushPromises();
      deletes = wrapper
        .findAll("button")
        .filter((b) => b.text().includes("ownerTables.delete"));
      if (deletes.length === 2) break;
    }
    // Two Delete buttons (mobile details + desktop article), each in its own
    // separated row below the grid — never inside the grid itself.
    expect(deletes).toHaveLength(2);
    for (const del of deletes) {
      expect(del.element.parentElement.className).toContain("border-t");
    }
    // The mobile more-actions grid holds the copies, not Delete.
    const mobileGrid = wrapper.find("details div.grid");
    expect(mobileGrid.exists()).toBe(true);
    expect(mobileGrid.text()).not.toContain("ownerTables.delete");
    // The desktop grid holds the copies, not Delete. (The cards list itself
    // is also sm:grid-cols-2, so pin the grid by its lg:grid-cols-3 class.)
    const desktopGrid = wrapper
      .findAll("div")
      .find((d) => d.classes().includes("lg:grid-cols-3"));
    expect(desktopGrid.exists()).toBe(true);
    expect(desktopGrid.text()).not.toContain("ownerTables.delete");
    // POS-UX-45: exactly one Refresh button (the header one).
    const refreshes = wrapper
      .findAll("button")
      .filter((b) => b.text().includes("common.refresh"));
    expect(refreshes).toHaveLength(1);
  });
});
