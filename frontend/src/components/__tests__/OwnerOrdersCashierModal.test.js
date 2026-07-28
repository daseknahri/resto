/**
 * Unit tests for OwnerOrdersCashierModal — the cashier-mode big-total modal of
 * OwnerOrders.vue, extracted into a standalone presentational component
 * (RISK FE-2). The `cashierOrder` state, the settle API call and the
 * `settlingOrderId` guard stay owned by the parent; this component only renders
 * the big-total screen it's given and asks the parent to close/settle via emits
 * (`close`, `settle`).
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import OwnerOrdersCashierModal from "../OwnerOrdersCashierModal.vue";

const formatCurrency = (amount, currency = "USD") => `${currency} ${amount}`;

const order = (overrides = {}) => ({
  id: 42,
  order_number: "1042",
  total: "125.00",
  currency: "MAD",
  table_label: null,
  status: "pending",
  ...overrides,
});

// Stub teleport so the modal renders inline (queryable in the wrapper), same
// pattern used by OwnerOrdersFilterSheet.test.js for teleport-based sheets.
const mountModal = (props = {}) =>
  mount(OwnerOrdersCashierModal, {
    props: {
      order: order(),
      settling: false,
      formatCurrency,
      ...props,
    },
    global: { stubs: { teleport: true } },
  });

describe("OwnerOrdersCashierModal", () => {
  it("renders nothing when order is null", () => {
    const w = mountModal({ order: null });
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("renders the dialog with the formatted total and order number when open", () => {
    const w = mountModal();
    expect(w.find('[role="dialog"]').exists()).toBe(true);
    expect(w.text()).toContain("ownerOrders.cashierModalTitle");
    expect(w.text()).toContain("MAD 125.00");
    expect(w.text()).toContain("#1042");
  });

  it("shows the table label only when the order has one", () => {
    const wNoTable = mountModal();
    expect(wNoTable.text()).not.toContain("ownerOrders.fulfillmentTable");

    const wTable = mountModal({ order: order({ table_label: "T3" }) });
    expect(wTable.text()).toContain('ownerOrders.fulfillmentTable:{"table":"T3"}');
  });

  it("labels the settle button 'markPaid' for a non-ready order", () => {
    const w = mountModal({ order: order({ status: "pending" }) });
    expect(w.text()).toContain("ownerOrders.markPaid");
    expect(w.text()).not.toContain("ownerOrders.settleAndClose");
  });

  it("labels the settle button 'settleAndClose' for a ready order", () => {
    const w = mountModal({ order: order({ status: "ready" }) });
    expect(w.text()).toContain("ownerOrders.settleAndClose");
    expect(w.text()).not.toContain("ownerOrders.markPaid");
  });

  it("emits close from the cancel button", async () => {
    const w = mountModal();
    const cancelBtn = w.findAll("button").find((b) => b.text() === "common.cancel");
    await cancelBtn.trigger("click");
    expect(w.emitted("close")).toBeTruthy();
  });

  it("emits close when the backdrop is clicked", async () => {
    const w = mountModal();
    const backdrop = w.findAll("div").find((d) => d.classes().includes("backdrop-blur-sm"));
    expect(backdrop).toBeTruthy();
    await backdrop.trigger("click");
    expect(w.emitted("close")).toBeTruthy();
  });

  it("emits settle with the order from the settle button", async () => {
    const o = order();
    const w = mountModal({ order: o });
    const settleBtn = w.findAll("button").find((b) => b.text().includes("ownerOrders.markPaid"));
    await settleBtn.trigger("click");
    expect(w.emitted("settle")).toBeTruthy();
    expect(w.emitted("settle")[0]).toEqual([o]);
  });

  it("disables the settle button and shows a spinner while settling", () => {
    const w = mountModal({ settling: true });
    const settleBtn = w.findAll("button").find((b) => b.attributes("disabled") !== undefined);
    expect(settleBtn).toBeTruthy();
    expect(settleBtn.find(".animate-spin").exists()).toBe(true);
  });

  it("does not disable the settle button when not settling", () => {
    const w = mountModal({ settling: false });
    const settleBtn = w.findAll("button").find((b) => b.text().includes("ownerOrders.markPaid"));
    expect(settleBtn.attributes("disabled")).toBeUndefined();
    expect(settleBtn.find(".animate-spin").exists()).toBe(false);
  });
});
