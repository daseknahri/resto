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
    expect(cart).toEqual([{
      slug: 'taco', name: 'Taco', price: 12, unitPrice: 12, qty: 3,
      options: [], note: '', happy_hour_ends_at: null, happy_hour_starts_at: null,
    }]);
  });

  it('preserves selected options + note and re-prices with the live option deltas', () => {
    // Regression: marketplace reorder used to seed options:[] at the base price, so a
    // required-option dish hard-failed checkout and paid extras were silently dropped.
    const dishMap = mapOf([{
      slug: 'pizza', name: 'Pizza', price: 50, is_available: true,
      option_groups: [
        { id: 1, options: [{ id: 11, name: 'Large', price_delta: 10 }, { id: 12, name: 'Small', price_delta: 0 }] },
        { id: 2, options: [{ id: 21, name: 'Extra cheese', price_delta: 8 }] },
      ],
    }]);
    const { cart, priceChanged, dropped } = resolveMarketplaceReorderItems(
      [{
        slug: 'pizza', price: 68, qty: 2, note: 'no onions',
        options: [
          { id: 11, name: 'Large', price_delta: '10' },
          { id: 21, name: 'Extra cheese', price_delta: '8' },
        ],
      }],
      dishMap,
    );
    expect(dropped).toBe(false);
    expect(priceChanged).toBe(false); // snapshot unit 68 === recomputed 50 + 10 + 8
    expect(cart).toHaveLength(1);
    expect(cart[0].options).toEqual([
      { id: 11, name: 'Large', price_delta: 10 },
      { id: 21, name: 'Extra cheese', price_delta: 8 },
    ]);
    expect(cart[0].note).toBe('no onions');
    expect(cart[0].unitPrice).toBe(68);
    expect(cart[0].qty).toBe(2);
  });

  it('drops a stale option no longer on the live dish and flags the change', () => {
    const dishMap = mapOf([{
      slug: 'pizza', name: 'Pizza', price: 50, is_available: true,
      option_groups: [{ id: 1, options: [{ id: 11, name: 'Large', price_delta: 10 }] }],
    }]);
    const { cart, priceChanged } = resolveMarketplaceReorderItems(
      [{
        slug: 'pizza', price: 68, qty: 1,
        options: [
          { id: 11, name: 'Large', price_delta: '10' },
          { id: 99, name: 'Gone', price_delta: '8' }, // no longer on the menu
        ],
      }],
      dishMap,
    );
    expect(cart[0].options).toEqual([{ id: 11, name: 'Large', price_delta: 10 }]);
    expect(cart[0].unitPrice).toBe(60); // 50 + 10 (stale +8 dropped)
    expect(priceChanged).toBe(true);
  });

  it('re-prices kept options using the live price_delta, not the snapshot delta', () => {
    const dishMap = mapOf([{
      slug: 'pizza', name: 'Pizza', price: 50, is_available: true,
      option_groups: [{ id: 1, options: [{ id: 11, name: 'Large', price_delta: 15 }] }], // was 10
    }]);
    const { cart, priceChanged } = resolveMarketplaceReorderItems(
      [{ slug: 'pizza', price: 60, qty: 1, options: [{ id: 11, name: 'Large', price_delta: '10' }] }],
      dishMap,
    );
    expect(cart[0].options[0].price_delta).toBe(15);
    expect(cart[0].unitPrice).toBe(65); // 50 + 15
    expect(priceChanged).toBe(true); // 60 → 65
  });

  it('uses the happy-hour effective base when the dish is on happy hour', () => {
    const dishMap = mapOf([{
      slug: 'burger', name: 'Burger', price: 40, effective_price: 30,
      happy_hour: { ends_at: '20:00', starts_at: '17:00' }, is_available: true,
    }]);
    const { cart } = resolveMarketplaceReorderItems([{ slug: 'burger', price: 40, qty: 1 }], dishMap);
    expect(cart[0].unitPrice).toBe(30);
    expect(cart[0].happy_hour_ends_at).toBe('20:00');
    expect(cart[0].happy_hour_starts_at).toBe('17:00');
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
