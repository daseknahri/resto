/**
 * Unit tests for DriverPageDeliveryHistory — the "recent deliveries" history
 * accordion of DriverPage.vue, extracted into a standalone presentational
 * component (RISK FE-2). Fetch/pagination state stays in the parent; this
 * component only renders whatever page it's given and asks the parent to
 * toggle / load more via emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) => k,
  }),
}));

import DriverPageDeliveryHistory from "../DriverPageDeliveryHistory.vue";

const statusLabel = (s) => `label:${s}`;
const fmtDate = (iso) => `date:${iso}`;
const fmtMoney = (v) => `$${v}`;

const delivery = (overrides = {}) => ({
  id: 1,
  restaurant_name: "Chez Karim",
  order_number: "1001",
  status: "delivered",
  delivered_at: "2026-07-01T12:00:00Z",
  failed_at: null,
  created_at: "2026-07-01T11:30:00Z",
  driver_payout: "18.50",
  ...overrides,
});

const mountComp = (props = {}) =>
  mount(DriverPageDeliveryHistory, {
    props: {
      show: false,
      loading: false,
      items: [],
      hasMore: false,
      statusLabel,
      fmtDate,
      fmtMoney,
      ...props,
    },
  });

describe("DriverPageDeliveryHistory", () => {
  it("renders the header but keeps the panel collapsed when show is false", () => {
    const w = mountComp({ show: false, items: [delivery()] });
    expect(w.text()).toContain("driver.historyTitle");
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
    expect(w.text()).toContain("driver.historyEmpty");
  });

  it("renders delivery rows with formatted status, date and payout", () => {
    const w = mountComp({ show: true, items: [delivery()] });
    expect(w.text()).toContain("Chez Karim");
    expect(w.text()).toContain("label:delivered");
    expect(w.text()).toContain("date:2026-07-01T12:00:00Z");
    expect(w.text()).toContain("$18.50");
  });

  it("falls back to the order number when there is no restaurant name", () => {
    const w = mountComp({ show: true, items: [delivery({ restaurant_name: "" })] });
    expect(w.text()).toContain("#1001");
  });

  it("does not render a load-more button when hasMore is false", () => {
    const w = mountComp({ show: true, items: [delivery()], hasMore: false });
    expect(w.text()).not.toContain("driver.historyLoadMore");
  });

  it("renders and emits load-more when hasMore is true and the button is clicked", async () => {
    const w = mountComp({ show: true, items: [delivery()], hasMore: true });
    const buttons = w.findAll("button");
    const loadMoreBtn = buttons.find((b) => b.text().includes("driver.historyLoadMore"));
    expect(loadMoreBtn).toBeTruthy();
    await loadMoreBtn.trigger("click");
    expect(w.emitted("load-more")).toBeTruthy();
  });

  it("shows the loading label on the load-more button while loading", () => {
    const w = mountComp({ show: true, items: [delivery()], hasMore: true, loading: true });
    const buttons = w.findAll("button");
    const loadMoreBtn = buttons.find((b) => b.attributes("disabled") !== undefined && b.text().includes("common.loading"));
    expect(loadMoreBtn).toBeTruthy();
  });
});
