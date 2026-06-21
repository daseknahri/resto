import { describe, it, expect } from "vitest";
import {
  isAutoAcceptOn,
  clampPrepMinutes,
  PREP_MINUTES_DEFAULT,
  PREP_MINUTES_MIN,
  PREP_MINUTES_MAX,
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
