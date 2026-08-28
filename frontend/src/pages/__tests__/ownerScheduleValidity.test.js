import { describe, it, expect } from "vitest";

// Pure mirror of OwnerProfile.vue's `_isInvalidHoursWindow` predicate used by
// saveSchedule() (same convention as checkoutEta / driverTerminalOutcome tests).
// Locks the contract that the business-hours editor ACCEPTS an overnight window
// (close earlier than open — e.g. a bar open 18:00–02:00) and only REJECTS a
// zero-length / ambiguous window where open === close. Regression guard for the
// old `close <= open` rule, which blocked every legitimate after-midnight venue.
const isInvalidHoursWindow = (open, close) =>
  Boolean(open) && Boolean(close) && open === close;

// Mirror of the day-level guard: a day is only flagged when it is ENABLED and its
// window is invalid (a disabled day, or one with a missing time, is never flagged).
const findInvalidDay = (days) =>
  days.find((d) => d.enabled && isInvalidHoursWindow(d.open, d.close));

describe("business-hours window validity (OwnerProfile.saveSchedule)", () => {
  it("accepts a normal same-day window (open < close)", () => {
    expect(isInvalidHoursWindow("09:00", "22:00")).toBe(false);
  });

  it("accepts an overnight window that closes after midnight (close < open)", () => {
    expect(isInvalidHoursWindow("18:00", "02:00")).toBe(false);
    expect(isInvalidHoursWindow("22:00", "06:00")).toBe(false);
  });

  it("rejects a zero-length / ambiguous window (open === close)", () => {
    expect(isInvalidHoursWindow("09:00", "09:00")).toBe(true);
    expect(isInvalidHoursWindow("00:00", "00:00")).toBe(true);
  });

  it("does not flag a window with a missing open or close (guarded upstream)", () => {
    expect(isInvalidHoursWindow("", "22:00")).toBe(false);
    expect(isInvalidHoursWindow("09:00", "")).toBe(false);
  });

  it("flags only the enabled day whose open === close", () => {
    const days = [
      { key: "mon", enabled: true, open: "18:00", close: "02:00" }, // overnight → OK
      { key: "tue", enabled: false, open: "09:00", close: "09:00" }, // invalid but disabled → ignored
      { key: "wed", enabled: true, open: "10:00", close: "10:00" }, // enabled + equal → flagged
    ];
    expect(findInvalidDay(days)?.key).toBe("wed");
  });

  it("passes a full week of valid windows (overnight + same-day mix)", () => {
    const days = [
      { key: "mon", enabled: true, open: "09:00", close: "22:00" },
      { key: "fri", enabled: true, open: "18:00", close: "02:00" },
      { key: "sat", enabled: true, open: "20:00", close: "04:00" },
      { key: "sun", enabled: false, open: "09:00", close: "09:00" },
    ];
    expect(findInvalidDay(days)).toBeUndefined();
  });
});
