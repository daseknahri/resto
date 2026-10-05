import { describe, it, expect } from 'vitest';
import {
  ROAD_FACTOR,
  AVG_SPEED_KMH,
  deliveryCardPricing,
  haversineKm,
  validCoord,
  parseCoordinateValue,
  parseCoordinatesFromMapUrl,
} from '../deliveryPricing';

// M12: a marketplace card said "Free delivery" whenever the FLAT fee was 0 — including for a
// base + per-km restaurant that then charged at checkout (tenancy/delivery_pricing).
describe('deliveryCardPricing', () => {
  it('is distance-priced whenever per-km is set, quoting the base as the floor', () => {
    expect(deliveryCardPricing({ delivery_fee: '0', delivery_base_fee: '8.00', delivery_per_km: '2.50', delivery_free_over: '0' }))
      .toEqual({ kind: 'distance', from: 8, freeOver: 0 });
    // No base → nothing worth quoting as "from".
    expect(deliveryCardPricing({ delivery_fee: '0', delivery_base_fee: '0', delivery_per_km: '3', delivery_free_over: '150' }))
      .toEqual({ kind: 'distance', from: 0, freeOver: 150 });
  });

  it('is the flat fee when there is no per-km pricing', () => {
    expect(deliveryCardPricing({ delivery_fee: '15.00', delivery_base_fee: '0', delivery_per_km: '0', delivery_free_over: '100' }))
      .toEqual({ kind: 'flat', fee: 15, freeOver: 100 });
  });

  it('is free only when nothing is ever charged (a base alone is not charged without per-km)', () => {
    expect(deliveryCardPricing({ delivery_fee: '0', delivery_base_fee: '0', delivery_per_km: '0', delivery_free_over: '0' }).kind).toBe('free');
    expect(deliveryCardPricing({ delivery_fee: '0', delivery_base_fee: '5', delivery_per_km: '0', delivery_free_over: '50' }))
      .toEqual({ kind: 'free', freeOver: 0 });
  });

  it('keeps the old flat-only reading for a row without the pricing keys', () => {
    expect(deliveryCardPricing({ delivery_fee: '12.00' }).kind).toBe('flat');
    expect(deliveryCardPricing({ delivery_fee: '0' }).kind).toBe('free');
  });
});

describe('deliveryPricing primitives', () => {
  it('exposes the backend-matching constants', () => {
    expect(ROAD_FACTOR).toBe(1.3);
    expect(AVG_SPEED_KMH).toBe(22);
  });

  describe('haversineKm', () => {
    it('returns 0 for the same point', () => {
      expect(haversineKm(33.57, -7.59, 33.57, -7.59)).toBe(0);
    });

    it('computes a known distance (Casablanca → Rabat ≈ 86 km)', () => {
      const d = haversineKm(33.5731, -7.5898, 34.0209, -6.8416);
      expect(d).toBeGreaterThan(80);
      expect(d).toBeLessThan(92);
    });

    it('returns null for non-finite / missing coordinates', () => {
      expect(haversineKm(null, null, 1, 1)).toBeNull();
      expect(haversineKm('', '', '', '')).toBeNull();
      expect(haversineKm(33.5, -7.5, undefined, 2)).toBeNull();
    });

    it('coerces numeric strings', () => {
      expect(haversineKm('33.57', '-7.59', '33.57', '-7.59')).toBe(0);
    });
  });

  describe('validCoord', () => {
    it('accepts a real coordinate', () => {
      expect(validCoord(33.57, -7.59)).toBe(true);
      expect(validCoord('33.57', '-7.59')).toBe(true);
    });

    it('rejects the null island (0,0)', () => {
      expect(validCoord(0, 0)).toBe(false);
    });

    it('rejects out-of-range values', () => {
      expect(validCoord(999, -7.59)).toBe(false);
      expect(validCoord(33.57, 999)).toBe(false);
      expect(validCoord(-91, 0.5)).toBe(false);
    });

    it('rejects non-finite / missing values', () => {
      expect(validCoord(null, null)).toBe(false);
      expect(validCoord(undefined, 2)).toBe(false);
      expect(validCoord('abc', 2)).toBe(false);
    });

    it('accepts a valid coordinate with one zero component (not null island)', () => {
      expect(validCoord(33.57, 0)).toBe(true);
    });
  });

  describe('parseCoordinateValue', () => {
    it('returns null for blank / nullish input (an emptied manual field)', () => {
      expect(parseCoordinateValue(null)).toBeNull();
      expect(parseCoordinateValue(undefined)).toBeNull();
      expect(parseCoordinateValue('')).toBeNull();
      expect(parseCoordinateValue('   ')).toBeNull();
    });

    it('coerces numeric strings and numbers, rejecting garbage', () => {
      expect(parseCoordinateValue('33.5731')).toBe(33.5731);
      expect(parseCoordinateValue(-7.5898)).toBe(-7.5898);
      expect(parseCoordinateValue('abc')).toBeNull();
    });
  });

  describe('parseCoordinatesFromMapUrl', () => {
    it('extracts coordinates from a Google Maps @lat,lng link', () => {
      expect(parseCoordinatesFromMapUrl('https://www.google.com/maps/@33.5731,-7.5898,16z')).toEqual({
        lat: 33.5731,
        lng: -7.5898,
      });
    });

    it('extracts from ?q= / ll= / destination= query params', () => {
      expect(parseCoordinatesFromMapUrl('https://maps.google.com/?q=33.5731,-7.5898')).toEqual({
        lat: 33.5731,
        lng: -7.5898,
      });
      expect(parseCoordinatesFromMapUrl('https://maps.apple.com/?ll=34.02,-6.84')).toEqual({
        lat: 34.02,
        lng: -6.84,
      });
    });

    it('extracts from an OpenStreetMap #map=z/lat/lng fragment', () => {
      expect(parseCoordinatesFromMapUrl('https://www.openstreetmap.org/#map=16/33.5731/-7.5898')).toEqual({
        lat: 33.5731,
        lng: -7.5898,
      });
    });

    it('returns null for blank input or a link with no coordinates', () => {
      expect(parseCoordinatesFromMapUrl('')).toBeNull();
      expect(parseCoordinatesFromMapUrl(null)).toBeNull();
      expect(parseCoordinatesFromMapUrl('https://maps.google.com/place/somewhere')).toBeNull();
    });

    it('rejects out-of-range coordinates', () => {
      expect(parseCoordinatesFromMapUrl('https://maps.google.com/?q=999,-7.5898')).toBeNull();
    });
  });
});
