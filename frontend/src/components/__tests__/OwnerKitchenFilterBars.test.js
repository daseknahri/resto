/**
 * Unit tests for OwnerKitchenFilterBars — the station / prep-station filter
 * nav bars of OwnerKitchen.vue (KDS), extracted into a standalone
 * presentational component (RISK FE-2). The filter values, the derived
 * option lists, and every order fetch/poll/status-mutation concern stay
 * owned by the parent; this component only renders what it's given and
 * asks the parent to change the selection via emits (`set-station-filter`,
 * `set-prep-station`).
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) => k,
  }),
}));

import OwnerKitchenFilterBars from "../OwnerKitchenFilterBars.vue";

const stationFilters = [
  { value: "all", label: "All", count: 5 },
  { value: "table", label: "Tables", count: 2 },
  { value: "pickup", label: "Pickup", count: 3 },
];

const prepStationFilters = [
  { value: "", label: "All stations", count: 5 },
  { value: "grill", label: "grill", count: 3 },
  { value: "fry", label: "fry", count: 2 },
];

const mountBars = (props = {}) =>
  mount(OwnerKitchenFilterBars, {
    props: {
      stationFilters,
      activeStationFilter: "all",
      prepStationFilters: [],
      activePrepStation: "",
      ...props,
    },
  });

describe("OwnerKitchenFilterBars", () => {
  it("renders the station filter bar with labels and counts", () => {
    const w = mountBars();
    expect(w.findAll("nav").length).toBe(1); // prep bar hidden by default (empty list)
    expect(w.text()).toContain("All");
    expect(w.text()).toContain("Tables");
    expect(w.text()).toContain("Pickup");
  });

  it("marks the active station filter via aria-pressed and the active class", () => {
    const w = mountBars({ activeStationFilter: "table" });
    const buttons = w.findAll("button");
    const tableBtn = buttons.find((b) => b.text().startsWith("Tables"));
    const allBtn = buttons.find((b) => b.text().startsWith("All"));

    expect(tableBtn.attributes("aria-pressed")).toBe("true");
    expect(tableBtn.classes()).toContain("kitchen-filter-btn--active");
    expect(allBtn.attributes("aria-pressed")).toBe("false");
    expect(allBtn.classes()).not.toContain("kitchen-filter-btn--active");
  });

  it("emits set-station-filter with the clicked value", async () => {
    const w = mountBars();
    const buttons = w.findAll("button");
    const pickupBtn = buttons.find((b) => b.text().startsWith("Pickup"));
    await pickupBtn.trigger("click");
    expect(w.emitted("set-station-filter")[0]).toEqual(["pickup"]);
  });

  it("hides the prep-station bar when there is 1 or fewer options", () => {
    const w = mountBars({ prepStationFilters: [{ value: "", label: "All", count: 1 }] });
    expect(w.findAll("nav").length).toBe(1);
  });

  it("shows the prep-station bar when there are 2+ options, marks the active one, and emits set-prep-station", async () => {
    const w = mountBars({ prepStationFilters, activePrepStation: "grill" });
    const navs = w.findAll("nav");
    expect(navs.length).toBe(2);

    const prepButtons = navs[1].findAll("button");
    const grillBtn = prepButtons.find((b) => b.text().startsWith("grill"));
    const fryBtn = prepButtons.find((b) => b.text().startsWith("fry"));

    expect(grillBtn.attributes("aria-pressed")).toBe("true");
    expect(fryBtn.attributes("aria-pressed")).toBe("false");

    await fryBtn.trigger("click");
    expect(w.emitted("set-prep-station")[0]).toEqual(["fry"]);
  });

  it("does not render a count badge when count is 0", () => {
    const w = mountBars({
      stationFilters: [{ value: "all", label: "All", count: 0 }],
    });
    expect(w.find(".kitchen-filter-count").exists()).toBe(false);
  });

  it("renders a count badge when count is greater than 0", () => {
    const w = mountBars();
    expect(w.findAll(".kitchen-filter-count").length).toBe(stationFilters.filter((f) => f.count > 0).length);
  });
});
