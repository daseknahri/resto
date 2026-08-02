import { describe, it, expect } from "vitest";
import { ratingErrorKey } from "../useOrderRating";

const errWith = (code) => ({ response: { data: { code } } });

describe("ratingErrorKey", () => {
  it("maps each known rejection code to its distinct key suffix", () => {
    expect(ratingErrorKey(errWith("already_rated"))).toBe("rateErrorAlreadyRated");
    expect(ratingErrorKey(errWith("order_not_completed"))).toBe("rateErrorNotCompleted");
    expect(ratingErrorKey(errWith("not_order_owner"))).toBe("rateErrorNotOwner");
    expect(ratingErrorKey(errWith("invalid_score"))).toBe("rateErrorInvalidScore");
  });

  it("falls back to the generic key for unknown / missing codes", () => {
    expect(ratingErrorKey(errWith("something_else"))).toBe("rateError");
    expect(ratingErrorKey({})).toBe("rateError");
    expect(ratingErrorKey(undefined)).toBe("rateError");
    expect(ratingErrorKey(null)).toBe("rateError");
  });
});
