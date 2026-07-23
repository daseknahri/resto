/**
 * Unit tests for WaiterFloorTileGrid — the floor table-tile grid extracted from
 * WaiterPage.vue's floor view (RISK FE-2). It renders the tappable tiles and
 * emits `toggle(tile)`; the floor data, the expanded-tile state and the actions
 * stay in the parent (tiles + expandedKey + display helpers passed as props).
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import WaiterFloorTileGrid from "../WaiterFloorTileGrid.vue";

const tile = (overrides = {}) => ({
  tableKey: "t1",
  tableLabel: "Table 1",
  tableStatus: "occupied",
  tableCapacity: 4,
  orders: [{ status: "preparing", currency: "MAD" }],
  totalOutstanding: "120",
  longestElapsedLabel: "18m",
  longestElapsedClass: "text-amber-300",
  ...overrides,
});

const mountGrid = (props = {}) =>
  mount(WaiterFloorTileGrid, {
    props: {
      tiles: [tile()],
      expandedKey: null,
      floorTileClass: () => "tile-x",
      floorDotClass: () => "dot-x",
      tableStatusBadgeClass: () => "badge-x",
      fmtOrderPrice: (a) => `$${a}`,
      ...props,
    },
  });

describe("WaiterFloorTileGrid", () => {
  it("renders a tile per entry with label, status and order count", () => {
    const w = mountGrid();
    expect(w.text()).toContain("Table 1");
    expect(w.text()).toContain("waiterPage.tableStatus_occupied");
    expect(w.text()).toContain("1"); // order-count badge
    expect(w.text()).toContain('waiterPage.floorCapacity:{"n":4}');
  });

  it("shows the outstanding total and longest-elapsed badge when occupied", () => {
    const w = mountGrid({ tiles: [tile({ totalOutstanding: "120", longestElapsedLabel: "18m" })] });
    expect(w.text()).toContain("$120");
    expect(w.text()).toContain("18m");
  });

  it("shows the no-orders hint for an empty tile", () => {
    const w = mountGrid({ tiles: [tile({ orders: [], totalOutstanding: "0" })] });
    expect(w.text()).toContain("waiterPage.floorNoOrders");
  });

  it("shows the ready pulse when a tile has a ready order", () => {
    const readyPulse = (t) => t.find(".animate-ping").exists();
    expect(readyPulse(mountGrid({ tiles: [tile({ orders: [{ status: "ready", currency: "MAD" }] })] }))).toBe(true);
    expect(readyPulse(mountGrid({ tiles: [tile({ orders: [{ status: "preparing", currency: "MAD" }] })] }))).toBe(false);
  });

  it("reflects the expanded tile via aria-pressed and the rotated indicator", () => {
    const w = mountGrid({ expandedKey: "t1" });
    const btn = w.find("button");
    expect(btn.attributes("aria-pressed")).toBe("true");
    expect(w.find(".rotate-180").exists()).toBe(true);
    // not expanded
    expect(mountGrid({ expandedKey: null }).find("button").attributes("aria-pressed")).toBe("false");
  });

  it("emits toggle with the tile when a tile is clicked", async () => {
    const t = tile();
    const w = mountGrid({ tiles: [t] });
    await w.find("button").trigger("click");
    expect(w.emitted("toggle")[0]).toEqual([t]);
  });

  it("renders one button per tile", () => {
    const w = mountGrid({ tiles: [tile({ tableKey: "a" }), tile({ tableKey: "b" }), tile({ tableKey: "c" })] });
    expect(w.findAll("button").length).toBe(3);
  });
});
