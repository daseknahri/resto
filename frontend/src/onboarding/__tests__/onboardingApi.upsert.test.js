/**
 * Unit tests for lib/onboardingApi.js dishApi.upsert — Rostoy Run 8, Surface 1,
 * cluster S1-G (gap A3-03).
 *
 * WHY: the A3-03 fix lives in the upsert whitelist (the payload the component
 * sends), which the StepDishes mount test cannot see — onboardingApi is mocked
 * there. These tests import the REAL dishApi with lib/api mocked and assert the
 * exact payload: is_available is always sent (including `false`), and the
 * pre-existing restock rule (a restock re-enables a sold-out dish) is preserved.
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

  it("sends is_available:false on update (mark unavailable persists)", async () => {
    await dishApi.upsert(
      { id: 7, category: 1, name: "Soup", price: 10, stock_qty: 5, is_available: false },
      { baselineStockQty: 5 }
    );
    expect(apiPutMock).toHaveBeenCalledTimes(1);
    expect(apiPutMock.mock.calls[0][1].is_available).toBe(false);
  });

  it("sends is_available:true when the dish carries no explicit value", async () => {
    await dishApi.upsert(
      { id: 7, category: 1, name: "Soup", price: 10, stock_qty: 5 },
      { baselineStockQty: 5 }
    );
    expect(apiPutMock.mock.calls[0][1].is_available).toBe(true);
  });

  it("restock still re-enables a sold-out dish (existing rule preserved)", async () => {
    await dishApi.upsert(
      { id: 7, category: 1, name: "Soup", price: 10, stock_qty: 5, is_available: false },
      { baselineStockQty: 0 }
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
});
