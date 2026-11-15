/**
 * Unit tests for lib/onboardingApi.js dishApi.upsert — Rostoy Run 8, Surface 1,
 * cluster S1-G (gap A3-03), CORRECTED at the S1 full-FE-gate (2026-11-15).
 *
 * WHY: the A3-03 fix lives in the upsert payload (the payload the component
 * sends), which the StepDishes mount test cannot see — onboardingApi is mocked
 * there. These tests import the REAL dishApi with lib/api mocked and assert the
 * exact payload.
 *
 * CORRECTION: the first version of this file asserted is_available is ALWAYS
 * sent (including `false` on every re-save). That broke the pre-existing
 * contract in src/lib/__tests__/onboardingApi.test.js: a re-save with stock
 * untouched, a stock change to null (unlimited), and a stock change to 0 must
 * NOT send is_available. is_available now follows the SAME "only when changed"
 * discipline as stock_qty: sent on create (default true), or on update when it
 * differs from the known baselineIsAvailable; an unknown baseline on an update
 * never sends it (fail safe). The restock rule (a restock re-enables a sold-out
 * dish) is preserved and still wins over the baseline rule.
 *
 * Destination in repo: frontend/src/onboarding/__tests__/onboardingApi.upsert.test.js
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// lib/api is the only boundary dishApi.upsert touches (plus the pure slugify,
// translate and staleCache helpers, which load for real).
const apiPutMock = vi.hoisted(() => vi.fn());
const apiPostMock = vi.hoisted(() => vi.fn());
vi.mock("../../lib/api", () => ({
  extractApiErrorMessage: (err, fallback = "") => fallback,
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: apiPostMock,
    put: apiPutMock,
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import { dishApi } from "../../lib/onboardingApi";

describe("dishApi.upsert — A3-03 availability payload", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    apiPutMock.mockResolvedValue({ data: { id: 7, slug: "soup", is_available: false } });
    apiPostMock.mockResolvedValue({ data: { id: 99, slug: "soup" } });
  });

  it("sends is_available:false on update when the owner changed it (mark unavailable persists)", async () => {
    await dishApi.upsert(
      { id: 7, category: 1, name: "Soup", price: 10, stock_qty: 5, is_available: false },
      { baselineStockQty: 5, baselineIsAvailable: true }
    );
    expect(apiPutMock).toHaveBeenCalledTimes(1);
    expect(apiPutMock.mock.calls[0][1].is_available).toBe(false);
  });

  it("does NOT send is_available on update when unchanged vs baseline", async () => {
    await dishApi.upsert(
      { id: 7, category: 1, name: "Soup", price: 10, stock_qty: 5, is_available: true },
      { baselineStockQty: 5, baselineIsAvailable: true }
    );
    expect(apiPutMock).toHaveBeenCalledTimes(1);
    expect("is_available" in apiPutMock.mock.calls[0][1]).toBe(false);
  });

  it("does NOT send is_available on update with unknown baseline (fail safe)", async () => {
    await dishApi.upsert(
      { id: 7, category: 1, name: "Soup", price: 10, stock_qty: 5, is_available: false },
      { baselineStockQty: 5 }
    );
    expect(apiPutMock).toHaveBeenCalledTimes(1);
    expect("is_available" in apiPutMock.mock.calls[0][1]).toBe(false);
  });

  it("restock still re-enables a sold-out dish (existing rule preserved)", async () => {
    await dishApi.upsert(
      { id: 7, category: 1, name: "Soup", price: 10, stock_qty: 5, is_available: false },
      { baselineStockQty: 0, baselineIsAvailable: false }
    );
    const payload = apiPutMock.mock.calls[0][1];
    expect(payload.stock_qty).toBe(5);
    expect(payload.is_available).toBe(true);
  });

  it("sends is_available:false on create", async () => {
    await dishApi.upsert({ category: 1, name: "Soup", price: 10, is_available: false });
    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(apiPostMock.mock.calls[0][1].is_available).toBe(false);
  });

  it("sends is_available:true on create when the dish carries no explicit value", async () => {
    await dishApi.upsert({ category: 1, name: "Soup", price: 10 });
    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(apiPostMock.mock.calls[0][1].is_available).toBe(true);
  });
});
