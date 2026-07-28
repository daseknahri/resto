/**
 * Unit tests for WaiterSettleSheet — the inner body of WaiterPage's settle sheet
 * (cash / wallet / split-by-seat), a FRAGMENT child that owns NO payment logic
 * (RISK FE-2). The parent keeps the modal shell + focus trap + every settle
 * handler; here we verify the form models, the seat-split branch, the split
 * accordion, and that each action fires the right emit with the right payload.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));

import WaiterSettleSheet from "../WaiterSettleSheet.vue";

const order = {
  id: 7,
  table_label: "T1",
  order_number: 5,
  currency: "MAD",
  fulfillment_type: "table",
  items: [{ id: 1, qty: 2, dish_name: "Pizza", subtotal: 20 }],
};

const baseProps = {
  order,
  seatGroups: [],
  seatGroupsLoading: false,
  seatGroupsError: "",
  cashChange: null,
  settleOutstanding: () => 50,
  fmtOrderPrice: (a, c) => `${a} ${c}`,
  seatGroupLabel: (s) => `Seat ${s.seat}`,
  splitBySeatMode: false,
  cashReceived: "",
  splitSectionOpen: false,
  splitAmount: "",
};

const mountIt = (props = {}) => mount(WaiterSettleSheet, { props: { ...baseProps, ...props } });
const byText = (w, text) => w.findAll("button").filter((b) => b.text().includes(text));

describe("WaiterSettleSheet", () => {
  it("renders the identity line, outstanding and item breakdown", () => {
    const w = mountIt();
    expect(w.text()).toContain("T1");
    expect(w.text()).toContain("50 MAD"); // settleOutstanding -> fmtOrderPrice
    expect(w.text()).toContain("Pizza");
    expect(w.text()).toContain("20 MAD");
  });

  it("shows the standard cash/wallet CTAs when not in seat-split mode", () => {
    const w = mountIt({ splitBySeatMode: false });
    expect(byText(w, "waiterPage.cashFull").length).toBe(1);
    expect(byText(w, "waiterPage.payWalletMethod").length).toBe(1);
    expect(w.find("#waiter-cash-received").exists()).toBe(true);
  });

  it("emits update:cashReceived as the cash input is typed", async () => {
    const w = mountIt();
    await w.find("#waiter-cash-received").setValue("60");
    // type="number" v-model coerces to a Number (unchanged from the original markup).
    expect(w.emitted("update:cashReceived")[0]).toEqual([60]);
  });

  it("shows the change line only when cashChange is set", () => {
    expect(mountIt({ cashChange: null }).text()).not.toContain("waiterPage.cashChange");
    expect(mountIt({ cashChange: "10.00" }).text()).toContain("waiterPage.cashChange");
  });

  it("emits payCash / payWallet from the primary CTAs", async () => {
    const w = mountIt();
    await byText(w, "waiterPage.cashFull")[0].trigger("click");
    await byText(w, "waiterPage.payWalletMethod")[0].trigger("click");
    expect(w.emitted("payCash")).toBeTruthy();
    expect(w.emitted("payWallet")).toBeTruthy();
  });

  it("toggles seat-split mode and requests a seat-group load when turning it on", async () => {
    const w = mountIt({ splitBySeatMode: false });
    await byText(w, "waiterPage.splitBySeat")[0].trigger("click");
    expect(w.emitted("update:splitBySeatMode")[0]).toEqual([true]);
    expect(w.emitted("loadSeatGroups")).toBeTruthy();
  });

  it("hides the seat-split toggle for non-table orders", () => {
    const w = mountIt({ order: { ...order, fulfillment_type: "delivery" } });
    expect(byText(w, "waiterPage.splitBySeat").length).toBe(0);
  });

  it("renders seat rows and emits per-seat pay actions with the seat payload", async () => {
    const seat = { seat: 2, subtotal: 25, items: [{ id: 1 }] };
    const w = mountIt({ splitBySeatMode: true, seatGroups: [seat] });
    expect(w.text()).toContain("Seat 2");
    await byText(w, "waiterPage.payCash")[0].trigger("click");
    await byText(w, "waiterPage.payWalletForSeat")[0].trigger("click");
    expect(w.emitted("payCashForSeat")[0]).toEqual([seat]);
    expect(w.emitted("payWalletForSeat")[0]).toEqual([seat]);
  });

  it("shows the seat-split loading and error states", () => {
    expect(mountIt({ splitBySeatMode: true, seatGroupsLoading: true }).find(".ui-skeleton").exists()).toBe(true);
    expect(mountIt({ splitBySeatMode: true, seatGroupsError: "boom" }).text()).toContain("boom");
  });

  it("quick-split ÷n sets splitAmount to the divided outstanding", async () => {
    const w = mountIt({ splitSectionOpen: true });
    await byText(w, "÷2")[0].trigger("click");
    expect(w.emitted("update:splitAmount")[0]).toEqual(["25.00"]); // 50 / 2
  });

  it("emits close from the cancel button", async () => {
    const w = mountIt();
    await byText(w, "common.cancel")[0].trigger("click");
    expect(w.emitted("close")).toBeTruthy();
  });
});
