import { describe, it, expect } from 'vitest';
import { recentRecipients, recentDropoffs } from '../recentRecipients';

// Rows mirror /api/rides/history/ shape (kind + recipient_* + dropoff_*).
const row = (over = {}) => ({
  kind: 'package',
  recipient_name: '',
  recipient_phone: '',
  dropoff_address: '',
  dropoff_lat: null,
  dropoff_lng: null,
  ...over,
});

describe('recentRecipients', () => {
  it('returns [] for non-array / empty input', () => {
    expect(recentRecipients(null)).toEqual([]);
    expect(recentRecipients(undefined)).toEqual([]);
    expect(recentRecipients([])).toEqual([]);
  });

  it('ignores non-package rows (rides)', () => {
    const hist = [
      row({ kind: 'ride', recipient_name: 'Ghost', recipient_phone: '+212600000000' }),
    ];
    expect(recentRecipients(hist)).toEqual([]);
  });

  it('skips rows with neither name nor phone', () => {
    expect(recentRecipients([row({}), row({ recipient_name: '   ' })])).toEqual([]);
  });

  it('returns newest-first distinct recipients (deduped by phone digits)', () => {
    const hist = [
      row({ recipient_name: 'Amine', recipient_phone: '+212 600-111-222' }),
      // Same digits, different formatting → deduped.
      row({ recipient_name: 'Amine (dup)', recipient_phone: '212600111222' }),
      row({ recipient_name: 'Sara', recipient_phone: '+212600333444' }),
    ];
    const out = recentRecipients(hist);
    // First Amine kept; same digits => second dropped; Sara kept.
    expect(out).toEqual([
      { name: 'Amine', phone: '+212 600-111-222' },
      { name: 'Sara', phone: '+212600333444' },
    ]);
  });

  it('dedupes by lowercased name when phone is absent', () => {
    const hist = [
      row({ recipient_name: 'Yasmine' }),
      row({ recipient_name: 'yasmine' }),
      row({ recipient_name: 'Omar' }),
    ];
    expect(recentRecipients(hist)).toEqual([
      { name: 'Yasmine', phone: '' },
      { name: 'Omar', phone: '' },
    ]);
  });

  it('honours the limit (default 4)', () => {
    const hist = Array.from({ length: 9 }, (_, i) =>
      row({ recipient_name: `R${i}`, recipient_phone: `+21260000000${i}` }),
    );
    expect(recentRecipients(hist)).toHaveLength(4);
    expect(recentRecipients(hist, 2)).toHaveLength(2);
  });
});

describe('recentDropoffs', () => {
  it('returns [] for non-array input', () => {
    expect(recentDropoffs(null)).toEqual([]);
  });

  it('returns newest-first distinct drop-off addresses with coords', () => {
    const hist = [
      row({ dropoff_address: '12 Rue A', dropoff_lat: 33.5, dropoff_lng: -7.6 }),
      row({ dropoff_address: '12 rue a', dropoff_lat: 33.5, dropoff_lng: -7.6 }), // dup (case)
      row({ dropoff_address: '99 Bd B', dropoff_lat: 34.0, dropoff_lng: -6.8 }),
    ];
    expect(recentDropoffs(hist)).toEqual([
      { address: '12 Rue A', lat: 33.5, lng: -7.6 },
      { address: '99 Bd B', lat: 34.0, lng: -6.8 },
    ]);
  });

  it('nulls out non-finite coords', () => {
    const hist = [row({ dropoff_address: 'No coords', dropoff_lat: null, dropoff_lng: null })];
    expect(recentDropoffs(hist)).toEqual([{ address: 'No coords', lat: null, lng: null }]);
  });

  it('skips package rows without a drop-off address and ignores rides', () => {
    const hist = [
      row({ dropoff_address: '' }),
      row({ kind: 'ride', dropoff_address: 'Ride dest' }),
      row({ dropoff_address: 'Real' }),
    ];
    expect(recentDropoffs(hist)).toEqual([{ address: 'Real', lat: null, lng: null }]);
  });

  it('honours the limit (default 3)', () => {
    const hist = Array.from({ length: 6 }, (_, i) => row({ dropoff_address: `Addr ${i}` }));
    expect(recentDropoffs(hist)).toHaveLength(3);
    expect(recentDropoffs(hist, 1)).toHaveLength(1);
  });
});
