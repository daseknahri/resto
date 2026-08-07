import { describe, it, expect } from 'vitest';
import { resolveMarketplaceReorderItems } from '../reorder';

const mapOf = (dishes) => new Map(dishes.map((d) => [d.slug, d]));

describe('resolveMarketplaceReorderItems', () => {
  it('drops a sold-out dish (is_available === false) instead of seeding it', () => {
    // Regression: a seeded sold-out dish would block checkout via the unavailableSlugs
    // guard until removed by hand — reorder must drop it, like the tenant spine does.
    const dishMap = mapOf([{ slug: 'taco', name: 'Taco', price: 10, is_available: false }]);
    const { cart, dropped } = resolveMarketplaceReorderItems([{ slug: 'taco', price: 10, qty: 2 }], dishMap);
    expect(cart).toEqual([]);
    expect(dropped).toBe(true);
  });

  it('drops a dish no longer on the menu', () => {
    const { cart, dropped } = resolveMarketplaceReorderItems([{ slug: 'gone', price: 5, qty: 1 }], mapOf([]));
    expect(cart).toEqual([]);
    expect(dropped).toBe(true);
  });

  it('keeps an available dish and re-prices it to the live price', () => {
    const dishMap = mapOf([{ slug: 'taco', name: 'Taco', price: 12, is_available: true }]);
    const { cart, priceChanged, dropped } = resolveMarketplaceReorderItems(
      [{ slug: 'taco', price: 10, qty: 3 }],
      dishMap,
    );
    expect(dropped).toBe(false);
    expect(priceChanged).toBe(true); // 10 → 12
    expect(cart).toEqual([{ slug: 'taco', name: 'Taco', price: 12, unitPrice: 12, qty: 3, options: [] }]);
  });

  it('treats an absent is_available as available (only strict false drops)', () => {
    const dishMap = mapOf([{ slug: 'taco', name: 'Taco', price: 10 }]);
    const { cart, dropped } = resolveMarketplaceReorderItems([{ slug: 'taco', price: 10, qty: 1 }], dishMap);
    expect(dropped).toBe(false);
    expect(cart).toHaveLength(1);
  });

  it('flags neither priceChanged nor dropped for an unchanged available reorder', () => {
    const dishMap = mapOf([{ slug: 'taco', name: 'Taco', price: 10, is_available: true }]);
    const { priceChanged, dropped } = resolveMarketplaceReorderItems(
      [{ slug: 'taco', price: 10, qty: 1 }],
      dishMap,
    );
    expect(priceChanged).toBe(false);
    expect(dropped).toBe(false);
  });

  it('clamps qty to a positive integer and skips items with no slug', () => {
    const dishMap = mapOf([{ slug: 'taco', name: 'Taco', price: 10, is_available: true }]);
    const { cart } = resolveMarketplaceReorderItems(
      [{ slug: 'taco', price: 10, qty: 0 }, { price: 10, qty: 2 }],
      dishMap,
    );
    expect(cart).toHaveLength(1);
    expect(cart[0].qty).toBe(1); // qty 0 → clamped to 1
  });

  it('returns empty for non-array input or a missing dishMap', () => {
    expect(resolveMarketplaceReorderItems(null, mapOf([]))).toEqual({ cart: [], priceChanged: false, dropped: false });
    expect(resolveMarketplaceReorderItems([{ slug: 'x' }], null)).toEqual({ cart: [], priceChanged: false, dropped: false });
  });
});
