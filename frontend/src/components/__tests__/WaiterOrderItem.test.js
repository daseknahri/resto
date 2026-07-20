/**
 * Unit tests for WaiterOrderItem — a single order-item row extracted from
 * WaiterPage.vue's order cards (RISK FE-2). It DRYs the item <li> that was
 * identical across three of the four card loops. Display + tap-to-ready / comp /
 * void affordances, forwarded as toggleReady / comp / void emits; all order-
 * derived flags are computed in the parent and passed as props.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import WaiterOrderItem from "../WaiterOrderItem.vue";

const item = (overrides = {}) => ({
  id: 1,
  qty: 2,
  dish_name: "Pizza",
  note: "",
  course: 0,
  is_ready: false,
  is_voided: false,
  is_comped: false,
  ...overrides,
});

const mountItem = (props = {}) =>
  mount(WaiterOrderItem, {
    props: {
      item: item(),
      held: false,
      canManage: true,
      canComp: true,
      canVoid: true,
      readyToggleable: true,
      notTerminal: true,
      comping: false,
      voiding: false,
      ...props,
    },
  });

describe("WaiterOrderItem", () => {
  it("renders the quantity and dish name", () => {
    const w = mountItem();
    expect(w.text()).toContain("2");
    expect(w.text()).toContain("Pizza");
  });

  it("shows the note only when present", () => {
    expect(mountItem({ item: item({ note: "no onions" }) }).text()).toContain("no onions");
    expect(mountItem({ item: item({ note: "" }) }).text()).not.toContain("(");
  });

  it("shows the course chip (or held chip) for a coursed, non-voided item", () => {
    expect(mountItem({ item: item({ course: 2 }), held: false }).text()).toContain('waiterPage.courseChip:{"n":2}');
    expect(mountItem({ item: item({ course: 2 }), held: true }).text()).toContain("waiterPage.heldChip");
  });

  it("shows the voided badge and no affordances for a voided item", () => {
    const w = mountItem({ item: item({ is_voided: true }) });
    expect(w.text()).toContain("waiterPage.voidedBadge");
    expect(w.find('button[aria-pressed]').exists()).toBe(false);
  });

  it("shows the comped badge for a comped item", () => {
    expect(mountItem({ item: item({ is_comped: true }) }).text()).toContain("waiterPage.compedBadge");
  });

  it("shows the tap-to-ready toggle and emits toggleReady when clicked", async () => {
    const w = mountItem({ item: item({ is_ready: false }), readyToggleable: true });
    const btn = w.find('button[aria-pressed]');
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    expect(w.emitted("toggleReady")).toBeTruthy();
  });

  it("hides the tap-to-ready toggle when the order is not kitchen-active", () => {
    expect(mountItem({ readyToggleable: false }).find('button[aria-pressed]').exists()).toBe(false);
  });

  it("shows the comp button when allowed and emits comp; disabled while comping", async () => {
    const w = mountItem({ canComp: true });
    const btn = w.findAll("button").find((b) => b.attributes("aria-label") === "waiterPage.compItem");
    expect(btn).toBeTruthy();
    await btn.trigger("click");
    expect(w.emitted("comp")).toBeTruthy();
    expect(mountItem({ canComp: true, comping: true }).findAll("button")
      .find((b) => b.attributes("aria-label") === "waiterPage.compItem").attributes("disabled")).toBeDefined();
  });

  it("hides the comp button when comping is not allowed", () => {
    expect(mountItem({ canComp: false }).findAll("button").some((b) => b.attributes("aria-label") === "waiterPage.compItem")).toBe(false);
  });

  it("shows the void button when allowed and emits void; disabled while voiding", async () => {
    const w = mountItem({ canVoid: true });
    const btn = w.findAll("button").find((b) => b.attributes("aria-label") === "waiterPage.voidItem");
    await btn.trigger("click");
    expect(w.emitted("void")).toBeTruthy();
    expect(mountItem({ canVoid: true, voiding: true }).findAll("button")
      .find((b) => b.attributes("aria-label") === "waiterPage.voidItem").attributes("disabled")).toBeDefined();
  });

  it("hides comp/void affordances when the waiter cannot manage orders", () => {
    const w = mountItem({ canManage: false });
    expect(w.findAll("button").length).toBe(0);
  });
});
