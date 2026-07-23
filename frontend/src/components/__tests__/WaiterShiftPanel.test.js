/**
 * Unit tests for WaiterShiftPanel — the shift-summary + change-password tab panel
 * extracted from WaiterPage.vue (RISK FE-2). The waiter store, the summary fetch
 * and the password submit stay in the parent; the two form values round-trip via
 * v-model:since / v-model:pw-form, and the panel emits refresh / submitPassword.
 */
import { describe, it, expect, vi } from "vitest";
import { reactive } from "vue";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import WaiterShiftPanel from "../WaiterShiftPanel.vue";

const waiterStore = (overrides = {}) => ({
  shiftSummary: null,
  shiftSummaryLoading: false,
  shiftSummaryError: "",
  ...overrides,
});

const pwForm = (overrides = {}) => reactive({ current: "", next: "", loading: false, error: "", ...overrides });

const mountPanel = (props = {}) =>
  mount(WaiterShiftPanel, {
    props: {
      since: "2026-01-01T09:00",
      pwForm: pwForm(),
      waiter: waiterStore(),
      showShiftRevenue: true,
      shiftRevenue: "$420",
      ...props,
    },
  });

describe("WaiterShiftPanel", () => {
  it("binds the shift-since input and round-trips it via v-model:since", async () => {
    const w = mountPanel();
    const input = w.find("#shift-since-input");
    expect(input.element.value).toBe("2026-01-01T09:00");
    await input.setValue("2026-02-02T10:00");
    expect(w.emitted("update:since")[0]).toEqual(["2026-02-02T10:00"]);
  });

  it("emits refresh from the refresh button and disables it while loading", async () => {
    const w = mountPanel();
    const btn = w.findAll("button").find((b) => b.text().includes("waiterPage.shiftRefresh"));
    await btn.trigger("click");
    expect(w.emitted("refresh")).toBeTruthy();
    const loadingBtn = mountPanel({ waiter: waiterStore({ shiftSummaryLoading: true }) })
      .findAll("button").find((b) => b.text().includes("waiterPage.shiftLoading"));
    expect(loadingBtn.attributes("disabled")).toBeDefined();
  });

  it("shows the shift-summary error when present", () => {
    const w = mountPanel({ waiter: waiterStore({ shiftSummaryError: "boom" }) });
    expect(w.find('[role="alert"]').text()).toContain("boom");
  });

  it("renders the stats grid with revenue when show_revenue is on", () => {
    const w = mountPanel({
      waiter: waiterStore({ shiftSummary: { orders_handled: 12, average_prep_time_minutes: 8, period_hours: 5 } }),
      showShiftRevenue: true,
      shiftRevenue: "$420",
    });
    expect(w.text()).toContain("12"); // orders handled
    expect(w.text()).toContain("$420"); // revenue tile
    expect(w.text()).toContain("waiterPage.shiftAvgPrep");
    expect(w.text()).toContain('waiterPage.shiftPeriod:{"hours":5}');
  });

  it("hides the revenue tile when showShiftRevenue is false", () => {
    const w = mountPanel({
      waiter: waiterStore({ shiftSummary: { orders_handled: 3, average_prep_time_minutes: null, period_hours: 2 } }),
      showShiftRevenue: false,
      shiftRevenue: "$0",
    });
    expect(w.text()).not.toContain("$0");
    expect(w.text()).toContain("—"); // avg prep dash when null
  });

  it("shows the skeleton while loading and the empty hint otherwise", () => {
    expect(mountPanel({ waiter: waiterStore({ shiftSummaryLoading: true }) }).find(".ui-skeleton").exists()).toBe(true);
    expect(mountPanel({ waiter: waiterStore() }).text()).toContain("waiterPage.shiftHint");
  });

  it("binds the password fields and emits submitPassword on submit", async () => {
    const model = pwForm();
    const w = mountPanel({ pwForm: model });
    await w.find("#waiter-current-password").setValue("old");
    await w.find("#waiter-new-password").setValue("new");
    expect(model.current).toBe("old");
    expect(model.next).toBe("new");
    await w.find("form").trigger("submit");
    expect(w.emitted("submitPassword")).toBeTruthy();
  });

  it("disables the password submit until both fields are filled", () => {
    const empty = mountPanel({ pwForm: pwForm({ current: "", next: "" }) });
    expect(empty.find('button[type="submit"]').attributes("disabled")).toBeDefined();
    const filled = mountPanel({ pwForm: pwForm({ current: "a", next: "b" }) });
    expect(filled.find('button[type="submit"]').attributes("disabled")).toBeUndefined();
  });

  it("shows the password error when present", () => {
    const w = mountPanel({ pwForm: pwForm({ error: "wrong password" }) });
    expect(w.text()).toContain("wrong password");
  });
});
