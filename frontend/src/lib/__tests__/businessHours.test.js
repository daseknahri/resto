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
import { WEEKDAY_KEYS, isRestaurantOpenNow } from "../businessHours";

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
