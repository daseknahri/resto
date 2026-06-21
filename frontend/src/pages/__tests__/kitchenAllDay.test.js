import { describe, it, expect } from "vitest";

// Pure mirror of the all-day prep-counts aggregation in OwnerKitchen.vue's
// allDayItems computed. Across active (not-yet-ready) orders it sums qty of
// non-voided, not-yet-ready items grouped by dish name (+ station), excluding
// held-course items unless includeHeld is on, respecting the prep-station
// filter, sorted by qty desc then name. This locks that derivation.

// Mirrors isItemHeld(item, order): a course-tagged item is held while its
// course is above the order's fired_course (default 1).
function isItemHeld(item, order) {
  const c = item.course ?? 0;
  if (c === 0) return false;
  return c > (order.fired_course ?? 1);
}

function allDayItems(orders, { prepStation = "", includeHeld = false } = {}) {
  const ps = prepStation;
  const groups = new Map();
  for (const order of orders) {
    for (const item of order.items || []) {
      if (item.is_voided || item.is_ready) continue;
      if (ps && item.station && item.station !== ps) continue;
      if (!includeHeld && isItemHeld(item, order)) continue;
      const qty = Number(item.qty) || 0;
      if (qty <= 0) continue;
      const station = item.station || "";
      const key = item.dish_name + String.fromCharCode(124) + station;
      const existing = groups.get(key);
      if (existing) existing.qty += qty;
      else groups.set(key, { key, name: item.dish_name, station, qty });
    }
  }
  return [...groups.values()].sort(
    (a, b) => b.qty - a.qty || a.name.localeCompare(b.name)
  );
}

describe("kitchen all-day prep-counts aggregation", () => {
  it("sums quantities of the same dish across multiple orders", () => {
    const orders = [
      { items: [{ dish_name: "Burger", qty: 8 }, { dish_name: "Fries", qty: 5 }] },
      { items: [{ dish_name: "Burger", qty: 6 }, { dish_name: "Fries", qty: 4 }] },
    ];
    expect(allDayItems(orders)).toEqual([
      { key: "Burger|", name: "Burger", station: "", qty: 14 },
      { key: "Fries|", name: "Fries", station: "", qty: 9 },
    ]);
  });

  it("sorts by qty desc then by name", () => {
    const orders = [
      { items: [{ dish_name: "Zucchini", qty: 3 }, { dish_name: "Apple", qty: 3 }, { dish_name: "Burger", qty: 10 }] },
    ];
    expect(allDayItems(orders).map((r) => r.name)).toEqual(["Burger", "Apple", "Zucchini"]);
  });

  it("excludes voided and already-ready items", () => {
    const orders = [
      { items: [
        { dish_name: "Burger", qty: 5 },
        { dish_name: "Burger", qty: 3, is_voided: true },
        { dish_name: "Burger", qty: 2, is_ready: true },
      ] },
    ];
    expect(allDayItems(orders)).toEqual([
      { key: "Burger|", name: "Burger", station: "", qty: 5 },
    ]);
  });

  it("excludes held-course items by default but includes them when asked", () => {
    const orders = [
      { fired_course: 1, items: [
        { dish_name: "Soup", qty: 2, course: 1 },   // fired (course == fired_course)
        { dish_name: "Steak", qty: 2, course: 2 },  // held (course > fired_course)
      ] },
    ];
    expect(allDayItems(orders)).toEqual([
      { key: "Soup|", name: "Soup", station: "", qty: 2 },
    ]);
    expect(allDayItems(orders, { includeHeld: true }).map((r) => r.name).sort()).toEqual([
      "Soup",
      "Steak",
    ]);
  });

  it("keeps the same dish on different stations as distinct rows", () => {
    const orders = [
      { items: [
        { dish_name: "Burger", qty: 4, station: "grill" },
        { dish_name: "Burger", qty: 2, station: "fry" },
      ] },
    ];
    const rows = allDayItems(orders);
    expect(rows).toHaveLength(2);
    expect(rows.find((r) => r.station === "grill").qty).toBe(4);
    expect(rows.find((r) => r.station === "fry").qty).toBe(2);
  });

  it("respects the prep-station filter", () => {
    const orders = [
      { items: [
        { dish_name: "Burger", qty: 4, station: "grill" },
        { dish_name: "Fries", qty: 9, station: "fry" },
      ] },
    ];
    expect(allDayItems(orders, { prepStation: "grill" })).toEqual([
      { key: "Burger|grill", name: "Burger", station: "grill", qty: 4 },
    ]);
  });

  it("returns an empty list when nothing is left to prep", () => {
    const orders = [
      { items: [{ dish_name: "Burger", qty: 3, is_ready: true }] },
    ];
    expect(allDayItems(orders)).toEqual([]);
  });

  it("ignores zero / non-numeric quantities", () => {
    const orders = [
      { items: [
        { dish_name: "Burger", qty: 0 },
        { dish_name: "Fries", qty: "bad" },
        { dish_name: "Soda", qty: 2 },
      ] },
    ];
    expect(allDayItems(orders)).toEqual([
      { key: "Soda|", name: "Soda", station: "", qty: 2 },
    ]);
  });
});
