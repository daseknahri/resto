/**
 * Unit tests for WaiterStatusTabBar — the status-tab bar + action toolbar
 * extracted from WaiterPage.vue (RISK FE-2). activeTab / soundOn / floorView
 * round-trip via v-model; tabs/currentShift/etc. are props; selectShift / clock /
 * charge / newOrder are emits. The parent keeps openShiftSummary, doClock,
 * openCharge and the new-order clock-in guard.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import WaiterStatusTabBar from "../WaiterStatusTabBar.vue";

const tabs = [
  { key: "needs_action", label: "Needs action", count: 2 },
  { key: "all", label: "All", count: 0 },
];

const mountBar = (props = {}) =>
  mount(WaiterStatusTabBar, {
    props: {
      activeTab: "needs_action",
      soundOn: true,
      floorView: false,
      tabs,
      canManage: true,
      currentShift: null,
      clockBusy: false,
      shiftElapsed: "",
      formatDateTime: (v) => `dt(${v})`,
      ...props,
    },
  });

describe("WaiterStatusTabBar", () => {
  it("renders the tabs with their counts and marks the active one", () => {
    const w = mountBar({ activeTab: "needs_action" });
    const t0 = w.find("#waiter-tab-needs_action");
    expect(t0.text()).toContain("Needs action");
    expect(t0.text()).toContain("2"); // count badge
    expect(t0.attributes("aria-selected")).toBe("true");
    expect(w.find("#waiter-tab-all").attributes("aria-selected")).toBe("false");
  });

  it("selects a regular tab via v-model:activeTab", async () => {
    const w = mountBar({ activeTab: "needs_action" });
    await w.find("#waiter-tab-all").trigger("click");
    expect(w.emitted("update:activeTab")[0]).toEqual(["all"]);
  });

  it("selects the recent tab via v-model", async () => {
    const w = mountBar();
    await w.find("#waiter-tab-recent").trigger("click");
    expect(w.emitted("update:activeTab")[0]).toEqual(["recent"]);
  });

  it("emits selectShift (not a direct set) for the shift tab", async () => {
    const w = mountBar();
    await w.find("#waiter-tab-shift").trigger("click");
    expect(w.emitted("selectShift")).toBeTruthy();
    expect(w.emitted("update:activeTab")).toBeFalsy();
  });

  it("toggles the sound via v-model:soundOn", async () => {
    const w = mountBar({ soundOn: true });
    const btn = w.findAll("button").find((b) => b.attributes("aria-label") === "ownerOrders.muteAlerts");
    await btn.trigger("click");
    expect(w.emitted("update:soundOn")[0]).toEqual([false]);
  });

  it("shows clock-in when no shift and emits clock('in')", async () => {
    const w = mountBar({ currentShift: null });
    const btn = w.findAll("button").find((b) => b.text().includes("waiterPage.clockIn"));
    await btn.trigger("click");
    expect(w.emitted("clock")[0]).toEqual(["in"]);
  });

  it("shows clock-out (with elapsed) when in a shift and emits clock('out')", async () => {
    const w = mountBar({ currentShift: { clock_in: "09:00" }, shiftElapsed: "2h" });
    const btn = w.findAll("button").find((b) => b.text().includes("waiterPage.clockOut"));
    expect(btn.text()).toContain("2h");
    await btn.trigger("click");
    expect(w.emitted("clock")[0]).toEqual(["out"]);
  });

  it("emits charge and newOrder from their buttons", async () => {
    const w = mountBar();
    await w.findAll("button").find((b) => b.text().includes("waiterPage.chargeWalletBtn")).trigger("click");
    await w.findAll("button").find((b) => b.text().includes("waiterPage.newOrderBtn")).trigger("click");
    expect(w.emitted("charge")).toBeTruthy();
    expect(w.emitted("newOrder")).toBeTruthy();
  });

  it("toggles the floor view via v-model and hides it on the shift tab", async () => {
    const w = mountBar({ activeTab: "needs_action", floorView: false });
    const toggle = w.findAll("button").find((b) => b.attributes("aria-pressed") !== undefined);
    await toggle.trigger("click");
    expect(w.emitted("update:floorView")[0]).toEqual([true]);
    // hidden on shift / recent tabs
    expect(mountBar({ activeTab: "shift" }).findAll("button").some((b) => b.attributes("aria-pressed") !== undefined)).toBe(false);
  });

  it("hides the action buttons when the waiter cannot manage orders", () => {
    const w = mountBar({ canManage: false });
    expect(w.findAll("button").some((b) => b.text().includes("waiterPage.newOrderBtn"))).toBe(false);
    expect(w.findAll("button").some((b) => b.text().includes("waiterPage.clockIn"))).toBe(false);
  });
});
