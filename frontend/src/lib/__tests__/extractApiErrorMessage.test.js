/**
 * extractApiErrorMessage — the shared DRF error-body reader (lib/api).
 *
 * Regression: a serializers.ValidationError raised from a serializer's save()
 * (the password-reset / activation lost-race path: "Token expired or used") reaches
 * the client as a BARE LIST body. The extractor ignored that shape and returned the
 * caller's generic fallback, so the customer never learned the link was spent.
 */
import { describe, it, expect } from "vitest";
import { extractApiErrorMessage } from "../api";

const errWith = (data) => ({ response: { data } });

describe("extractApiErrorMessage", () => {
  it("reads a bare-list body (ValidationError raised from save())", () => {
    expect(extractApiErrorMessage(errWith(["Token expired or used"]), "fallback")).toBe("Token expired or used");
  });

  it("falls back on an empty or non-string bare list", () => {
    expect(extractApiErrorMessage(errWith([]), "fallback")).toBe("fallback");
    expect(extractApiErrorMessage(errWith([{ nested: 1 }]), "fallback")).toBe("fallback");
  });

  it("keeps the existing precedence: detail, non_field_errors, then the first field list", () => {
    expect(extractApiErrorMessage(errWith({ detail: "Nope", non_field_errors: ["x"] }), "f")).toBe("Nope");
    expect(extractApiErrorMessage(errWith({ non_field_errors: ["Invalid token"] }), "f")).toBe("Invalid token");
    expect(extractApiErrorMessage(errWith({ password: ["This password is too common."] }), "f")).toBe(
      "This password is too common.",
    );
  });

  it("returns a plain-string body and falls back with no response at all", () => {
    expect(extractApiErrorMessage(errWith("Bad gateway"), "f")).toBe("Bad gateway");
    expect(extractApiErrorMessage({}, "f")).toBe("f");
    expect(extractApiErrorMessage(undefined, "f")).toBe("f");
  });
});
