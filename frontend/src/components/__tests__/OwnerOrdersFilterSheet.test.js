/**
 * Unit tests for OwnerOrdersFilterSheet — the fulfillment/payment/date
 * filter bottom-drawer of OwnerOrders.vue, extracted into a standalone
 * presentational component (RISK FE-2). All filter state and derived tab
 * lists stay owned by the parent; this component only renders what it's
 * given and asks the parent to apply mutations via emits
 * (`close`, `clear`, `set-date-filter`, `set-custom-date-from`,
 * `set-custom-date-to`, `set-fulfillment-type`, `set-payment-status`).
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import OwnerOrdersFilterSheet from "../OwnerOrdersFilterSheet.vue";

const dateTabs = [
  { value: "all", label: "All" },
  { value: "today", label: "Today" },
  { value: "yesterday", label: "Yesterday" },
  { value: "week", label: "Last 7 days" },
  { value: "custom", label: "Custom" },
];

const fulfillmentTabs = [
  { value: "", label: "All" },
  { value: "pickup", label: "Pickup" },
  { value: "delivery", label: "Delivery" },
];

const paymentStatusTabs = [
  { value: "", label: "All", count: 0 },
  { value: "unpaid", label: "Unpaid", count: 3 },
  { value: "paid", label: "Paid", count: 7 },
];

// Stub teleport so the drawer renders inline (queryable in the wrapper),
// same pattern used by BusyModeControl.test.js for teleport-based sheets.
const mountSheet = (props = {}) =>
  mount(OwnerOrdersFilterSheet, {
    props: {
      open: true,
      activeDateFilter: "all",
      customDateFrom: "",
      customDateTo: "",
      activeFulfillmentType: "",
      activePaymentStatus: "",
      activeFilterCount: 0,
      dateTabs,
      fulfillmentTabs,
      paymentStatusTabs,
      ...props,
    },
    global: { stubs: { teleport: true } },
  });

describe("OwnerOrdersFilterSheet", () => {
  it("renders nothing when closed", () => {
    const w = mountSheet({ open: false });
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("renders the dialog and all three filter groups when open", () => {
    const w = mountSheet();
    expect(w.find('[role="dialog"]').exists()).toBe(true);
    expect(w.text()).toContain("ownerOrders.filterSheetTitle");
    expect(w.text()).toContain("Today");
    expect(w.text()).toContain("Pickup");
    expect(w.text()).toContain("Unpaid");
  });

  it("hides the fulfillment-type group when fulfillmentTabs is empty (single type)", () => {
    const w = mountSheet({ fulfillmentTabs: [] });
    expect(w.text()).not.toContain("ownerOrders.fulfillmentFilter");
  });

  it("shows the clear-filters button only when activeFilterCount > 0", () => {
    const w0 = mountSheet({ activeFilterCount: 0 });
    expect(w0.text()).not.toContain("ownerOrders.clearFilters");

    const w1 = mountSheet({ activeFilterCount: 2 });
    expect(w1.text()).toContain("ownerOrders.clearFilters");
  });

  it("emits set-date-filter when a date tab is clicked", async () => {
    const w = mountSheet();
    const buttons = w.findAll("button");
    const todayBtn = buttons.find((b) => b.text() === "Today");
    await todayBtn.trigger("click");
    expect(w.emitted("set-date-filter")[0]).toEqual(["today"]);
  });

  it("shows custom date inputs only when activeDateFilter is 'custom', and emits on input", async () => {
    const w = mountSheet({ activeDateFilter: "all" });
    expect(w.find("#fs-date-from").exists()).toBe(false);

    const wCustom = mountSheet({ activeDateFilter: "custom", customDateFrom: "2026-07-01" });
    const fromInput = wCustom.find("#fs-date-from");
    expect(fromInput.exists()).toBe(true);
    expect(fromInput.element.value).toBe("2026-07-01");

    await fromInput.setValue("2026-07-05");
    expect(wCustom.emitted("set-custom-date-from")[0]).toEqual(["2026-07-05"]);

    const toInput = wCustom.find("#fs-date-to");
    await toInput.setValue("2026-07-10");
    expect(wCustom.emitted("set-custom-date-to")[0]).toEqual(["2026-07-10"]);
  });

  it("emits set-fulfillment-type and set-payment-status when their chips are clicked", async () => {
    const w = mountSheet();
    const buttons = w.findAll("button");

    const pickupBtn = buttons.find((b) => b.text() === "Pickup");
    await pickupBtn.trigger("click");
    expect(w.emitted("set-fulfillment-type")[0]).toEqual(["pickup"]);

    const paidBtn = buttons.find((b) => b.text().startsWith("Paid"));
    await paidBtn.trigger("click");
    expect(w.emitted("set-payment-status")[0]).toEqual(["paid"]);
  });

  it("emits clear and close from their respective buttons", async () => {
    const w = mountSheet({ activeFilterCount: 1 });
    const buttons = w.findAll("button");

    const clearBtn = buttons.find((b) => b.text() === "ownerOrders.clearFilters");
    await clearBtn.trigger("click");
    expect(w.emitted("clear")).toBeTruthy();

    const closeBtn = buttons.find((b) => b.text() === "common.close");
    await closeBtn.trigger("click");
    expect(w.emitted("close")).toBeTruthy();
  });

  it("emits close when the backdrop is clicked", async () => {
    const w = mountSheet();
    const backdrop = w.findAll("div").find((d) => d.classes().includes("backdrop-blur-sm"));
    expect(backdrop).toBeTruthy();
    await backdrop.trigger("click");
    expect(w.emitted("close")).toBeTruthy();
  });
});
