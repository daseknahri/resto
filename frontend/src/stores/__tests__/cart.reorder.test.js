/**
 * Unit tests for the cart store's availability-safe `reorderFromOrder` action.
 *
 * The action posts past order lines to /reorder-resolve/ and adds ONLY the
 * still-available lines at their current price, dropping stale options. A mocked
 * api client stands in for the resolver so we can drive each branch.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useCartStore } from "../cart";

const makeApi = (resolveData) => ({
  post: vi.fn(async () => ({ data: resolveData })),
});

describe("cart.reorderFromOrder — availability-safe", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it("adds available lines at the server's current price", async () => {
    const cart = useCartStore();
    const api = makeApi({
      items: [
        { slug: "burger", name: "Burger", available: true, current_price: "12.50", currency: "USD", current_option_ids: [], current_option_ids_valid: true },
      ],
      any_unavailable: false,
      any_options_dropped: false,
    });
    const res = await cart.reorderFromOrder(
      [{ slug: "burger", name: "Burger", price: 10, qty: 2, option_ids: [] }],
      api,
    );
    expect(res.ok).toBe(true);
    expect(res.added).toBe(1);
    expect(res.skipped).toEqual([]);
    expect(cart.items).toHaveLength(1);
    expect(cart.items[0].price).toBe(12.5); // refreshed to current price, not snapshot 10
    expect(cart.items[0].qty).toBe(2);
  });

  it("skips unavailable lines and reports their names", async () => {
    const cart = useCartStore();
    const api = makeApi({
      items: [
        { slug: "burger", name: "Burger", available: true, current_price: "10.00", currency: "USD", current_option_ids: [], current_option_ids_valid: true },
        { slug: "gone", name: "Old Special", available: false, current_price: null },
      ],
      any_unavailable: true,
      any_options_dropped: false,
    });
    const res = await cart.reorderFromOrder(
      [
        { slug: "burger", name: "Burger", price: 10, qty: 1 },
        { slug: "gone", name: "Old Special", price: 8, qty: 1 },
      ],
      api,
    );
    expect(res.added).toBe(1);
    expect(res.skipped).toEqual(["Old Special"]);
    expect(cart.items).toHaveLength(1);
    expect(cart.items[0].slug).toBe("burger");
  });

  it("drops stale options and uses only the server-validated option ids", async () => {
    const cart = useCartStore();
    const api = makeApi({
      items: [
        { slug: "burger", name: "Burger", available: true, current_price: "12.00", currency: "USD", current_option_ids: [1], current_option_ids_valid: false },
      ],
      any_unavailable: false,
      any_options_dropped: true,
    });
    const res = await cart.reorderFromOrder(
      [{ slug: "burger", name: "Burger", price: 12, qty: 1, option_ids: [1, 99] }],
      api,
    );
    expect(res.added).toBe(1);
    expect(res.priceChanged).toBe(true); // options dropped => flagged for the toast
    expect(cart.items[0].option_ids).toEqual([1]); // stale 99 removed
  });

  it("derives option_ids from an options[] snapshot when option_ids is absent", async () => {
    const cart = useCartStore();
    const api = makeApi({
      items: [
        { slug: "burger", name: "Burger", available: true, current_price: "12.00", currency: "USD", current_option_ids: [5], current_option_ids_valid: true },
      ],
      any_unavailable: false,
      any_options_dropped: false,
    });
    await cart.reorderFromOrder(
      [{ dish_slug: "burger", dish_name: "Burger", unit_price: "12.00", qty: 1, options: [{ id: 5, name: "Cheese" }] }],
      api,
    );
    // The request payload carries the derived option id.
    expect(api.post).toHaveBeenCalledWith("/reorder-resolve/", {
      items: [{ slug: "burger", option_ids: [5] }],
    });
    expect(cart.items[0].option_ids).toEqual([5]);
  });

  it("flags a price change when current price differs from the snapshot", async () => {
    const cart = useCartStore();
    const api = makeApi({
      items: [
        { slug: "burger", name: "Burger", available: true, current_price: "15.00", currency: "USD", current_option_ids: [], current_option_ids_valid: true },
      ],
      any_unavailable: false,
      any_options_dropped: false,
    });
    const res = await cart.reorderFromOrder(
      [{ slug: "burger", name: "Burger", price: 10, qty: 1 }],
      api,
    );
    expect(res.priceChanged).toBe(true);
    expect(cart.items[0].price).toBe(15);
  });

  it("fails safe (adds nothing) when the resolver call rejects", async () => {
    const cart = useCartStore();
    const api = { post: vi.fn(async () => { throw new Error("network"); }) };
    const res = await cart.reorderFromOrder(
      [{ slug: "burger", name: "Burger", price: 10, qty: 1 }],
      api,
    );
    expect(res.ok).toBe(false);
    expect(res.added).toBe(0);
    expect(cart.items).toHaveLength(0);
  });

  it("returns early for an empty order", async () => {
    const cart = useCartStore();
    const api = makeApi({ items: [] });
    const res = await cart.reorderFromOrder([], api);
    expect(res.ok).toBe(true);
    expect(res.added).toBe(0);
    expect(api.post).not.toHaveBeenCalled();
  });
});
