/**
 * Wave E targeted tests (2026-11-23): POS-UX-48, POS-UX-3/4/6, POS-UX-12/16,
 * POS-UX-24/27, POS-UX-28, POS-UX-38/39.
 *
 * Two layers:
 *   (1) i18n VALUE tests — import the real messages-en/fr/ar and assert the
 *       user-facing strings say the plain words (no "86", no "Check", the
 *       clock-in toast names the button + its position). These lock the wording
 *       itself, which a mocked-t mount test cannot see.
 *   (2) Mount tests — mocked useI18n (t returns the key verbatim) + a
 *       URL-routed api mock + real pinia, pattern-faithful to the existing
 *       *.mount.test.js files. They lock the structure: the pinned button is
 *       outside the scroll container, the mini-bar appears with a cart item,
 *       the strip is 2-col on phones, the quick actions link the three daily
 *       destinations, the toolbar labels are visible, the KDS buttons carry
 *       labels, the tap affordance renders.
 *
 * NOT covered here: POS-UX-6's scrollIntoView/focus itself — it needs the real
 * tab bar in the DOM (shallowMount stubs it, so getElementById finds nothing
 * and the call no-ops). It is covered by the tab-bar id test below (the anchor
 * the guard looks up) + `npm run build` + `npm run lint`.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, mount, flushPromises } from "@vue/test-utils";
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

// URL-routed api mock (same pattern as OwnerHome/OwnerKitchen mount tests).
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", async (importOriginal) => {
  // Keep the real named exports (mapApiErrorCode, extractApiErrorMessage, …):
  // OwnerMenuBuilder's graph (StepSuperCategories → onboardingApi) imports
  // them, and a default-only mock fails collection. Only `default` (the
  // axios client) is replaced. The vi.fn closures read _match lazily at call
  // time, so no TDZ on the hoisted factory.
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
import OwnerKitchenOrderCard from "../../components/OwnerKitchenOrderCard.vue";
import WaiterStatusTabBar from "../../components/WaiterStatusTabBar.vue";
import WaiterNewOrder from "../../components/WaiterNewOrder.vue";
import OwnerHome from "../OwnerHome.vue";
import OwnerMenuBuilder from "../OwnerMenuBuilder.vue";

// ── (1) i18n values ─────────────────────────────────────────────────────────
describe("Wave E — i18n values", () => {
  // POS-UX-48: no user-facing "86" anywhere in the three locales.
  it("retires the 86 shorthand from every user-facing string (POS-UX-48)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      for (const key of ["eightySixTitle", "eightySixSoldOut", "eightySixOpen"]) {
        expect(m.kitchen[key], `${name}.kitchen.${key}`).not.toContain("86");
      }
      expect(m.ownerOrders.eightySixBoardBtn, `${name}.ownerOrders.eightySixBoardBtn`).not.toContain("86");
      expect(m.ownerHome.dish86d, `${name}.ownerHome.dish86d`).not.toContain("86");
    }
    expect(en.kitchen.eightySixTitle).toBe("Sold out");
    expect(en.kitchen.eightySixSoldOut).toBe("Sold out");
    expect(en.kitchen.eightySixOpen).toBe("Open sold-out board");
    expect(en.ownerOrders.eightySixBoardBtn).toBe("Sold out");
    expect(en.ownerHome.dish86d).toBe("Sold out");
  });

  // POS-UX-24: the new KDS label keys exist and are non-empty in all locales.
  it("has the KDS top-bar label keys in every locale (POS-UX-24)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      for (const key of ["soundLabel", "autoPrintLabel", "fullscreenLabel"]) {
        expect(m.kitchen[key], `${name}.kitchen.${key}`).toBeTruthy();
      }
    }
    expect(en.kitchen.soundLabel).toBe("Sound");
    expect(en.kitchen.autoPrintLabel).toBe("Print");
    expect(en.kitchen.fullscreenLabel).toBe("Full screen");
  });

  // POS-UX-4: the mini-bar's review key exists in every locale.
  it("has the review-cart key in every locale (POS-UX-4)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      expect(m.waiterPage.newOrderReviewCart, `${name}.waiterPage.newOrderReviewCart`).toBeTruthy();
    }
    expect(en.waiterPage.newOrderReviewCart).toBe("Review cart");
  });

  // POS-UX-6: the refusal names the Clock in button and where it sits.
  it("the clock-in refusal names the button and its position (POS-UX-6)", () => {
    expect(en.waiterPage.mustClockInFirst).toContain("Clock in");
    expect(en.waiterPage.mustClockInFirst).toContain("top of this page");
    expect(fr.waiterPage.mustClockInFirst).toContain("Pointer");
    expect(fr.waiterPage.mustClockInFirst).toContain("haut");
    expect(ar.waiterPage.mustClockInFirst).toContain("تسجيل الحضور");
    expect(ar.waiterPage.mustClockInFirst).toContain("أعلى");
  });

  // POS-UX-39: the driver cash-out lookup no longer says "Check".
  it("the driver cash-out lookup says Look up, not Check (POS-UX-39)", () => {
    expect(en.ownerWallet.driverCashoutLookup).toBe("Look up");
    expect(fr.ownerWallet.driverCashoutLookup).toBe("Rechercher");
    expect(ar.ownerWallet.driverCashoutLookup).toBe("ابحث");
  });

  // POS-UX-38: the Owner Wallet copy was already correct — lock it so the
  // audit's stale claim can't come back as a "fix". (The scan hint lives in
  // the walletCharge section, not ownerWallet — that was the audit's stale
  // attribution; the value itself is the correct one.)
  it("the Owner Wallet scan/search copy is already correct (POS-UX-38)", () => {
    expect(en.ownerWallet.scanTitle).toBe("Scan pay code");
    expect(en.walletCharge.scanHint).toContain("paste it");
    expect(en.ownerWallet.searchPlaceholder).toContain("name");
    expect(en.ownerWallet.searchPlaceholder).toContain("phone");
    expect(fr.ownerWallet.searchPlaceholder).toContain("nom");
    expect(ar.ownerWallet.searchPlaceholder).toContain("الاسم");
  });
});

// ── (2a) OwnerKitchen top bar — POS-UX-24 + POS-UX-48 ───────────────────────
describe("Wave E — OwnerKitchen top bar (POS-UX-24 + POS-UX-48)", () => {
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

  it("labels the sound / print / full-screen buttons and shows Sold out, not 86", async () => {
    wrapper = shallowMount(OwnerKitchen);
    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // The three icon-only buttons now carry a visible text label each.
    expect(wrapper.text()).toContain("kitchen.soundLabel");
    expect(wrapper.text()).toContain("kitchen.autoPrintLabel");
    expect(wrapper.text()).toContain("kitchen.fullscreenLabel");
    // The 86 board button shows the board title instead of the "86" glyph.
    expect(wrapper.text()).toContain("kitchen.eightySixTitle");
    expect(wrapper.find('button[aria-label="kitchen.eightySixOpen"]').exists()).toBe(true);
    // No bare "86" anywhere on the empty board (keys say "eightySix", never "86").
    expect(wrapper.text()).not.toContain("86");
  });
});

// ── (2b) OwnerKitchenOrderCard — POS-UX-27 ──────────────────────────────────
describe("Wave E — OwnerKitchenOrderCard tap affordance (POS-UX-27)", () => {
  const order = {
    id: 1,
    order_number: "K100",
    status: "preparing",
    fulfillment_type: "table",
    table_label: "T3",
    customer_name: "Sara",
    created_at: new Date().toISOString(),
    scheduled_for: null,
    fired_course: 1,
    delivery_job: null,
    items: [
      { id: 11, dish_name: "Burger", qty: 2, course: 0, station: "grill", is_ready: false, is_voided: false },
      { id: 12, dish_name: "Fries", qty: 1, course: 0, station: "fry", is_ready: true, is_voided: false },
    ],
  };
  const fn = () => "";
  const boolFn = () => false;
  const mountCard = () =>
    mount(OwnerKitchenOrderCard, {
      props: {
        order,
        index: 0,
        prepStation: "",
        firingCourseOrderId: null,
        markingAllOrderIds: new Set(),
        waiter: { nextStatus: () => "ready", updatingOrderIds: new Set() },
        cardClass: fn,
        stripClass: fn,
        headlineColorClass: fn,
        orderHeadline: (o) => `Order ${o.order_number}`,
        chipClass: fn,
        elapsedBadgeClass: fn,
        elapsedMinutes: () => 5,
        elapsedLabel: () => "5 min",
        timeAgo: () => "now",
        formatScheduledFor: fn,
        kitchenDueSoon: boolFn,
        djChipClass: fn,
        djChipLabel: fn,
        orderReadyCount: (o) => {
          // Mirrors the parent's shape: { done, total } over trackable items.
          const trackable = o.items.filter((i) => i.id != null && !i.is_voided);
          return { done: trackable.filter((i) => i.is_ready).length, total: trackable.length };
        },
        isItemHeld: boolFn,
        lowestHeldCourse: () => null,
        hasUnreadyItems: (o) => o.items.some((i) => !i.is_ready && !i.is_voided),
        allItemsReady: (o) => o.items.every((i) => i.is_ready || i.is_voided),
        actionBtnClass: fn,
        actionLabel: fn,
      },
    });

  it("shows an empty circle for the unready item and a checkmark for the ready one", () => {
    const wrapper = mountCard();
    const burgerRow = wrapper.findAll("button").find((b) => b.text().includes("Burger"));
    const friesRow = wrapper.findAll("button").find((b) => b.text().includes("Fries"));
    expect(burgerRow.exists()).toBe(true);
    expect(friesRow.exists()).toBe(true);
    // Unready row: the empty circle, no checkmark svg.
    expect(burgerRow.findAll("span.rounded-full.border-2")).toHaveLength(1);
    expect(burgerRow.find("svg").exists()).toBe(false);
    // Ready row: the checkmark svg, no empty circle.
    expect(friesRow.find("svg").exists()).toBe(true);
    expect(friesRow.findAll("span.rounded-full.border-2")).toHaveLength(0);
    // The hint line that explains the tap is still there.
    expect(wrapper.text()).toContain("kitchen.tapItemReady");
    wrapper.unmount();
  });

  it("tapping the unready row emits toggleItem with the order and the item", async () => {
    const wrapper = mountCard();
    const row = wrapper.findAll("button").find((b) => b.text().includes("Burger"));
    expect(row.exists()).toBe(true);
    await row.trigger("click");
    const emitted = wrapper.emitted("toggleItem");
    expect(emitted).toBeTruthy();
    // toStrictEqual, not toBe: the emitted order is Vue's reactive proxy of
    // the prop object, so Object.is identity fails on a deep-equal value.
    expect(emitted[0][0]).toStrictEqual(order);
    expect(emitted[0][1].id).toBe(11);
    wrapper.unmount();
  });
});

// ── (2c) WaiterStatusTabBar — POS-UX-3 + POS-UX-6 anchor ────────────────────
describe("Wave E — WaiterStatusTabBar pinned New order (POS-UX-3 + POS-UX-6)", () => {
  const mountBar = () =>
    shallowMount(WaiterStatusTabBar, {
      props: {
        tabs: [
          { key: "pending", label: "Pending", count: 0 },
          { key: "confirmed", label: "Confirmed", count: 1 },
        ],
        canManage: true,
        formatDateTime: (v) => String(v),
      },
    });

  it("keeps + New order outside the scrolling strip and gives the clock-in button a stable id", () => {
    const wrapper = mountBar();
    const newOrderBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("waiterPage.newOrderBtn"));
    expect(newOrderBtn.exists()).toBe(true);
    // The button must NOT live inside the horizontally scrolling container.
    const scroller = wrapper.find(".overflow-x-auto");
    expect(scroller.exists()).toBe(true);
    expect(scroller.text()).not.toContain("waiterPage.newOrderBtn");
    // The clock-in button (the POS-UX-6 guard's anchor) is findable by id.
    expect(wrapper.find("#waiter-clock-in-btn").exists()).toBe(true);
    wrapper.unmount();
  });
});

// ── (2d) WaiterNewOrder — POS-UX-4 ──────────────────────────────────────────
describe("Wave E — WaiterNewOrder sticky cart (POS-UX-4)", () => {
  let wrapper;
  const dish = {
    slug: "burger",
    name: "Burger",
    price: "50.00",
    is_available: true,
    options: [],
    option_groups: [],
    tags: [],
    allergens: [],
  };
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {
      "/categories/": { data: [{ slug: "mains", name: "Mains", dishes: [dish] }] },
      "/dishes/": { data: [dish] },
    };
    vi.clearAllMocks();
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  const mountNewOrder = () =>
    // attachTo: document.body — the focus test needs the component connected
    // to the document, because jsdom's focus() is a no-op on detached nodes.
    shallowMount(WaiterNewOrder, {
      attachTo: document.body,
      global: { stubs: { Teleport: { template: "<slot />" } } },
    });

  it("caps the cart panel on mobile and hides the mini-bar while the cart is empty", async () => {
    wrapper = mountNewOrder();
    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // (a) the right panel carries the mobile height cap.
    const capped = wrapper
      .findAll("div")
      .find((d) => d.classes().includes("max-h-[46vh]"));
    expect(capped.exists()).toBe(true);
    // (b) no mini-bar before anything is added.
    expect(wrapper.text()).not.toContain("waiterPage.newOrderReviewCart");
  });

  it("shows the mini-bar with the total once a dish is added, and Review cart focuses submit", async () => {
    wrapper = mountNewOrder();
    await flushPromises();
    const addBtn = wrapper.find('button[aria-label="dishPage.increaseQuantity Burger"]');
    expect(addBtn.exists()).toBe(true);
    await addBtn.trigger("click");
    await flushPromises();
    // The mini-bar renders with the total and the review key.
    expect(wrapper.text()).toContain("waiterPage.newOrderReviewCart");
    const miniBar = wrapper
      .findAll("div")
      .find((d) => d.classes().includes("md:hidden") && d.text().includes("waiterPage.newOrderReviewCart"));
    expect(miniBar.exists()).toBe(true);
    expect(miniBar.text()).toContain("50");
    // Review cart focuses the submit button.
    const reviewBtn = miniBar.find("button");
    await reviewBtn.trigger("click");
    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("waiterPage.newOrderSubmit"));
    expect(submitBtn.exists()).toBe(true);
    expect(document.activeElement).toBe(submitBtn.element);
  });
});

// ── (2e) OwnerHome — POS-UX-12 + POS-UX-16 ──────────────────────────────────
describe("Wave E — OwnerHome strip + quick actions (POS-UX-12 + POS-UX-16)", () => {
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
  });

  it("renders the marketplace strip 2-col on phones, 4-col from sm up (POS-UX-12)", async () => {
    wrapper = mountHome();
    await flushPromises();
    const strip = wrapper
      .findAll("div")
      .find((d) => d.text().includes("ownerHome.marketplaceOrders") && d.classes().includes("grid"));
    expect(strip.exists()).toBe(true);
    expect(strip.classes()).toContain("grid-cols-2");
    expect(strip.classes()).toContain("sm:grid-cols-4");
  });

  it("links Kitchen, Tables & QR and Day close from the quick actions (POS-UX-16)", async () => {
    wrapper = mountHome();
    await flushPromises();
    const tos = wrapper
      .findAllComponents({ name: "RouterLink" })
      .map((c) => c.props("to"));
    expect(tos).toContainEqual({ name: "owner-kitchen" });
    expect(tos).toContainEqual({ name: "owner-tables" });
    expect(tos).toContainEqual({ name: "owner-z-report" });
  });
});

// ── (2f) OwnerMenuBuilder — POS-UX-28 ────────────────────────────────────────
describe("Wave E — OwnerMenuBuilder toolbar labels (POS-UX-28)", () => {
  it("shows the Preview / Templates / Import CSV labels on all widths", async () => {
    setActivePinia(createPinia());
    _routes = {};
    const wrapper = shallowMount(OwnerMenuBuilder);
    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    for (const key of ["ownerLayout.publicPreview", "ownerTemplates.button", "ownerMenuBuilder.importCsv"]) {
      // Preview is an <a>, Templates / Import are <button>s.
      const el = wrapper.findAll("button, a").find((b) => b.text().includes(key));
      expect(el.exists()).toBe(true);
      // The label is a plain visible span now — no hidden-sm:inline span and
      // no sr-only duplicate announcing it twice.
      expect(el.html()).not.toContain("hidden sm:inline");
      expect(el.html()).not.toContain("sr-only");
    }
    wrapper.unmount();
    _routes = {};
  });
});
