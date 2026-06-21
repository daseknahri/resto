import { describe, it, expect } from 'vitest';
import { groupWalletTransactionsByDate } from '../walletHistory';

// Fixed reference "now": 2026-06-21T12:00:00 local.
const NOW = new Date(2026, 5, 21, 12, 0, 0);
const t = (k) => (k === 'today' ? 'Today' : 'Yesterday');
const formatMonth = (d) => `M${d.getMonth()}-${d.getFullYear()}`;
const group = (txs) => groupWalletTransactionsByDate(txs, { t, formatMonth, now: NOW });

const at = (y, m, day, h = 9) => new Date(y, m, day, h, 0, 0).toISOString();

describe('groupWalletTransactionsByDate', () => {
  it('returns an empty array for an empty / missing list', () => {
    expect(group([])).toEqual([]);
    expect(groupWalletTransactionsByDate(undefined, { t, formatMonth, now: NOW })).toEqual([]);
  });

  it('buckets today and yesterday with relative labels', () => {
    const groups = group([
      { id: 1, created_at: at(2026, 5, 21) },
      { id: 2, created_at: at(2026, 5, 20) },
    ]);
    expect(groups.map((g) => g.key)).toEqual(['today', 'yesterday']);
    expect(groups[0].label).toBe('Today');
    expect(groups[1].label).toBe('Yesterday');
  });

  it('buckets older rows by year-month with a formatted label', () => {
    const groups = group([{ id: 9, created_at: at(2026, 4, 3) }]);
    expect(groups).toHaveLength(1);
    expect(groups[0].key).toBe('2026-4');
    expect(groups[0].label).toBe('M4-2026');
  });

  it('merges multiple rows in the same bucket and preserves input order', () => {
    const groups = group([
      { id: 1, created_at: at(2026, 5, 21, 10) },
      { id: 2, created_at: at(2026, 5, 21, 8) },
      { id: 3, created_at: at(2026, 4, 1) },
    ]);
    expect(groups).toHaveLength(2);
    expect(groups[0].key).toBe('today');
    expect(groups[0].items.map((x) => x.id)).toEqual([1, 2]);
    expect(groups[1].key).toBe('2026-4');
  });

  it('separates same-month-different-year into distinct buckets', () => {
    const groups = group([
      { id: 1, created_at: at(2026, 2, 5) },
      { id: 2, created_at: at(2025, 2, 5) },
    ]);
    expect(groups.map((g) => g.key)).toEqual(['2026-2', '2025-2']);
  });

  it('puts rows with a missing / invalid date in an unknown bucket', () => {
    const groups = group([
      { id: 1, created_at: null },
      { id: 2 },
      { id: 3, created_at: 'not-a-date' },
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].key).toBe('unknown');
    expect(groups[0].label).toBe('—');
    expect(groups[0].items.map((x) => x.id)).toEqual([1, 2, 3]);
  });

  it('falls back to literal keys when no label resolvers are supplied', () => {
    const groups = groupWalletTransactionsByDate(
      [{ id: 1, created_at: at(2026, 5, 21) }],
      { now: NOW },
    );
    expect(groups[0].label).toBe('today');
  });
});
