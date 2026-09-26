/**
 * Canonical vertical taxonomy — frontend mirror of backend/accounts/verticals.py.
 * See KEPOLI_ACCOUNT_ARCHITECTURE.md §3. Keep the maps in sync with the backend.
 *
 * A "vertical" is a consumer-facing service line. The ids here match the
 * services.js registry ids and the backend VERTICALS_ENABLED tokens, so this is
 * the single place the frontend resolves a tenant business_type or a ride kind
 * to a vertical. pharmacy is its OWN vertical token (not folded into shops).
 */

export const FOOD = 'food';
export const SHOPS = 'shops';
export const PHARMACY = 'pharmacy';
export const RIDES = 'rides';
export const COURIER = 'courier';
export const DRIVER = 'driver';

