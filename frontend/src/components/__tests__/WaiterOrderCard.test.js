/**
 * Unit tests for WaiterOrderCard — the unified waiter order card extracted from
 * WaiterPage.vue (RISK FE-2). One component now backs the three near-identical
 * card loops (table-grouped / non-table / flat-list); the two variant flags
 * showElapsed / showCombos gate the only differences. It embeds WaiterOrderItem
 * (stubbed here) and re-emits its events; every action is an emit; all display
 * helpers + the waiter store are props.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import WaiterOrderCard from "../WaiterOrderCard.vue";

const order = (overrides = {}) => ({
  id: 5,
  order_number: "1042",
  status: "preparing",
  created_at: "2026-01-01T00:00:00Z",
  customer_name: "Sam",
  section_name: "",
  scheduled_for: null,
  fulfillment_type: "table",
  delivery_job: null,
  items: [{ id: 1, dish_name: "Pizza", combo_components: [{ dish_id: 9, name: "Coke", qty: 1 }], qty: 2 }],
  customer_note: "",
  owner_note: "",
  estimated_ready_minutes: 15,
  total: "50",
  currency: "MAD",
  payment_status: "unpaid",
  amount_paid: "0",
  outstanding: "50",
  ...overrides,
});

// Stub WaiterOrderItem to a simple <li> that can emit the three item events.
const WaiterOrderItemStub = {
  name: "WaiterOrderItem",
  props: ["item"],
  emits: ["toggleReady", "comp", "void"],
  template: `<li class="woi">{{ item.dish_name }}
    <button class="woi-ready" @click="$emit('toggleReady')" />
    <button class="woi-comp" @click="$emit('comp')" />
    <button class="woi-void" @click="$emit('void')" /></li>`,
};

const fnprops = () => ({
  statusCardClass: () => "cc", orderHeadline: (o) => `HL:${o.order_number}`,
  timeUrgencyClass: () => "tu", timeAgo: () => "2m", formatScheduledFor: () => "later",
  waiterDjChipClass: () => "dj", waiterDjChipLabel: () => "DJ", statusChipClass: () => "sc",
  statusBorderClass: () => "sb", isItemHeld: () => false, canCompPaidOrder: () => true,
  canVoidPaidOrder: () => true, fmtOrderPrice: (a) => `$${a}`, actionBtnClass: () => "ab",
  actionLabel: () => "Start", lowestHeldCourse: () => null,
  orderElapsedLabel: () => "12m", orderElapsedClass: () => "ec",
});

const mountCard = (props = {}) =>
  mount(WaiterOrderCard, {
    props: {
      order: order(), index: 0, canManage: true,
      waiter: { nextStatus: () => "ready", updatingOrderIds: new Set() },
      firingCourseOrderId: null, allReadyBusyIds: new Set(),
      compingItemId: null, voidingItemId: null,
      itemReadyStatuses: new Set(["preparing", "ready"]),
      terminalStatuses: new Set(["completed", "cancelled"]),
      appendableTableStatuses: new Set(["preparing", "confirmed"]),
      showElapsed: false, showCombos: false,
      ...fnprops(), ...props,
    },
    global: { stubs: { WaiterOrderItem: WaiterOrderItemStub } },
  });

describe("WaiterOrderCard", () => {
  it("renders the header (headline, order number, status chip)", () => {
    const w = mountCard();
    expect(w.text()).toContain("HL:1042");
    expect(w.text()).toContain("#1042");
    expect(w.text()).toContain("waiterPage.status_preparing");
  });

  it("shows the elapsed badge only when showElapsed is true", () => {
    expect(mountCard({ showElapsed: false }).text()).not.toContain("12m");
    expect(mountCard({ showElapsed: true }).text()).toContain("12m");
  });

  it("renders combo sub-lines only when showCombos is true", () => {
    expect(mountCard({ showCombos: false }).text()).not.toContain("Coke");
    expect(mountCard({ showCombos: true }).text()).toContain("Coke");
  });

  it("renders a WaiterOrderItem per item and re-emits its events with the item", async () => {
    const o = order();
    const w = mountCard({ order: o, showCombos: false });
    expect(w.find(".woi").exists()).toBe(true);
    await w.find(".woi-ready").trigger("click");
    await w.find(".woi-comp").trigger("click");
    await w.find(".woi-void").trigger("click");
    expect(w.emitted("toggleItemReady")[0]).toEqual([o.items[0]]);
    expect(w.emitted("compItem")[0]).toEqual([o.items[0]]);
    expect(w.emitted("voidItem")[0]).toEqual([o.items[0]]);
  });

  it("shows the scheduled + delivery chips conditionally", () => {
    expect(mountCard({ order: order({ scheduled_for: "2026-01-02" }) }).text()).toContain("later");
    expect(mountCard({ order: order({ fulfillment_type: "delivery", delivery_job: { status: "searching" } }) }).text()).toContain("DJ");
  });

  it("renders the eta, total and payment status", () => {
    const w = mountCard();
    expect(w.text()).toContain('waiterPage.eta:{"minutes":15}');
    expect(w.text()).toContain("$50");
    expect(w.text()).toContain("ownerOrders.unpaid");
  });

  it("emits advance from the primary action button", async () => {
    const w = mountCard();
    const btn = w.findAll("button").find((b) => b.text().includes("Start"));
    await btn.trigger("click");
    expect(w.emitted("advance")).toBeTruthy();
  });

  it("shows the settle button when no next status + unpaid, and emits settle", async () => {
    const w = mountCard({ waiter: { nextStatus: () => null, updatingOrderIds: new Set() }, order: order({ payment_status: "unpaid" }) });
    const btn = w.findAll("button").find((b) => b.text().includes("ownerOrders.markPaid") || b.text().includes("ownerOrders.settleAndClose"));
    await btn.trigger("click");
    expect(w.emitted("settle")).toBeTruthy();
  });

  it("emits append / fireCourse / allReady / overflow from the secondary actions", async () => {
    // append: table + appendable + unpaid + has next status
    await mountCard().findAll("button").find((b) => b.text().includes("waiterPage.addItems")).trigger("click");
    // fireCourse: lowestHeldCourse !== null
    const fireW = mountCard({ lowestHeldCourse: () => 2 });
    await fireW.findAll("button").find((b) => b.text().includes("waiterPage.fireCourse")).trigger("click");
    expect(fireW.emitted("fireCourse")).toBeTruthy();
    // allReady: no held course, kitchen-active, has an unready item
    const arW = mountCard({ lowestHeldCourse: () => null, order: order({ items: [{ id: 1, dish_name: "X", is_ready: false, is_voided: false }] }) });
    await arW.findAll("button").find((b) => b.text().includes("waiterPage.allReadyBtn")).trigger("click");
    expect(arW.emitted("allReady")).toBeTruthy();
    // overflow: the "…" button
    const ovW = mountCard();
    await ovW.findAll("button").find((b) => b.attributes("aria-label") === "common.more").trigger("click");
    expect(ovW.emitted("overflow")).toBeTruthy();
  });

  it("hides the action buttons when the waiter cannot manage orders", () => {
    const w = mountCard({ canManage: false, waiter: { nextStatus: () => "ready", updatingOrderIds: new Set() } });
    expect(w.findAll("button").some((b) => b.text().includes("Start"))).toBe(false);
    expect(w.findAll("button").some((b) => b.attributes("aria-label") === "common.more")).toBe(true); // overflow always shows
  });
});
