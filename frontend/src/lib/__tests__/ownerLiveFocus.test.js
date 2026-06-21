import { describe, it, expect } from "vitest";
import {
  minutesUntilScheduled,
  isDueSoon,
  upcomingOrders,
  orderAgeMinutes,
  isUrgentOrder,
  computeNextAction,
  DUE_SOON_WINDOW_MIN,
  UPCOMING_WINDOW_MIN,
} from "../ownerLiveFocus";

// Fixed reference "now" for deterministic time math.
const NOW = new Date("2026-06-21T12:00:00Z").getTime();
const minsFromNow = (m) => new Date(NOW + m * 60000).toISOString();
const minsAgo = (m) => new Date(NOW - m * 60000).toISOString();

describe("minutesUntilScheduled", () => {
  it("returns positive minutes for a future fire time", () => {
    expect(minutesUntilScheduled({ scheduled_for: minsFromNow(25) }, NOW)).toBe(25);
  });
  it("returns negative minutes once the fire time has passed", () => {
    expect(minutesUntilScheduled({ scheduled_for: minsAgo(10) }, NOW)).toBe(-10);
  });
  it("returns NaN when there is no scheduled_for", () => {
    expect(Number.isNaN(minutesUntilScheduled({}, NOW))).toBe(true);
    expect(Number.isNaN(minutesUntilScheduled({ scheduled_for: null }, NOW))).toBe(true);
  });
});

describe("isDueSoon", () => {
  it("is true inside the prep window and once overdue", () => {
    expect(isDueSoon({ scheduled_for: minsFromNow(DUE_SOON_WINDOW_MIN - 1) }, NOW)).toBe(true);
    expect(isDueSoon({ scheduled_for: minsAgo(5) }, NOW)).toBe(true);
  });
  it("is false when the fire time is still far out", () => {
    expect(isDueSoon({ scheduled_for: minsFromNow(DUE_SOON_WINDOW_MIN + 30) }, NOW)).toBe(false);
  });
  it("is false without a scheduled_for", () => {
    expect(isDueSoon({}, NOW)).toBe(false);
  });
});

describe("upcomingOrders", () => {
  it("includes scheduled + near-due orders within the window, soonest first", () => {
    const orders = [
      { id: 1, status: "scheduled", scheduled_for: minsFromNow(90) },
      { id: 2, status: "scheduled", scheduled_for: minsFromNow(20) },
      { id: 3, status: "pending", scheduled_for: minsFromNow(45) }, // released but still future
    ];
    const out = upcomingOrders(orders, NOW);
    expect(out.map((o) => o.id)).toEqual([2, 3, 1]);
  });

  it("excludes orders beyond the look-ahead window", () => {
    const orders = [
      { id: 1, status: "scheduled", scheduled_for: minsFromNow(UPCOMING_WINDOW_MIN + 60) },
      { id: 2, status: "scheduled", scheduled_for: minsFromNow(30) },
    ];
    expect(upcomingOrders(orders, NOW).map((o) => o.id)).toEqual([2]);
  });

  it("excludes terminal orders and ASAP (no scheduled_for) orders", () => {
    const orders = [
      { id: 1, status: "completed", scheduled_for: minsFromNow(10) },
      { id: 2, status: "cancelled", scheduled_for: minsFromNow(10) },
      { id: 3, status: "pending" },
    ];
    expect(upcomingOrders(orders, NOW)).toEqual([]);
  });

  it("includes an overdue scheduled order (negative minutes)", () => {
    const orders = [{ id: 1, status: "scheduled", scheduled_for: minsAgo(5) }];
    expect(upcomingOrders(orders, NOW).map((o) => o.id)).toEqual([1]);
  });
});

describe("orderAgeMinutes / isUrgentOrder", () => {
  it("computes age from created_at", () => {
    expect(orderAgeMinutes({ created_at: minsAgo(12) }, NOW)).toBe(12);
  });
  it("flags pending past 15m as urgent, not before", () => {
    expect(isUrgentOrder({ status: "pending", created_at: minsAgo(16) }, NOW)).toBe(true);
    expect(isUrgentOrder({ status: "pending", created_at: minsAgo(10) }, NOW)).toBe(false);
  });
  it("ignores statuses without a threshold", () => {
    expect(isUrgentOrder({ status: "ready", created_at: minsAgo(120) }, NOW)).toBe(false);
  });
});

describe("computeNextAction priority ladder", () => {
  it("prioritises an overdue pending order to confirm", () => {
    const orders = [
      { id: 1, order_number: "A1", status: "pending", created_at: minsAgo(20) },
      { id: 2, order_number: "A2", status: "ready", created_at: minsAgo(5) },
    ];
    const a = computeNextAction(orders, { now: NOW });
    expect(a.kind).toBe("confirm");
    expect(a.order.id).toBe(1);
    expect(a.minutes).toBe(20);
  });

  it("picks the OLDEST overdue pending order first", () => {
    const orders = [
      { id: 1, order_number: "A1", status: "pending", created_at: minsAgo(18) },
      { id: 2, order_number: "A2", status: "pending", created_at: minsAgo(40) },
    ];
    expect(computeNextAction(orders, { now: NOW }).order.id).toBe(2);
  });

  it("surfaces a due-soon scheduled order above ready handoff", () => {
    const orders = [
      { id: 1, order_number: "S1", status: "scheduled", scheduled_for: minsFromNow(10) },
      { id: 2, order_number: "R1", status: "ready", created_at: minsAgo(3) },
    ];
    const a = computeNextAction(orders, { now: NOW });
    expect(a.kind).toBe("dueSoon");
    expect(a.order.id).toBe(1);
  });

  it("falls to handoff when nothing more urgent exists", () => {
    const orders = [{ id: 2, order_number: "R1", status: "ready", created_at: minsAgo(3) }];
    expect(computeNextAction(orders, { now: NOW }).kind).toBe("handoff");
  });

  it("detects a held course ready to fire", () => {
    const orders = [
      {
        id: 3,
        order_number: "T1",
        status: "preparing",
        created_at: minsAgo(2),
        fired_course: 1,
        items: [{ course: 2, qty: 1 }],
      },
    ];
    expect(computeNextAction(orders, { now: NOW }).kind).toBe("fire");
  });

  it("flags an overdue preparing order", () => {
    const orders = [
      { id: 4, order_number: "P1", status: "preparing", created_at: minsAgo(30), items: [] },
    ];
    const a = computeNextAction(orders, { now: NOW });
    expect(a.kind).toBe("overdue");
    expect(a.minutes).toBe(30);
  });

  it("falls back to a non-overdue pending confirm", () => {
    const orders = [
      { id: 5, order_number: "N1", status: "pending", created_at: minsAgo(3) },
    ];
    expect(computeNextAction(orders, { now: NOW }).kind).toBe("confirm");
  });

  it("suggests resetting sold-out dishes when nothing else is pending", () => {
    expect(computeNextAction([], { now: NOW, soldOutCount: 4 })).toEqual({ kind: "soldOut", count: 4 });
  });

  it("returns all-clear when there is nothing to do", () => {
    expect(computeNextAction([], { now: NOW })).toEqual({ kind: "allClear" });
    expect(computeNextAction([{ id: 9, status: "completed" }], { now: NOW })).toEqual({ kind: "allClear" });
  });
});
