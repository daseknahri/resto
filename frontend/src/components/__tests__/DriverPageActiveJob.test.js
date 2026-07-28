/**
 * Unit tests for DriverPageActiveJob — the active-job hero extracted from
 * DriverPage.vue (RISK FE-2, hardest tier). It renders the sticky hero for the
 * driver's current job and forwards intent via emits: advance(to), fail({reason,
 * note}), toggleDetail. The activeJob data, the advance action, busy, the
 * computeds and showActiveJobDetail (+ its watcher) stay in the parent; only the
 * fail-picker UI state is local here.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

// Stub AppIcon to a simple span so icon names don't matter to these tests.
vi.mock("../AppIcon.vue", () => ({
  default: { name: "AppIcon", props: ["name"], template: "<span />" },
}));

import DriverPageActiveJob from "../DriverPageActiveJob.vue";

const job = (overrides = {}) => ({
  id: 3,
  status: "assigned",
  business_type: "restaurant",
  order_number: "1042",
  restaurant_name: "Acme Bistro",
  driver_payout: "18.00",
  distance_km: 2.4,
  items_count: 3,
  pickup_address: "1 Pickup St",
  pickup_lat: 1,
  pickup_lng: 2,
  delivery_address: "9 Dropoff Ave",
  delivery_lat: 3,
  delivery_lng: 4,
  collect_cash: false,
  order_total: "50.00",
  customer_phone: "+212600",
  customer_name: "Sam",
  restaurant_phone: "+212611",
  items: [{ name: "Pizza", qty: 2 }],
  ...overrides,
});

const statusLabel = (s) => `status(${s})`;
const fmtMoney = (v) => `$${v}`;
const mapsLink = (lat, lng) => `maps:${lat},${lng}`;

const mountHero = (props = {}) =>
  mount(DriverPageActiveJob, {
    props: {
      job: job(),
      nextAction: { to: "picked_up", label: "Mark picked up" },
      readyEta: null,
      navigateHref: "",
      busy: false,
      detailOpen: false,
      statusLabel,
      fmtMoney,
      mapsLink,
      ...props,
    },
  });

describe("DriverPageActiveJob", () => {
  it("renders the status label, restaurant name, order number and payout", () => {
    const w = mountHero();
    expect(w.text()).toContain("status(assigned)");
    expect(w.text()).toContain("Acme Bistro");
    expect(w.text()).toContain("#1042");
    expect(w.text()).toContain("$18.00");
  });

  it("shows the pickup address before pickup and the dropoff after", () => {
    expect(mountHero({ job: job({ status: "assigned" }) }).text()).toContain("1 Pickup St");
    expect(mountHero({ job: job({ status: "picked_up" }) }).text()).toContain("9 Dropoff Ave");
  });

  it("shows the food-ready ETA when provided", () => {
    const w = mountHero({ readyEta: { clock: "18:30", mins: 12 } });
    expect(w.text()).toContain('driver.foodReady:{"time":"18:30"}');
    expect(w.text()).toContain('driver.foodReadyIn:{"minutes":12}');
  });

  it("shows collect-cash for COD and prepaid otherwise", () => {
    expect(mountHero({ job: job({ collect_cash: true }) }).text()).toContain("driver.collectCash");
    expect(mountHero({ job: job({ collect_cash: false, order_total: "50.00" }) }).text()).toContain("driver.prepaid:{\"amount\":\"$50.00\"}");
  });

  it("emits advance with nextAction.to when the big button is clicked", async () => {
    const w = mountHero({ nextAction: { to: "delivered", label: "Confirm" } });
    const advanceBtn = w.findAll("button").find((b) => b.text().includes("Confirm"));
    await advanceBtn.trigger("click");
    expect(w.emitted("advance")[0]).toEqual(["delivered"]);
  });

  it("shows the code reminder only for the delivered step", () => {
    expect(mountHero({ nextAction: { to: "delivered", label: "x" } }).text()).toContain("driver.codeReminder");
    expect(mountHero({ nextAction: { to: "picked_up", label: "x" } }).text()).not.toContain("driver.codeReminder");
  });

  it("disables the advance button and shows a spinner while busy", () => {
    const w = mountHero({ busy: true });
    const advanceBtn = w.findAll("button").find((b) => b.attributes("aria-busy") === "true");
    expect(advanceBtn).toBeTruthy();
    expect(advanceBtn.attributes("disabled")).toBeDefined();
    expect(advanceBtn.find(".animate-spin").exists()).toBe(true);
  });

  it("renders the navigate link only when a navigateHref is provided", () => {
    expect(mountHero({ navigateHref: "" }).find('a[target="_blank"]').exists()).toBe(false);
    const w = mountHero({ navigateHref: "https://maps/x" });
    expect(w.find('a[href="https://maps/x"]').exists()).toBe(true);
  });

  it("opens the fail picker, emits fail with reason + note, and cancels", async () => {
    const w = mountHero();
    // open
    await w.findAll("button").find((b) => b.text() === "driver.actionFailed").trigger("click");
    expect(w.text()).toContain("driver.failReasonTitle");
    // type a note
    await w.find("input").setValue("gate locked");
    // pick a reason -> emits fail
    await w.findAll("button").find((b) => b.text() === "driver.failReason_bad_address").trigger("click");
    expect(w.emitted("fail")[0]).toEqual([{ reason: "bad_address", note: "gate locked" }]);
    // picker closed again after submit
    expect(w.text()).not.toContain("driver.failReasonTitle");
  });

  it("emits toggleDetail when the detail disclosure is clicked", async () => {
    const w = mountHero({ detailOpen: false });
    await w.findAll("button").find((b) => b.attributes("aria-controls") === "active-job-detail-panel").trigger("click");
    expect(w.emitted("toggleDetail")).toBeTruthy();
  });

  it("renders the detail panel (maps + phone links, items, payout) only when detailOpen", () => {
    expect(mountHero({ detailOpen: false }).text()).not.toContain("driver.itemsTitle");
    const w = mountHero({ detailOpen: true });
    expect(w.find('a[href="maps:1,2"]').exists()).toBe(true); // pickup maps link
    expect(w.find('a[href="tel:+212600"]').exists()).toBe(true); // customer phone
    expect(w.text()).toContain("driver.itemsTitle");
    expect(w.text()).toContain("Pizza");
  });
});
