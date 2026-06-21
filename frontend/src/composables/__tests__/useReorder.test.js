/**
 * Unit tests for the useReorder composable — the unified reorder spine.
 *
 * Verifies the orchestration around the cart store's reorderFromOrder action:
 *   - the correct contextual toast fires for each outcome
 *   - fulfillment context is restored (with pickup fallback when delivery is off)
 *   - hydrateServerHistory merges account-bound history into cart.recentOrders
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";

// api is imported directly by the composable AND passed into the cart action.
vi.mock("../../lib/api", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

// Deterministic translator: returns "key|json(params)" so assertions are simple.
vi.mock("../useI18n", () => ({
  useI18n: () => ({
    t: (key, params) => (params ? `${key}|${JSON.stringify(params)}` : key),
  }),
}));

import api from "../../lib/api";
import { useReorder } from "../useReorder";
import { useCartStore } from "../../stores/cart";
import { useToastStore } from "../../stores/toast";

const resolverResponse = (items, extra = {}) => ({
  data: { items, any_unavailable: false, any_options_dropped: false, ...extra },
});

describe("useReorder.reorderFromOrder", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    api.get.mockReset();
    api.post.mockReset();
  });

  it("toasts 'empty' and adds nothing for an order with no items", async () => {
    const toast = useToastStore();
    const { reorderFromOrder } = useReorder();
    const res = await reorderFromOrder({ items: [] });
    expect(res.added).toBe(0);
    expect(toast.message).toBe("reorder.empty");
    expect(api.post).not.toHaveBeenCalled();
  });

  it("adds available lines and toasts success", async () => {
    api.post.mockResolvedValue(resolverResponse([
      { slug: "burger", name: "Burger", available: true, current_price: "10.00", currency: "USD", current_option_ids: [], current_option_ids_valid: true },
    ]));
    const cart = useCartStore();
    const toast = useToastStore();
    const { reorderFromOrder } = useReorder();
    const res = await reorderFromOrder({ items: [{ slug: "burger", name: "Burger", price: 10, qty: 1 }] });
    expect(res.added).toBe(1);
    expect(cart.items).toHaveLength(1);
    expect(toast.message).toBe("reorder.added");
    expect(toast.type).toBe("success");
  });

  it("toasts someUnavailable with the skipped names", async () => {
    api.post.mockResolvedValue(resolverResponse(
      [
        { slug: "burger", name: "Burger", available: true, current_price: "10.00", currency: "USD", current_option_ids: [], current_option_ids_valid: true },
        { slug: "gone", name: "Old Special", available: false, current_price: null },
      ],
      { any_unavailable: true },
    ));
    const toast = useToastStore();
    const { reorderFromOrder } = useReorder();
    await reorderFromOrder({ items: [
      { slug: "burger", name: "Burger", price: 10, qty: 1 },
      { slug: "gone", name: "Old Special", price: 8, qty: 1 },
    ] });
    expect(toast.message).toContain("reorder.someUnavailable");
    expect(toast.message).toContain("Old Special");
    expect(toast.type).toBe("warning");
  });

  it("toasts allUnavailable (error) when nothing could be added", async () => {
    api.post.mockResolvedValue(resolverResponse(
      [{ slug: "gone", name: "Gone", available: false, current_price: null }],
      { any_unavailable: true },
    ));
    const toast = useToastStore();
    const { reorderFromOrder } = useReorder();
    const res = await reorderFromOrder({ items: [{ slug: "gone", name: "Gone", price: 5, qty: 1 }] });
    expect(res.added).toBe(0);
    expect(toast.message).toBe("reorder.allUnavailable");
    expect(toast.type).toBe("error");
  });

  it("restores delivery fulfillment context from the order", async () => {
    api.post.mockResolvedValue(resolverResponse([
      { slug: "burger", name: "Burger", available: true, current_price: "10.00", currency: "USD", current_option_ids: [], current_option_ids_valid: true },
    ]));
    const cart = useCartStore();
    const { reorderFromOrder } = useReorder();
    await reorderFromOrder({
      items: [{ slug: "burger", name: "Burger", price: 10, qty: 1 }],
      fulfillment_type: "delivery",
      delivery_address: "12 Rue Test",
      delivery_lat: 33.5,
      delivery_lng: -7.6,
    });
    const ctx = cart.loadFulfillmentContext();
    expect(ctx.fulfillment_type).toBe("delivery");
    expect(ctx.delivery_address).toBe("12 Rue Test");
    expect(ctx.delivery_lat).toBe(33.5);
  });

  it("falls back to pickup when delivery is no longer offered", async () => {
    api.post.mockResolvedValue(resolverResponse([
      { slug: "burger", name: "Burger", available: true, current_price: "10.00", currency: "USD", current_option_ids: [], current_option_ids_valid: true },
    ]));
    const cart = useCartStore();
    const { reorderFromOrder } = useReorder();
    await reorderFromOrder(
      { items: [{ slug: "burger", name: "Burger", price: 10, qty: 1 }], fulfillment_type: "delivery", delivery_address: "X" },
      { profile: { delivery_enabled: false } },
    );
    expect(cart.loadFulfillmentContext().fulfillment_type).toBe("pickup");
  });
});

describe("useReorder.hydrateServerHistory", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    api.get.mockReset();
    api.post.mockReset();
  });

  it("merges server order history into cart.recentOrders (newest first)", async () => {
    api.get.mockResolvedValue({
      data: {
        orders: [
          { order_number: "B2", total: "20", currency: "USD", created_at: "2026-06-20T10:00:00Z", items: [{ dish_slug: "fries", dish_name: "Fries", unit_price: "4.50", qty: 1, options: [] }] },
          { order_number: "A1", total: "10", currency: "USD", created_at: "2026-06-19T10:00:00Z", items: [{ dish_slug: "burger", dish_name: "Burger", unit_price: "10.00", qty: 1, options: [{ id: 3, name: "Cheese" }] }] },
        ],
      },
    });
    const cart = useCartStore();
    const { hydrateServerHistory } = useReorder();
    const merged = await hydrateServerHistory();
    expect(merged).toBe(2);
    expect(cart.recentOrders[0].order_number).toBe("B2"); // newest at front
    // option ids derived from the options snapshot
    expect(cart.recentOrders[1].items[0].option_ids).toEqual([3]);
  });

  it("returns 0 and stays silent when the history call rejects", async () => {
    api.get.mockRejectedValue(new Error("401"));
    const cart = useCartStore();
    const { hydrateServerHistory } = useReorder();
    const merged = await hydrateServerHistory();
    expect(merged).toBe(0);
    expect(cart.recentOrders).toHaveLength(0);
  });
});
