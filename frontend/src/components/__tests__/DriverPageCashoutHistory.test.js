/**
 * Unit tests for DriverPageCashoutHistory — the "cash-out history" accordion
 * of DriverPage.vue, extracted into a standalone presentational component
 * (RISK FE-2), mirroring the merged DriverPageDeliveryHistory.vue precedent.
 * Fetch/pagination state stays in the parent; this component only renders
 * whatever page it's given and asks the parent to toggle / load more via
 * emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) => k,
  }),
}));

import DriverPageCashoutHistory from "../DriverPageCashoutHistory.vue";

const fmtDate = (iso) => `date:${iso}`;
const fmtMoney = (v) => `$${v}`;

const cashout = (overrides = {}) => ({
  id: 1,
  settled_by: "Chez Karim",
  status: "paid",
  resolved_at: "2026-07-01T12:00:00Z",
  created_at: "2026-07-01T11:30:00Z",
  amount: "42.00",
  ...overrides,
});

const mountComp = (props = {}) =>
  mount(DriverPageCashoutHistory, {
    props: {
      show: false,
      loading: false,
      items: [],
      hasMore: false,
      fmtDate,
      fmtMoney,
      ...props,
    },
  });

describe("DriverPageCashoutHistory", () => {
  it("renders the header but keeps the panel collapsed when show is false", () => {
    const w = mountComp({ show: false, items: [cashout()] });
    expect(w.text()).toContain("driver.cashOutHistoryTitle");
    expect(w.text()).not.toContain("Chez Karim");
    expect(w.find("button[aria-expanded]").attributes("aria-expanded")).toBe("false");
  });

  it("emits toggle when the header is clicked", async () => {
    const w = mountComp();
    await w.find("button[aria-expanded]").trigger("click");
    expect(w.emitted("toggle")).toBeTruthy();
  });

  it("renders the loading skeleton when expanded with no items yet", () => {
    const w = mountComp({ show: true, loading: true, items: [] });
    expect(w.findAll(".ui-skeleton").length).toBeGreaterThan(0);
  });

  it("renders the empty state when expanded with no items and not loading", () => {
    const w = mountComp({ show: true, loading: false, items: [] });
    expect(w.text()).toContain("driver.cashOutHistoryEmpty");
  });

  it("renders cash-out rows with settled-by, formatted date and amount", () => {
    const w = mountComp({ show: true, items: [cashout()] });
    expect(w.text()).toContain("Chez Karim");
    expect(w.text()).toContain("date:2026-07-01T12:00:00Z");
    expect(w.text()).toContain("$42.00");
    expect(w.text()).toContain("driver.cashOutStatus_paid");
  });

  it("falls back to the unsettled label when there is no settled_by", () => {
    const w = mountComp({ show: true, items: [cashout({ settled_by: "" })] });
    expect(w.text()).toContain("driver.cashOutHistoryUnsettled");
  });

  it("renders status-specific styling classes for cancelled and expired rows", () => {
    const cancelled = mountComp({ show: true, items: [cashout({ status: "cancelled" })] });
    expect(cancelled.text()).toContain("driver.cashOutStatus_cancelled");

    const expired = mountComp({ show: true, items: [cashout({ status: "expired" })] });
    expect(expired.text()).toContain("driver.cashOutStatus_expired");
  });

  it("does not render a load-more button when hasMore is false", () => {
    const w = mountComp({ show: true, items: [cashout()], hasMore: false });
    expect(w.text()).not.toContain("driver.historyLoadMore");
  });

  it("renders and emits load-more when hasMore is true and the button is clicked", async () => {
    const w = mountComp({ show: true, items: [cashout()], hasMore: true });
    const buttons = w.findAll("button");
    const loadMoreBtn = buttons.find((b) => b.text().includes("driver.historyLoadMore"));
    expect(loadMoreBtn).toBeTruthy();
    await loadMoreBtn.trigger("click");
    expect(w.emitted("load-more")).toBeTruthy();
  });

  it("shows the loading label on the load-more button while loading", () => {
    const w = mountComp({ show: true, items: [cashout()], hasMore: true, loading: true });
    const buttons = w.findAll("button");
    const loadMoreBtn = buttons.find((b) => b.attributes("disabled") !== undefined && b.text().includes("common.loading"));
    expect(loadMoreBtn).toBeTruthy();
  });
});
