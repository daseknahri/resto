/**
 * Unit tests for WaiterFloorLegend — the floor-map status legend of WaiterPage,
 * a STATIC presentational child (RISK FE-2). No props/state/emits; it only renders
 * the legend label + the four table-status rows.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

import WaiterFloorLegend from "../WaiterFloorLegend.vue";

describe("WaiterFloorLegend", () => {
  it("renders the legend label and all four status rows", () => {
    const w = mount(WaiterFloorLegend);
    expect(w.text()).toContain("waiterPage.floorLegend");
    expect(w.text()).toContain("waiterPage.floorStatusOpen");
    expect(w.text()).toContain("waiterPage.floorStatusOccupied");
    expect(w.text()).toContain("waiterPage.floorStatusDirty");
    expect(w.text()).toContain("waiterPage.floorStatusReserved");
    expect(w.findAll("li")).toHaveLength(4);
  });
});
