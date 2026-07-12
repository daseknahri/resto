/**
 * Unit tests for RidePageHistory — the past-rides history section of
 * RidePage.vue (the ride-booking flow), extracted into a standalone
 * presentational component (RISK FE-2). This component does no fetching and
 * no fare/map/booking logic; it only renders whatever history it's given and
 * asks the parent to rebook via the `rebook` emit.
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

import RidePageHistory from "../RidePageHistory.vue";

const ride = (overrides = {}) => ({
  id: 1,
  pickup_address: "12 Rue Atlas",
  dropoff_address: "45 Avenue Hassan II",
  created_at: "2026-07-01T12:00:00Z",
  fare: 32,
  status: "completed",
  rider_driver_rating: null,
  ...overrides,
});

const mountComp = (props = {}) =>
  mount(RidePageHistory, {
    props: {
      history: [],
      loading: false,
      isAuthenticated: false,
      ...props,
    },
  });

describe("RidePageHistory", () => {
  it("renders nothing when there is no history, not loading, and not authenticated", () => {
    const w = mountComp();
    expect(w.text()).toBe("");
  });

  it("renders the loading skeleton when loading with no history yet", () => {
    const w = mountComp({ loading: true });
    expect(w.findAll(".animate-pulse").length).toBe(3);
    expect(w.text()).toContain("ridePage.historyTitle");
  });

  it("renders the empty state only once loading has finished and the customer is authenticated", () => {
    const w = mountComp({ loading: false, history: [], isAuthenticated: true });
    expect(w.text()).toContain("ridePage.historyEmpty");
  });

  it("does not render the empty state when not authenticated (mirrors the original guard)", () => {
    const w = mountComp({ loading: false, history: [], isAuthenticated: false });
    expect(w.text()).not.toContain("ridePage.historyEmpty");
  });

  it("renders a history row with dropoff address, formatted date, price, and status", () => {
    const w = mountComp({ history: [ride()] });
    expect(w.text()).toContain("45 Avenue Hassan II");
    expect(w.text()).toContain("$32");
    expect(w.text()).toContain("ridePage.completed");
    // fmtDate uses the mocked "en" locale — assert on the year to avoid
    // coupling the test to a specific ICU month/day rendering.
    expect(w.text()).toContain("2026");
  });

  it("falls back to pickup address when dropoff_address is absent", () => {
    const w = mountComp({ history: [ride({ dropoff_address: "" })] });
    expect(w.text()).toContain("12 Rue Atlas");
  });

  it("shows the rebook button for a completed ride and emits rebook with the ride on click", async () => {
    const r = ride({ status: "completed" });
    const w = mountComp({ history: [r] });
    const rebookBtn = w.find("button");
    expect(rebookBtn.exists()).toBe(true);
    expect(rebookBtn.text()).toContain("ridePage.rebookCta");

    await rebookBtn.trigger("click");
    expect(w.emitted("rebook")).toBeTruthy();
    expect(w.emitted("rebook")[0]).toEqual([r]);
  });

  it("hides the rebook button and shows the cancelled label for a cancelled ride", () => {
    const w = mountComp({ history: [ride({ status: "cancelled" })] });
    expect(w.find("button").exists()).toBe(false);
    expect(w.text()).toContain("ridePage.cancelled");
  });

  it("renders the star rating badge when rider_driver_rating is present", () => {
    const w = mountComp({ history: [ride({ rider_driver_rating: 4 })] });
    expect(w.find('[aria-label="4 stars"]').exists()).toBe(true);
  });

  it("omits the star rating badge when rider_driver_rating is absent", () => {
    const w = mountComp({ history: [ride({ rider_driver_rating: null })] });
    expect(w.find('[aria-label$=" stars"]').exists()).toBe(false);
  });

  it("renders the section (not the empty state) once history has rows, even while re-fetching", () => {
    const w = mountComp({ history: [ride()], loading: true });
    expect(w.text()).not.toContain("ridePage.historyEmpty");
    expect(w.text()).toContain("45 Avenue Hassan II");
  });
});
