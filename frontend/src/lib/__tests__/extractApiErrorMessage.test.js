/**
 * extractApiErrorMessage — the shared DRF error-body reader (lib/api).
 *
 * C-06 (Run 8 S2-H) CONTRACT CHANGE — the old behaviour (return the backend's raw
 * `detail` / `non_field_errors` / field-error / bare-list / plain-string body first)
 * is INTENTIONALLY replaced: backend strings are English backend copy and must never
 * reach the customer UI (OPS-6b). Now a known backend `code` returns its LOCALIZED
 * message (via the shared API_ERROR_CODE_MESSAGES map); anything unmapped returns
 * the caller's localized `fallback` ("" when none is given) — never the raw string.
 * The base assertions below were updated for that change (G3b A-04 precedent: an
 * expectation pinning old behaviour is updated in the same commit as the fix).
 *
 * Regression kept from before: a serializers.ValidationError raised from a
 * serializer's save() (the password-reset / activation lost-race path: "Token
 * expired or used") reaches the client as a BARE LIST body. It is no longer
 * surfaced verbatim — it falls back — until the backend sends a `code` for the
 * spent/invalid-token cases (see S2-H REPORT.md remainder).
 */
import { describe, it, expect } from "vitest";
import { extractApiErrorMessage, mapApiErrorCode } from "../api";
import { translate } from "../../i18n/translate";

const errWith = (data) => ({ response: { data } });

describe("extractApiErrorMessage", () => {
  it("falls back on a bare-list body (ValidationError raised from save())", () => {
    // C-06: the raw "Token expired or used" string must NOT leak to the customer.
    expect(extractApiErrorMessage(errWith(["Token expired or used"]), "fallback")).toBe("fallback");
  });

  it("falls back on an empty or non-string bare list", () => {
    expect(extractApiErrorMessage(errWith([]), "fallback")).toBe("fallback");
    expect(extractApiErrorMessage(errWith([{ nested: 1 }]), "fallback")).toBe("fallback");
  });

  it("never returns raw detail, non_field_errors, or field errors — only the fallback", () => {
    // C-06: the old precedence (detail, then non_field_errors, then first field
    // list) is gone. Without a known code every shape falls back.
    expect(extractApiErrorMessage(errWith({ detail: "Nope", non_field_errors: ["x"] }), "f")).toBe("f");
    expect(extractApiErrorMessage(errWith({ non_field_errors: ["Invalid token"] }), "f")).toBe("f");
    expect(extractApiErrorMessage(errWith({ password: ["This password is too common."] }), "f")).toBe("f");
  });

  it("returns a plain-string body and falls back with no response at all", () => {
    // C-06: a plain-string body is backend copy too — it falls back now.
    expect(extractApiErrorMessage(errWith("Bad gateway"), "f")).toBe("f");
    expect(extractApiErrorMessage({}, "f")).toBe("f");
    expect(extractApiErrorMessage(undefined, "f")).toBe("f");
  });

  // ── C-06: known code → localized message ──────────────────────────────────
  it("maps a known backend code to its localized message (never the raw detail)", () => {
    const err = errWith({ code: "auth_required", detail: "Delivery orders require a signed-in account." });
    expect(extractApiErrorMessage(err, "fallback")).toBe(translate("apiClient.authRequired"));
    expect(extractApiErrorMessage(err, "fallback")).not.toBe("Delivery orders require a signed-in account.");
  });

  it("maps checkout codes from Cart's mapOrderApiError list", () => {
    expect(extractApiErrorMessage(errWith({ code: "promo_invalid", detail: "x" }), "f")).toBe(
      translate("apiClient.promoInvalid"),
    );
    expect(extractApiErrorMessage(errWith({ code: "wallet_insufficient", detail: "x" }), "f")).toBe(
      translate("apiClient.walletInsufficient"),
    );
    expect(extractApiErrorMessage(errWith({ code: "restaurant_closed", detail: "x" }), "f")).toBe(
      translate("apiClient.restaurantClosed"),
    );
    expect(extractApiErrorMessage(errWith({ code: "items_unavailable", detail: "x", slugs: ["a"] }), "f")).toBe(
      translate("apiClient.itemsUnavailable"),
    );
    expect(extractApiErrorMessage(errWith({ code: "menu_temporarily_disabled", detail: "x", note: "n" }), "f")).toBe(
      translate("apiClient.menuTemporarilyDisabled"),
    );
  });

  it("maps auth/account codes from the account flows", () => {
    expect(extractApiErrorMessage(errWith({ code: "otp_expired", detail: "x" }), "f")).toBe(
      translate("apiClient.otpExpired"),
    );
    expect(extractApiErrorMessage(errWith({ code: "invalid_code", detail: "x" }), "f")).toBe(
      translate("apiClient.invalidCode"),
    );
    expect(extractApiErrorMessage(errWith({ code: "phone_taken", detail: "x" }), "f")).toBe(
      translate("apiClient.phoneTaken"),
    );
    expect(extractApiErrorMessage(errWith({ code: "email_taken", detail: "x" }), "f")).toBe(
      translate("apiClient.emailTaken"),
    );
    expect(extractApiErrorMessage(errWith({ code: "voucher_locked", detail: "x" }), "f")).toBe(
      translate("apiClient.voucherLocked"),
    );
  });

  it("maps the 429 rate-limit shape the api client rewrites", () => {
    expect(extractApiErrorMessage(errWith({ code: "rate_limited" }), "f")).toBe(translate("apiClient.rateLimited"));
  });

  it("maps prefix families (loyalty_*, schedule_*, plan_forbidden*)", () => {
    expect(extractApiErrorMessage(errWith({ code: "loyalty_insufficient_points", detail: "x" }), "f")).toBe(
      translate("apiClient.loyaltyError"),
    );
    expect(extractApiErrorMessage(errWith({ code: "loyalty_below_threshold", detail: "x" }), "f")).toBe(
      translate("apiClient.loyaltyError"),
    );
    expect(extractApiErrorMessage(errWith({ code: "schedule_invalid_time", detail: "x" }), "f")).toBe(
      translate("apiClient.scheduleInvalid"),
    );
    expect(extractApiErrorMessage(errWith({ code: "plan_forbidden_checkout", detail: "x" }), "f")).toBe(
      translate("apiClient.planForbidden"),
    );
  });

  // ── C-06: unmapped code → fallback / "" ────────────────────────────────────
  it("returns the fallback for an unknown code, even when detail is present", () => {
    const err = errWith({ code: "something_new", detail: "Brand new backend wording." });
    expect(extractApiErrorMessage(err, "fallback")).toBe("fallback");
    expect(extractApiErrorMessage(err, "fallback")).not.toBe("Brand new backend wording.");
  });

  it("returns '' for an unknown code with no fallback — never the raw detail", () => {
    const err = errWith({ code: "something_new", detail: "Brand new backend wording." });
    expect(extractApiErrorMessage(err)).toBe("");
    expect(extractApiErrorMessage(errWith({ detail: "No code at all." }))).toBe("");
    expect(extractApiErrorMessage(errWith({ detail: "No code at all." }), "")).toBe("");
  });

  it("returns the fallback for the erasure 409 shape (detail + errors, no code)", () => {
    const err = errWith({ detail: "Account cannot be erased at this time.", errors: ["Open orders exist."] });
    expect(extractApiErrorMessage(err, "blocked")).toBe("blocked");
  });

  // ── mapApiErrorCode ─────────────────────────────────────────────────────────
  it("mapApiErrorCode resolves known codes and prefix families, '' otherwise", () => {
    expect(mapApiErrorCode("auth_required")).toBe("apiClient.authRequired");
    expect(mapApiErrorCode("loyalty_anything")).toBe("apiClient.loyaltyError");
    expect(mapApiErrorCode("schedule_anything")).toBe("apiClient.scheduleInvalid");
    expect(mapApiErrorCode("plan_forbidden_anything")).toBe("apiClient.planForbidden");
    expect(mapApiErrorCode("nope")).toBe("");
    expect(mapApiErrorCode("")).toBe("");
    expect(mapApiErrorCode(undefined)).toBe("");
    expect(mapApiErrorCode(null)).toBe("");
  });
});
