/**
 * Unit tests for OwnerKitchenOrderCard — the kitchen order tile extracted from
 * OwnerKitchen.vue (RISK FE-2, the most coupled block). It renders one order and
 * forwards every action via emits (toggleItem / fireCourse / markAllReady /
 * advance / printTicket); the activeOrders grid, prepStation, the waiter store and
 * all display helpers stay in the parent (helpers passed as function props).
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import OwnerKitchenOrderCard from "../OwnerKitchenOrderCard.vue";

const order = (overrides = {}) => ({
  id: 5,
  order_number: "1042",
  status: "pending",
  created_at: "2026-01-01T00:00:00Z",
  customer_name: "Sam",
  fulfillment_type: "dine_in",
  items: [
    { id: 1, qty: 2, dish_name: "Pizza", is_ready: false, station: "grill", course: 1 },
    { id: 2, qty: 1, dish_name: "Salad", is_ready: true },
    { id: 3, qty: 1, dish_name: "Voided", is_voided: true },
  ],
  ...overrides,
});

// Stub helpers — simple, deterministic implementations so the card renders.
const helpers = () => ({
  cardClass: () => "card-x",
  stripClass: () => "strip-x",
  headlineColorClass: () => "hl-x",
  orderHeadline: (o) => `HL:${o.order_number}`,
  chipClass: () => "chip-x",
  elapsedBadgeClass: () => "eb-x",
  elapsedMinutes: () => 5,
  elapsedLabel: () => "5m",
  timeAgo: () => "2m",
  formatScheduledFor: () => "later",
  kitchenDueSoon: () => false,
  djChipClass: () => "dj-x",
  djChipLabel: () => "DJ",
  orderReadyCount: () => ({ done: 1, total: 2 }),
  isItemHeld: () => false,
  lowestHeldCourse: () => null,
  hasUnreadyItems: () => true,
  allItemsReady: () => false,
  actionBtnClass: () => "ab-x",
  actionLabel: () => "Start cooking",
});

const mountCard = (props = {}, waiterOverrides = {}) =>
  mount(OwnerKitchenOrderCard, {
    props: {
      order: order(),
      index: 0,
      prepStation: "",
      firingCourseOrderId: null,
      waiter: { nextStatus: () => "ready", updatingOrderIds: new Set(), ...waiterOverrides },
      ...helpers(),
      ...props,
    },
  });

describe("OwnerKitchenOrderCard", () => {
  it("renders the headline, order number and status chip", () => {
    const w = mountCard();
    expect(w.text()).toContain("HL:1042");
    expect(w.text()).toContain("#1042");
    expect(w.text()).toContain("kitchen.status_pending");
  });

  it("renders each non-voided item and strikes out voided ones", () => {
    const w = mountCard();
    expect(w.text()).toContain("Pizza");
    expect(w.text()).toContain("Salad");
    // voided item is shown but not as a toggle button
    expect(w.find('[aria-label="kitchen.itemVoided:{\\"name\\":\\"Voided\\"}"]').exists()).toBe(true);
  });

  it("emits toggleItem with (order, item) when an item is tapped", async () => {
    const o = order();
    const w = mountCard({ order: o });
    // the first item toggle button (aria-pressed present)
    const itemBtn = w.findAll('button[aria-pressed]')[0];
    await itemBtn.trigger("click");
    expect(w.emitted("toggleItem")[0]).toEqual([o, o.items[0]]);
  });

  it("shows the ready-progress pill from orderReadyCount", () => {
    const w = mountCard();
    expect(w.text()).toContain("1/2");
  });

  it("shows the fire-course button only when a held course exists and emits fireCourse", async () => {
    expect(mountCard({ lowestHeldCourse: () => null }).text()).not.toContain("waiterPage.fireCourse");
    const o = order();
    const w = mountCard({ order: o, lowestHeldCourse: () => 2 });
    const btn = w.findAll("button").find((b) => b.text().includes("waiterPage.fireCourse"));
    await btn.trigger("click");
    expect(w.emitted("fireCourse")[0]).toEqual([o]);
  });

  it("disables the fire-course button while that order is firing", () => {
    const w = mountCard({ lowestHeldCourse: () => 2, firingCourseOrderId: 5 });
    const btn = w.findAll("button").find((b) => b.text().includes("waiterPage.firingCourse"));
    expect(btn).toBeTruthy();
    expect(btn.attributes("disabled")).toBeDefined();
  });

  it("shows mark-all-ready when there are unready items and emits markAllReady", async () => {
    const o = order();
    const w = mountCard({ order: o, hasUnreadyItems: () => true });
    const btn = w.findAll("button").find((b) => b.text().includes("kitchen.markAllReady"));
    await btn.trigger("click");
    expect(w.emitted("markAllReady")[0]).toEqual([o]);
  });

  it("emits advance with the order id from the primary action button", async () => {
    const o = order();
    const w = mountCard({ order: o });
    const btn = w.findAll("button").find((b) => b.text().includes("Start cooking"));
    await btn.trigger("click");
    expect(w.emitted("advance")[0]).toEqual([o.id]);
  });

  it("disables the primary action while the order is updating", () => {
    const w = mountCard({}, { updatingOrderIds: new Set([5]) });
    // the primary action shows an ellipsis + is disabled
    const btn = w.findAll("button").find((b) => b.attributes("aria-busy") === "true");
    expect(btn).toBeTruthy();
    expect(btn.attributes("disabled")).toBeDefined();
  });

  it("shows the handed-off note when there is no next status", () => {
    const w = mountCard({}, { nextStatus: () => null });
    expect(w.text()).toContain("kitchen.handedOff");
  });

  it("emits printTicket when the print button is clicked", async () => {
    const o = order();
    const w = mountCard({ order: o });
    const btn = w.findAll("button").find((b) => b.text().includes("ownerOrders.printTicket"));
    await btn.trigger("click");
    expect(w.emitted("printTicket")[0]).toEqual([o]);
  });
});
