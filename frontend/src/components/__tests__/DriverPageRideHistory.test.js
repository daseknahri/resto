/**
 * Unit tests for DriverPageRideHistory — the "ride history" accordion of
 * DriverPage.vue, extracted into a standalone presentational component
 * (RISK FE-2), mirroring the merged DriverPageDeliveryHistory.vue /
 * DriverPageCashoutHistory.vue precedents. Fetch state and the car-only
 * visibility gate stay in the parent; this component only renders whatever
 * history it's given and asks the parent to toggle via the `toggle` emit.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import DriverPageRideHistory from "../DriverPageRideHistory.vue";

const fmtDate = (iso) => `date:${iso}`;
const fmtMoney = (v) => `$${v}`;

const ride = (overrides = {}) => ({
  id: 1,
  dropoff_address: "12 Rue Hassan II",
  kind: "ride",
  payment_method: "wallet",
  fare: "35.00",
  completed_at: "2026-07-01T12:00:00Z",
  driver_rider_rating: null,
  ...overrides,
});

const mountComp = (props = {}) =>
  mount(DriverPageRideHistory, {
    props: {
      show: false,
      loading: false,
      items: [],
      fmtDate,
      fmtMoney,
      ...props,
    },
  });

describe("DriverPageRideHistory", () => {
  it("renders the header but keeps the panel collapsed when show is false", () => {
    const w = mountComp({ show: false, items: [ride()] });
    expect(w.text()).toContain("driverRides.historyTitle");
    expect(w.text()).not.toContain("12 Rue Hassan II");
    expect(w.find("button[aria-expanded]").attributes("aria-expanded")).toBe("false");
  });

  it("marks the header aria-expanded true when show is true", () => {
    const w = mountComp({ show: true });
    expect(w.find("button[aria-expanded]").attributes("aria-expanded")).toBe("true");
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
    expect(w.text()).toContain("driverRides.historyEmpty");
  });

  it("renders ride rows with dropoff address, formatted date and fare", () => {
    const w = mountComp({ show: true, items: [ride()] });
    expect(w.text()).toContain("12 Rue Hassan II");
    expect(w.text()).toContain("date:2026-07-01T12:00:00Z");
    expect(w.text()).toContain("$35.00");
  });

  it("shows the paid-wallet chip for a wallet ride", () => {
    const w = mountComp({ show: true, items: [ride({ payment_method: "wallet" })] });
    expect(w.text()).toContain("driverRides.paidWallet");
    expect(w.text()).not.toContain("driverRides.collectCash");
  });

  it("shows the collect-cash chip with the fare for a cash ride", () => {
    const w = mountComp({ show: true, items: [ride({ payment_method: "cash" })] });
    expect(w.text()).toContain('driverRides.collectCash:{"amount":"$35.00"}');
    expect(w.text()).not.toContain("driverRides.paidWallet");
  });

  it("prefixes a package ride with the package emoji", () => {
    const w = mountComp({ show: true, items: [ride({ kind: "package" })] });
    expect(w.text()).toContain("📦");
  });

  it("does not render the package emoji for a normal ride", () => {
    const w = mountComp({ show: true, items: [ride({ kind: "ride" })] });
    expect(w.text()).not.toContain("📦");
  });

  it("shows the rider rating star only when a rating is present", () => {
    const withoutRating = mountComp({ show: true, items: [ride({ driver_rider_rating: null })] });
    expect(withoutRating.text()).not.toContain("★");

    const withRating = mountComp({ show: true, items: [ride({ driver_rider_rating: 5 })] });
    expect(withRating.text()).toContain("★");
    expect(withRating.text()).toContain("5");
  });
});
