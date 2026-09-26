/**
 * Regression tests for `formatCurrencyString` — the single source of truth for
 * NON-converting currency formatting, introduced to replace ~a dozen copy-pasted
 * `new Intl.NumberFormat(locale, {style:"currency",…})` helpers across the
 * admin/owner/driver/waiter screens.
 *
 * The core guard is EQUIVALENCE: for every valid input the function must return
 * the exact string the old inline helpers produced. We assert that against a
 * freshly-constructed reference `Intl.NumberFormat` (rather than a hard-coded
 * literal) so the test stays correct across Node/ICU versions and locales.
 */
import { describe, it, expect } from "vitest";
import { formatCurrencyString } from "../intlFormatters";

const ref = (locale, amount, currency, options = {}) =>
  new Intl.NumberFormat(locale, { style: "currency", currency, ...options }).format(amount);

describe("formatCurrencyString", () => {
  it("is byte-identical to the inline Intl.NumberFormat it replaced (the dedup must not change any displayed amount)", () => {
    const cases = [
      ["en", 12.5, "MAD", { maximumFractionDigits: 2 }],
      ["fr", 12.5, "MAD", { maximumFractionDigits: 2 }],
      ["ar", 1234.56, "MAD", { maximumFractionDigits: 2 }],
      ["en", 0, "MAD", { maximumFractionDigits: 2 }],
      ["en", 1000, "MAD", { maximumFractionDigits: 0 }], // owner/analytics whole-currency
      ["en", 42.99, "EUR", { maximumFractionDigits: 2 }],
      ["en", 7, "MAD", {}], // no options → code's Intl default (MAD → 2 dp)
    ];
    for (const [locale, amount, code, opts] of cases) {
      expect(formatCurrencyString(locale, amount, code, opts)).toBe(ref(locale, amount, code, opts));
    }
  });

  it("coerces a non-finite value to 0 (matches the old `Number.isFinite(…) ? … : 0` guard)", () => {
    expect(formatCurrencyString("en", "not-a-number", "MAD")).toBe(ref("en", 0, "MAD"));
    expect(formatCurrencyString("en", undefined, "MAD")).toBe(ref("en", 0, "MAD"));
    expect(formatCurrencyString("en", null, "MAD")).toBe(ref("en", 0, "MAD"));
    expect(formatCurrencyString("en", NaN, "MAD")).toBe(ref("en", 0, "MAD"));
  });

  it("accepts a numeric string exactly as the old helpers' parseFloat did for clean values", () => {
    expect(formatCurrencyString("en", "12.34", "MAD", { maximumFractionDigits: 2 }))
      .toBe(ref("en", 12.34, "MAD", { maximumFractionDigits: 2 }));
  });

  it("falls back to 'MAD' for a falsy currency code (matches `currency || 'MAD'`)", () => {
    expect(formatCurrencyString("en", 5, "")).toBe(ref("en", 5, "MAD"));
    expect(formatCurrencyString("en", 5, null)).toBe(ref("en", 5, "MAD"));
    expect(formatCurrencyString("en", 5, undefined)).toBe(ref("en", 5, "MAD")); // default arg
  });

  it("never throws on a malformed (non-ISO-4217) code — returns a plain symbol-less fallback", () => {
    // The old per-screen helpers each had a try/catch; the real app never passes a
    // bad code (MAD/EUR/SAR/AED), so this branch is defensive, but it must not white-screen.
    expect(() => formatCurrencyString("en", 12.5, "NOT_A_CODE")).not.toThrow();
    expect(formatCurrencyString("en", 12.5, "NOT_A_CODE")).toBe("NOT_A_CODE 12.50");
    expect(formatCurrencyString("en", 30, "NOT_A_CODE", { maximumFractionDigits: 0 })).toBe("NOT_A_CODE 30");
  });
});
