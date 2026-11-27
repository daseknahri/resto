import { describe, it, expect } from "vitest";
import {
  isAutoAcceptOn,
  clampPrepMinutes,
  clampPendingSlaMinutes,
  clampPendingAutoCancelMinutes,
  isAutoCancelValid,
  PREP_MINUTES_DEFAULT,
  PREP_MINUTES_MIN,
  PREP_MINUTES_MAX,
  PENDING_SLA_DEFAULT,
  PENDING_SLA_MIN,
  PENDING_SLA_MAX,
  PENDING_AUTO_CANCEL_DEFAULT,
  PENDING_AUTO_CANCEL_MAX,
} from "../orderHandling";

describe("isAutoAcceptOn — default-preserving guard", () => {
  it("is OFF for a profile without the flag (existing tenants unchanged)", () => {
    expect(isAutoAcceptOn({})).toBe(false);
    expect(isAutoAcceptOn({ name: "Demo" })).toBe(false);
  });

  it("is OFF for null/undefined profile", () => {
    expect(isAutoAcceptOn(null)).toBe(false);
    expect(isAutoAcceptOn(undefined)).toBe(false);
  });

  it("is OFF for an explicitly false flag", () => {
    expect(isAutoAcceptOn({ auto_accept_orders: false })).toBe(false);
  });

  it("only treats strict boolean true as ON", () => {
    expect(isAutoAcceptOn({ auto_accept_orders: true })).toBe(true);
    // Truthy-but-not-true values must NOT flip the indicator on.
    expect(isAutoAcceptOn({ auto_accept_orders: 1 })).toBe(false);
    expect(isAutoAcceptOn({ auto_accept_orders: "true" })).toBe(false);
  });
});

describe("clampPrepMinutes", () => {
  it("falls back to the default for blank / non-numeric input", () => {
    expect(clampPrepMinutes(null)).toBe(PREP_MINUTES_DEFAULT);
    expect(clampPrepMinutes(undefined)).toBe(PREP_MINUTES_DEFAULT);
    expect(clampPrepMinutes("")).toBe(PREP_MINUTES_DEFAULT);
    expect(clampPrepMinutes("abc")).toBe(PREP_MINUTES_DEFAULT);
    expect(clampPrepMinutes(0)).toBe(PREP_MINUTES_DEFAULT);
    expect(clampPrepMinutes(-5)).toBe(PREP_MINUTES_DEFAULT);
  });

  it("clamps to the supported range", () => {
    expect(clampPrepMinutes(1)).toBe(PREP_MINUTES_MIN);
    expect(clampPrepMinutes(999)).toBe(PREP_MINUTES_MAX);
    expect(clampPrepMinutes(30)).toBe(30);
  });

  it("rounds fractional input", () => {
    expect(clampPrepMinutes(20.4)).toBe(20);
    expect(clampPrepMinutes("25")).toBe(25);
  });
});

describe("clampPendingSlaMinutes (R6-16)", () => {
  it("falls back to the platform default for blank / non-numeric input", () => {
    expect(clampPendingSlaMinutes(null)).toBe(PENDING_SLA_DEFAULT);
    expect(clampPendingSlaMinutes(undefined)).toBe(PENDING_SLA_DEFAULT);
    expect(clampPendingSlaMinutes("")).toBe(PENDING_SLA_DEFAULT);
    expect(clampPendingSlaMinutes("abc")).toBe(PENDING_SLA_DEFAULT);
    expect(clampPendingSlaMinutes(0)).toBe(PENDING_SLA_DEFAULT);
    expect(clampPendingSlaMinutes(-5)).toBe(PENDING_SLA_DEFAULT);
  });

  it("clamps to the supported range", () => {
    expect(clampPendingSlaMinutes(1)).toBe(PENDING_SLA_MIN);
    expect(clampPendingSlaMinutes(999)).toBe(PENDING_SLA_MAX);
    expect(clampPendingSlaMinutes(15)).toBe(15);
  });
});

describe("clampPendingAutoCancelMinutes (R6-16)", () => {
  it("falls back to 0 (never) for blank / non-numeric input", () => {
    expect(clampPendingAutoCancelMinutes(null)).toBe(PENDING_AUTO_CANCEL_DEFAULT);
    expect(clampPendingAutoCancelMinutes(undefined)).toBe(PENDING_AUTO_CANCEL_DEFAULT);
    expect(clampPendingAutoCancelMinutes("")).toBe(PENDING_AUTO_CANCEL_DEFAULT);
    expect(clampPendingAutoCancelMinutes(0)).toBe(0);
    expect(clampPendingAutoCancelMinutes(-5)).toBe(0);
  });

  it("clamps to the supported range", () => {
    expect(clampPendingAutoCancelMinutes(999)).toBe(PENDING_AUTO_CANCEL_MAX);
    expect(clampPendingAutoCancelMinutes(90)).toBe(90);
  });
});

describe("isAutoCancelValid (R6-16)", () => {
  it("accepts 0 (never) and anything strictly above the SLA", () => {
    expect(isAutoCancelValid(0, 10)).toBe(true);
    expect(isAutoCancelValid(11, 10)).toBe(true);
    expect(isAutoCancelValid(200, 60)).toBe(true);
  });

  it("rejects auto-cancel at or below the SLA", () => {
    expect(isAutoCancelValid(10, 10)).toBe(false);
    expect(isAutoCancelValid(5, 10)).toBe(false);
    expect(isAutoCancelValid(30, 60)).toBe(false);
  });
});
