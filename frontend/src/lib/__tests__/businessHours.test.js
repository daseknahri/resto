/**
 * Unit tests for the centralized open/closed display verdict.
 *
 * isRestaurantOpenNow(profile) is THE single source of truth every storefront
 * surface (Menu, MenuSelect, Cart, DishPage notice, CustomerLeadPage) consumes.
 * It must prefer the server's authoritative tenant-local boolean
 * `profile.is_open_now`, and only fall back to the legacy browser-clock schedule
 * derivation when that field is absent.
 */
import { describe, it, expect } from "vitest";
import {
  WEEKDAY_KEYS,
  isRestaurantOpenNow,
  canAddToCartNow,
  canPlaceImmediateOrderNow,
  classifyClosedOrderState,
} from "../businessHours";

/** Build a schedule with the same enabled/open/close applied to every weekday. */
const uniformSchedule = ({ enabled, open = "09:00", close = "18:00" }) =>
  Object.fromEntries(WEEKDAY_KEYS.map((day) => [day, { enabled, open, close }]));

// Every day disabled → isCurrentlyOpenBySchedule() is false regardless of the
// browser's current weekday/time, making the fallback deterministic in CI.
const allDaysClosed = uniformSchedule({ enabled: false });
// Every day enabled for the full 24h → schedule reads open at any wall-clock time.
const allDaysOpen = uniformSchedule({ enabled: true, open: "00:00", close: "23:59" });

describe("isRestaurantOpenNow", () => {
  describe("server is_open_now wins (authoritative)", () => {
    it("returns true when is_open_now === true", () => {
      expect(isRestaurantOpenNow({ is_open_now: true })).toBe(true);
    });

    it("returns false when is_open_now === false", () => {
      expect(isRestaurantOpenNow({ is_open_now: false })).toBe(false);
    });

    it("is_open_now overrides a contradicting is_open flag (temp-disable / closure)", () => {
      // Manually "open" but server says closed (temp-disabled or closure date today).
      expect(isRestaurantOpenNow({ is_open_now: false, is_open: true })).toBe(false);
      // Manually "closed" but server's tenant-local verdict says open.
      expect(isRestaurantOpenNow({ is_open_now: true, is_open: false })).toBe(true);
    });

    it("is_open_now overrides the browser-clock schedule", () => {
      expect(isRestaurantOpenNow({ is_open_now: false, business_hours_schedule: allDaysOpen })).toBe(false);
      expect(isRestaurantOpenNow({ is_open_now: true, business_hours_schedule: allDaysClosed })).toBe(true);
    });
  });

  describe("fallback when is_open_now is absent (older payloads / safety)", () => {
    it("manual-closed: is_open === false → false", () => {
      expect(isRestaurantOpenNow({ is_open: false })).toBe(false);
    });

    it("schedule-closed: every day disabled → false", () => {
      expect(isRestaurantOpenNow({ is_open: true, business_hours_schedule: allDaysClosed })).toBe(false);
    });

    it("default-open: no negative signal → true", () => {
      expect(isRestaurantOpenNow({})).toBe(true);
      expect(isRestaurantOpenNow({ is_open: true })).toBe(true);
      expect(isRestaurantOpenNow({ is_open: true, business_hours_schedule: allDaysOpen })).toBe(true);
    });

    it("ignores a non-boolean is_open_now and uses the fallback", () => {
      // null / undefined are NOT booleans → must not short-circuit.
      expect(isRestaurantOpenNow({ is_open_now: null, is_open: false })).toBe(false);
      expect(isRestaurantOpenNow({ is_open_now: undefined, is_open: true })).toBe(true);
    });
  });

  describe("defensive null handling", () => {
    it("treats a missing profile as open (no negative signal)", () => {
      expect(isRestaurantOpenNow(null)).toBe(true);
      expect(isRestaurantOpenNow(undefined)).toBe(true);
    });
  });
});

/**
 * Closed-now ORDERING gates — mirror the backend order gate so the storefront
 * never builds an un-checkout-able cart.
 *
 *  - IMMEDIATE order possible only when open-now.
 *  - SCHEDULED (order-ahead) pickup/delivery bypasses the gate (handled at the
 *    Cart level), so add-to-cart for non-table context stays enabled when closed.
 *  - DINE-IN (table) has no scheduling, so closed-now blocks it entirely.
 */
describe("canAddToCartNow (dine-in closed gate)", () => {
  const openProfile = { is_open_now: true };
  const closedProfile = { is_open_now: false };

  it("dine-in + closed-now → blocked (the unrecoverable case)", () => {
    expect(canAddToCartNow({ profile: closedProfile, isTableContext: true })).toBe(false);
  });

  it("dine-in + open-now → allowed", () => {
    expect(canAddToCartNow({ profile: openProfile, isTableContext: true })).toBe(true);
  });

  it("pickup/delivery (non-table) + closed-now → still allowed (order-ahead is valid)", () => {
    expect(canAddToCartNow({ profile: closedProfile, isTableContext: false })).toBe(true);
  });

  it("pickup/delivery (non-table) + open-now → allowed", () => {
    expect(canAddToCartNow({ profile: openProfile, isTableContext: false })).toBe(true);
  });

  it("open restaurant is unchanged for every context", () => {
    expect(canAddToCartNow({ profile: openProfile, isTableContext: true })).toBe(true);
    expect(canAddToCartNow({ profile: openProfile, isTableContext: false })).toBe(true);
  });

  it("honors a manual is_open=false closure for dine-in (falls through to the verdict)", () => {
    expect(canAddToCartNow({ profile: { is_open: false }, isTableContext: true })).toBe(false);
    // …but non-table can still order ahead.
    expect(canAddToCartNow({ profile: { is_open: false }, isTableContext: false })).toBe(true);
  });
});

describe("canPlaceImmediateOrderNow (immediate-order gate)", () => {
  it("open-now → an immediate order is possible", () => {
    expect(canPlaceImmediateOrderNow({ is_open_now: true })).toBe(true);
  });

  it("closed-now → an immediate order is NOT possible (scheduled handled separately)", () => {
    expect(canPlaceImmediateOrderNow({ is_open_now: false })).toBe(false);
  });

  it("manual closure (is_open=false) blocks an immediate order", () => {
    expect(canPlaceImmediateOrderNow({ is_open: false })).toBe(false);
  });

  it("missing profile defaults to open (no negative signal)", () => {
    expect(canPlaceImmediateOrderNow(undefined)).toBe(true);
  });
});

describe("classifyClosedOrderState (Cart Place Order gate)", () => {
  const open = { is_open_now: true };
  const closed = { is_open_now: false };

  it("open-now → 'open' for every context (no new friction)", () => {
    expect(classifyClosedOrderState({ profile: open, isTableContext: true, isScheduled: false })).toBe("open");
    expect(classifyClosedOrderState({ profile: open, isTableContext: false, isScheduled: false })).toBe("open");
    expect(classifyClosedOrderState({ profile: open, isTableContext: false, isScheduled: true })).toBe("open");
  });

  it("closed-now + dine-in + immediate → 'blocked' (no scheduling escape)", () => {
    expect(classifyClosedOrderState({ profile: closed, isTableContext: true, isScheduled: false })).toBe("blocked");
  });

  it("closed-now + pickup/delivery + immediate → 'schedule' (steer to order-ahead)", () => {
    expect(classifyClosedOrderState({ profile: closed, isTableContext: false, isScheduled: false })).toBe("schedule");
  });

  it("closed-now + pickup/delivery + SCHEDULED → 'open' (order-ahead preserved)", () => {
    expect(classifyClosedOrderState({ profile: closed, isTableContext: false, isScheduled: true })).toBe("open");
  });

  it("a scheduled flag never rescues dine-in semantics, but dine-in is never scheduled in practice", () => {
    // Cart only sets isScheduled for pickup/delivery (canSchedule excludes table),
    // so a scheduled dine-in is not a real state — but the pure function still
    // treats any scheduled order as allowed.
    expect(classifyClosedOrderState({ profile: closed, isTableContext: true, isScheduled: true })).toBe("open");
  });

  it("manual is_open=false closure → immediate blocked/steered, scheduled still allowed", () => {
    const manualClosed = { is_open: false };
    expect(classifyClosedOrderState({ profile: manualClosed, isTableContext: true, isScheduled: false })).toBe("blocked");
    expect(classifyClosedOrderState({ profile: manualClosed, isTableContext: false, isScheduled: false })).toBe("schedule");
    expect(classifyClosedOrderState({ profile: manualClosed, isTableContext: false, isScheduled: true })).toBe("open");
  });
});
