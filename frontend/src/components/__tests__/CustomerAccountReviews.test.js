/**
 * Unit tests for CustomerAccountReviews — the reviews tab of
 * CustomerAccount.vue, extracted into a standalone presentational component
 * (RISK FE-2). Fetch/state (orders, drafts, hover, in-flight submissions)
 * stays owned by the parent; this component only renders whatever it's
 * given and asks the parent to apply mutations via the `hover`,
 * `draft-score`, `draft-comment` and `submit` emits.
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

import CustomerAccountReviews from "../CustomerAccountReviews.vue";

const RouterLinkStub = {
  name: "RouterLink",
  props: ["to"],
  template: '<a class="rl"><slot /></a>',
};

const AppIconStub = { template: "<i />" };

const pendingOrder = (overrides = {}) => ({
  order_number: "1001",
  created_at: "2026-07-01T12:00:00Z",
  total: 42.5,
  has_rating: false,
  ...overrides,
});

const submittedOrder = (overrides = {}) => ({
  order_number: "1002",
  created_at: "2026-06-01T12:00:00Z",
  has_rating: true,
  rating_score: 4,
  rating: { comment: "Great food" },
  ...overrides,
});

const mountComp = (props = {}) =>
  mount(CustomerAccountReviews, {
    props: {
      loading: false,
      completedOrders: [],
      pendingReviews: [],
      submittedReviews: [],
      reviewsAvgScore: 0,
      reviewHover: {},
      reviewDrafts: {},
      submittingReview: new Set(),
      reviewScoreLabels: ["", "Poor", "Fair", "Good", "Great", "Excellent!"],
      ...props,
    },
    global: { stubs: { RouterLink: RouterLinkStub, AppIcon: AppIconStub } },
  });

describe("CustomerAccountReviews", () => {
  it("renders the loading skeleton", () => {
    const w = mountComp({ loading: true });
    expect(w.findAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders the empty state when there are no completed orders", () => {
    const w = mountComp();
    expect(w.text()).toContain("customerAccount.reviewsEmpty");
    expect(w.text()).toContain("customerAccount.reviewsEmptyHint");
  });

  it("renders a pending review with its order number, date and price", () => {
    const order = pendingOrder();
    const w = mountComp({
      completedOrders: [order],
      pendingReviews: [order],
    });
    expect(w.text()).toContain("#1001");
    expect(w.text()).toContain("$42.5");
  });

  it("emits draft-score when a star is clicked, and hover on mouseenter/mouseleave", async () => {
    const order = pendingOrder();
    const w = mountComp({
      completedOrders: [order],
      pendingReviews: [order],
    });
    const stars = w.findAll("button.select-none");
    expect(stars.length).toBe(5);

    await stars[2].trigger("mouseenter");
    expect(w.emitted("hover")[0]).toEqual(["1001", 3]);

    await stars[2].trigger("mouseleave");
    expect(w.emitted("hover")[1]).toEqual(["1001", 0]);

    await stars[3].trigger("click");
    expect(w.emitted("draft-score")[0]).toEqual(["1001", 4]);
  });

  it("shows the comment box only once a draft score is set, and emits draft-comment on input", async () => {
    const order = pendingOrder();
    const w = mountComp({
      completedOrders: [order],
      pendingReviews: [order],
      reviewDrafts: {},
    });
    expect(w.find("textarea").exists()).toBe(false);

    await w.setProps({ reviewDrafts: { 1001: { score: 5, comment: "" } } });
    const textarea = w.find("textarea");
    expect(textarea.exists()).toBe(true);

    await textarea.setValue("Loved it");
    expect(w.emitted("draft-comment")[0]).toEqual(["1001", "Loved it"]);
  });

  it("disables the submit button until a score is drafted, and emits submit when clicked", async () => {
    const order = pendingOrder();
    const w = mountComp({
      completedOrders: [order],
      pendingReviews: [order],
      reviewDrafts: { 1001: { score: 5, comment: "" } },
    });
    const submitBtn = w.find("button.ui-btn-primary");
    expect(submitBtn.attributes("disabled")).toBeUndefined();

    await submitBtn.trigger("click");
    expect(w.emitted("submit")[0]).toEqual([order]);
  });

  it("disables the submit button while submittingReview has the order", () => {
    const order = pendingOrder();
    const w = mountComp({
      completedOrders: [order],
      pendingReviews: [order],
      reviewDrafts: { 1001: { score: 5, comment: "" } },
      submittingReview: new Set(["1001"]),
    });
    const submitBtn = w.find("button.ui-btn-primary");
    expect(submitBtn.attributes("disabled")).toBeDefined();
  });

  it("renders the average score card and submitted reviews with their comment", () => {
    const order = submittedOrder();
    const w = mountComp({
      completedOrders: [order],
      submittedReviews: [order],
      reviewsAvgScore: 4,
    });
    expect(w.text()).toContain("#1002");
    expect(w.text()).toContain("Great food");
    expect(w.text()).toContain("4.0");
  });
});
