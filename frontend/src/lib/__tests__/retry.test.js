/**
 * Unit tests for the API client's transient-failure retry policy.
 * Verifies what is (and crucially, is NOT) eligible for automatic retry.
 */
import { describe, it, expect } from "vitest";
import {
  MAX_RETRIES,
  isIdempotentMethod,
  isRetriableError,
  shouldRetry,
  retryBackoffMs,
} from "../retry";

const err = ({ method = "get", status, code } = {}) => ({
  config: method === null ? undefined : { method },
  code,
  response: status === undefined ? undefined : { status },
});

describe("isIdempotentMethod", () => {
  it("treats GET/HEAD/OPTIONS as idempotent", () => {
    ["get", "GET", "head", "options"].forEach((m) => expect(isIdempotentMethod(m)).toBe(true));
  });
  it("treats mutations as non-idempotent", () => {
    ["post", "put", "patch", "delete"].forEach((m) => expect(isIdempotentMethod(m)).toBe(false));
  });
  it("defaults missing method to GET (idempotent)", () => {
    expect(isIdempotentMethod(undefined)).toBe(true);
  });
});

describe("isRetriableError", () => {
  it("retries network-level failures (no response)", () => {
    expect(isRetriableError(err({}))).toBe(true);
  });
  it("retries 5xx", () => {
    [500, 502, 503, 504].forEach((s) => expect(isRetriableError(err({ status: s }))).toBe(true));
  });
  it("does NOT retry 4xx (incl. 401/403/404/422/429)", () => {
    [400, 401, 403, 404, 422, 429].forEach((s) => expect(isRetriableError(err({ status: s }))).toBe(false));
  });
  it("does NOT retry timeouts or cancellations", () => {
    expect(isRetriableError(err({ code: "ECONNABORTED" }))).toBe(false);
    expect(isRetriableError(err({ code: "ERR_CANCELED" }))).toBe(false);
  });
});

describe("shouldRetry", () => {
  it("retries a transient GET below the cap", () => {
    expect(shouldRetry(err({ method: "get", status: 503 }), 0)).toBe(true);
    expect(shouldRetry(err({ method: "get" }), 1)).toBe(true);
  });
  it("never retries mutations even on transient errors", () => {
    expect(shouldRetry(err({ method: "post", status: 503 }), 0)).toBe(false);
    expect(shouldRetry(err({ method: "delete" }), 0)).toBe(false);
  });
  it("stops once the retry cap is reached", () => {
    expect(shouldRetry(err({ method: "get", status: 503 }), MAX_RETRIES)).toBe(false);
  });
  it("does not retry when there is no request config", () => {
    expect(shouldRetry(err({ method: null, status: 503 }), 0)).toBe(false);
  });
});

describe("retryBackoffMs", () => {
  it("grows exponentially from 300ms", () => {
    expect(retryBackoffMs(0)).toBe(300);
    expect(retryBackoffMs(1)).toBe(600);
    expect(retryBackoffMs(2)).toBe(1200);
  });
  it("adds jitter", () => {
    expect(retryBackoffMs(0, 150)).toBe(450);
  });
});
