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
    // B-09: the confirm field round-trips like current/next.
    await w.find("#waiter-confirm-password").setValue("new");
    expect(model.current).toBe("old");
    expect(model.next).toBe("new");
    expect(model.confirm).toBe("new");
    await w.find("form").trigger("submit");
    expect(w.emitted("submitPassword")).toBeTruthy();
  });

  // B-09 (DELIBERATE CHANGE): the submit now needs current + new + CONFIRM —
  // current + new alone no longer enables it.
  it("disables the password submit until current, new AND confirm are filled", () => {
    const empty = mountPanel({ pwForm: pwForm({ current: "", next: "" }) });
    expect(empty.find('button[type="submit"]').attributes("disabled")).toBeDefined();
    const noConfirm = mountPanel({ pwForm: pwForm({ current: "a", next: "b" }) });
    expect(noConfirm.find('button[type="submit"]').attributes("disabled")).toBeDefined();
    const filled = mountPanel({ pwForm: pwForm({ current: "a", next: "b", confirm: "c" }) });
    expect(filled.find('button[type="submit"]').attributes("disabled")).toBeUndefined();
  });

  it("shows the password error when present", () => {
    const w = mountPanel({ pwForm: pwForm({ error: "wrong password" }) });
    expect(w.text()).toContain("wrong password");
  });
});

// ── S3-B (B-08 shift-load error + B-09 confirm field) ───────────────────────
// Appended, not rewritten: the base describe above is untouched except for the
// two B-09 tests it deliberately changes (see notes there). Panel tests mount
// fresh per test with no shared state, so no extra isolation hook is needed.
describe("WaiterShiftPanel — S3-B", () => {
  // B-08: the shift-load error renders with a Retry button that emits retryShift.
  it("shows the shift-load error with Retry and emits retryShift", async () => {
    const w = mountPanel({ shiftLoadError: "waiterPage.shiftLoadError" });
    expect(w.find('[role="alert"]').text()).toContain("waiterPage.shiftLoadError");
    const btn = w.findAll("button").find((b) => b.text().includes("waiterPage.retry"));
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    expect(w.emitted("retryShift")).toBeTruthy();
  });

  // B-08: while a re-fetch is in flight the Retry button shows loading and is disabled.
  it("disables Retry while the shift is reloading", () => {
    const w = mountPanel({ shiftLoadError: "boom", shiftLoading: true });
    const btn = w.findAll("button").find((b) => b.text().includes("waiterPage.shiftLoading"));
    expect(btn.exists()).toBe(true);
    expect(btn.attributes("disabled")).toBeDefined();
    expect(w.findAll("button").find((b) => b.text().includes("waiterPage.retry"))).toBeUndefined();
  });

  // B-08: no shift-load error block when the shift state is known (empty string).
  it("shows no shift-load error block when shiftLoadError is empty", () => {
    const w = mountPanel({ shiftLoadError: "" });
    expect(w.find('[role="alert"]').exists()).toBe(false);
  });

  // B-09: the confirm field is labelled and binds via v-model.
  it("labels the confirm field and binds it", async () => {
    const model = pwForm();
    const w = mountPanel({ pwForm: model });
    expect(w.text()).toContain("staffPassword.confirmLabel");
    const input = w.find("#waiter-confirm-password");
    expect(input.exists()).toBe(true);
    expect(input.attributes("type")).toBe("password");
    expect(input.attributes("autocomplete")).toBe("new-password");
    await input.setValue("typed-twice");
    expect(model.confirm).toBe("typed-twice");
  });
});
