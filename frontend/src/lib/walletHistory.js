/**
 * Wallet history helpers — pure logic for the CustomerAccount wallet tab.
 *
 * Kept out of the SFC so the date-bucketing can be unit-tested in isolation.
 * The transaction list is assumed newest-first (the API returns it ordered by
 * -created_at), and that ordering is preserved within and across buckets.
 */

/**
 * Group a newest-first wallet transaction list into dated buckets:
 * Today / Yesterday / one bucket per (year, month) for older rows.
 *
 * @param {Array<{id:*, created_at?:string}>} transactions newest-first list
 * @param {Object} opts
 * @param {(key:'today'|'yesterday') => string} opts.t resolves the relative-day label
 * @param {(date:Date) => string} opts.formatMonth resolves an older-bucket label (e.g. "May 2026")
 * @param {Date} [opts.now] reference "now" (defaults to new Date()) — injectable for tests
 * @returns {Array<{key:string, label:string, items:Array}>} buckets in list order
 */
export function groupWalletTransactionsByDate(transactions, { t, formatMonth, now } = {}) {
  const ref = now instanceof Date ? now : new Date();
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const todayStart = startOfDay(ref);
  const yesterdayStart = todayStart - 86400000;

  const groups = [];
  const byKey = new Map();

  for (const tx of transactions || []) {
    const d = tx && tx.created_at ? new Date(tx.created_at) : null;
    let key;
    let label;
    if (d && !Number.isNaN(d.getTime())) {
      const ds = startOfDay(d);
      if (ds === todayStart) {
        key = 'today';
        label = t ? t('today') : 'today';
      } else if (ds === yesterdayStart) {
        key = 'yesterday';
        label = t ? t('yesterday') : 'yesterday';
      } else {
        key = `${d.getFullYear()}-${d.getMonth()}`;
        label = formatMonth ? formatMonth(d) : key;
      }
    } else {
      key = 'unknown';
      label = '—';
    }

    let group = byKey.get(key);
    if (!group) {
      group = { key, label, items: [] };
      byKey.set(key, group);
      groups.push(group);
    }
    group.items.push(tx);
  }

  return groups;
}
