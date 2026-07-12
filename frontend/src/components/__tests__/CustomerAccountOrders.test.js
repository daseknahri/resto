/**
 * Unit tests for CustomerAccountOrders — the orders tab of
 * CustomerAccount.vue, extracted into a standalone presentational component
 * (RISK FE-2). CAUTION: this tab renders order history + live order STATUS —
 * every fetch, retry, pagination, cancel and reorder call stays owned by the
 * parent (CustomerAccount.vue); this component only renders whatever it's
 * given and asks the parent to run the underlying action via emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
    formatPrice: (n) => `$${n}`,
    currentLocale: { value: "en" },
  }),
}));

import CustomerAccountOrders from "../CustomerAccountOrders.vue";

const RouterLinkStub = {
  name: "RouterLink",
  props: ["to"],
  template: '<a class="rl"><slot /></a>',
};

const AppIconStub = { props: ["name"], template: "<i />" };

const ACTIVE_STATUSES = new Set(["pending", "confirmed", "preparing", "ready", "out_for_delivery"]);

const tenantOrder = (overrides = {}) => ({
  order_number: "1001",
  status: "pending",
  created_at: "2026-07-01T12:00:00Z",
  total: 42.5,
  fulfillment_type: "delivery",
  can_cancel: false,
  has_rating: false,
  items: [],
  ...overrides,
});

const marketplaceOrder = (overrides = {}) => ({
  order_number: "2001",
  restaurant_name: "Le Bistro",
  restaurant_slug: "le-bistro",
  status: "pending",
  created_at: "2026-07-01T12:00:00Z",
  total: 30,
  can_cancel: false,
  items_snapshot: [],
  ...overrides,
});

const mountComp = (props = {}) =>
  mount(CustomerAccountOrders, {
    props: {
      verticalFilterOptions: [],
      selectedVertical: "",
      orderSearch: "",
      marketplaceOrders: [],
      filteredMarketplaceOrders: [],
      loadingMarketplaceOrders: false,
      loadingMoreMarketplaceOrders: false,
      marketplaceOrdersHasMore: false,
      isAuthenticated: true,
      tenantName: "",
      apiOrders: [],
      loadingOrders: false,
      ordersError: false,
      ordersHasMore: false,
      loadingMoreOrders: false,
      recentOrders: [],
      activeStatuses: ACTIVE_STATUSES,
      expandedOrders: new Set(),
      cancellingOrderNumber: null,
      verticalSvcLabels: {},
      ...props,
    },
    global: { stubs: { RouterLink: RouterLinkStub, AppIcon: AppIconStub } },
  });

describe("CustomerAccountOrders", () => {
  it("renders the loading skeleton", () => {
    const w = mountComp({ loadingOrders: true });
    expect(w.findAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders the error state and emits retry when the retry button is clicked", async () => {
    const w = mountComp({ ordersError: true });
    expect(w.text()).toContain("customerAccount.fetchError");
    const retryBtn = w.findAll("button").find((b) => b.text() === "common.retry");
    await retryBtn.trigger("click");
    expect(w.emitted("retry")).toBeTruthy();
  });

  it("renders the empty state when there are no orders at all", () => {
    const w = mountComp();
    expect(w.text()).toContain("customerAccount.ordersEmpty");
    expect(w.text()).toContain("customerAccount.ordersEmptyCta");
  });

  it("falls back to the local recentOrders list when apiOrders is empty", () => {
    const w = mountComp({ recentOrders: [{ order_number: "555", total: 10 }] });
    expect(w.text()).not.toContain("customerAccount.ordersEmpty");
    expect(w.text()).toContain("customerAccount.orderNumber");
    expect(w.text()).toContain("$10");
  });

  it("renders the tenant order list with order number, status and price", () => {
    const o = tenantOrder();
    const w = mountComp({ apiOrders: [o] });
    expect(w.text()).toContain("$42.5");
    expect(w.text()).toContain("orderStatus.statusPending");
  });

  it("emits cancel-order with the order when its cancel button is clicked", async () => {
    const o = tenantOrder({ can_cancel: true });
    const w = mountComp({ apiOrders: [o] });
    const cancelBtn = w.findAll("button").find((b) => b.text() === "customerAccount.cancelOrder");
    await cancelBtn.trigger("click");
    expect(w.emitted("cancel-order")[0]).toEqual([o]);
  });

  it("emits toggle-order with the order_number when the show-items button is clicked", async () => {
    const o = tenantOrder({ items: [{ qty: 1, dish_name: "Pizza", subtotal: 42.5 }] });
    const w = mountComp({ apiOrders: [o] });
    const toggleBtn = w.findAll("button").find((b) => b.text() === "customerAccount.orderShowItems");
    await toggleBtn.trigger("click");
    expect(w.emitted("toggle-order")[0]).toEqual(["1001"]);
  });

  it("renders expanded line items (driven by the expandedOrders prop) and emits reorder", async () => {
    const o = tenantOrder({ items: [{ qty: 2, dish_name: "Pizza", subtotal: 20 }] });
    const w = mountComp({ apiOrders: [o], expandedOrders: new Set(["1001"]) });
    expect(w.text()).toContain("Pizza");
    const reorderBtn = w.findAll("button").find((b) => b.text() === "customerAccount.reorder");
    await reorderBtn.trigger("click");
    expect(w.emitted("reorder")[0]).toEqual([o]);
  });

  it("emits view-receipt with the order when the view-receipt button is clicked", async () => {
    const o = tenantOrder({ status: "completed", has_rating: true, items: [{ qty: 1, dish_name: "Pizza", subtotal: 42.5 }] });
    const w = mountComp({ apiOrders: [o] });
    const receiptBtn = w.findAll("button").find((b) => b.text() === "customerAccount.viewReceipt");
    await receiptBtn.trigger("click");
    expect(w.emitted("view-receipt")[0]).toEqual([o]);
  });

  it("emits switch-tab('reviews') when the rate nudge is clicked for a completed, unrated order", async () => {
    const o = tenantOrder({ status: "completed", has_rating: false });
    const w = mountComp({ apiOrders: [o] });
    const nudgeBtn = w.findAll("button").find((b) => b.text() === "customerAccount.reviewsRateNudge");
    await nudgeBtn.trigger("click");
    expect(w.emitted("switch-tab")[0]).toEqual(["reviews"]);
  });

  it("emits load-more-orders when the tenant load-more button is clicked", async () => {
    const w = mountComp({ apiOrders: [tenantOrder()], ordersHasMore: true });
    const btn = w.findAll("button").find((b) => b.text().includes("customerAccount.loadMoreOrders"));
    await btn.trigger("click");
    expect(w.emitted("load-more-orders")).toBeTruthy();
  });

  it("renders the marketplace order list and emits reorder-marketplace / cancel-marketplace-order", async () => {
    const o = marketplaceOrder({ can_cancel: true, items_snapshot: [{ dish_name: "Burger" }] });
    const w = mountComp({ marketplaceOrders: [o], filteredMarketplaceOrders: [o] });
    expect(w.text()).toContain("Le Bistro");

    const reorderBtn = w.findAll("button").find((b) => b.text() === "customerAccount.reorder");
    await reorderBtn.trigger("click");
    expect(w.emitted("reorder-marketplace")[0]).toEqual([o]);

    const cancelBtn = w.findAll("button").find((b) => b.text() === "customerAccount.cancelOrder");
    await cancelBtn.trigger("click");
    expect(w.emitted("cancel-marketplace-order")[0]).toEqual([o]);
  });

  it("shows the marketplace no-results message when the search filter matches nothing", () => {
    const o = marketplaceOrder();
    const w = mountComp({ marketplaceOrders: [o], filteredMarketplaceOrders: [], orderSearch: "zzz" });
    expect(w.text()).toContain("customerAccount.orderSearchNoResults");
  });

  it("emits load-more-marketplace-orders when its load-more button is clicked", async () => {
    const o = marketplaceOrder();
    const w = mountComp({ marketplaceOrders: [o], filteredMarketplaceOrders: [o], marketplaceOrdersHasMore: true });
    const btn = w.findAll("button").find((b) => b.text().includes("customerAccount.loadMoreOrders"));
    await btn.trigger("click");
    expect(w.emitted("load-more-marketplace-orders")).toBeTruthy();
  });

  it("emits select-vertical with the option id when a filter chip is clicked", async () => {
    const w = mountComp({
      verticalFilterOptions: [{ id: "", label: "All" }, { id: "food", label: "Food" }],
    });
    const chip = w.findAll("button").find((b) => b.text() === "Food");
    await chip.trigger("click");
    expect(w.emitted("select-vertical")[0]).toEqual(["food"]);
  });

  it("does not render the vertical filter chips when there is only one option", () => {
    const w = mountComp({ verticalFilterOptions: [{ id: "", label: "All" }] });
    expect(w.findAll("button").find((b) => b.text() === "All")).toBeUndefined();
  });

  it("emits update-order-search when typing in the search input", async () => {
    const w = mountComp();
    const input = w.find('input[type="search"]');
    await input.setValue("burger");
    expect(w.emitted("update-order-search")[0]).toEqual(["burger"]);
  });
});
