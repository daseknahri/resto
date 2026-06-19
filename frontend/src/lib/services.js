/**
 * Kepoli service registry — single source of truth for every surface.
 *
 * Pattern:
 *   - Add a new service here and every surface (Home verticals strip,
 *     Marketplace hub rail, future nav) picks it up automatically.
 *   - NO Tailwind classes in this file. Tailwind's content scanner reliably
 *     finds classes only in .vue/.js files that are scanned, but computed
 *     class strings can be purged. Each surface defines its own ACCENT_CLASSES
 *     map with full literal class strings keyed by `accent`.
 *   - i18n: each entry is labelled via t('services.' + id + 'Title') and
 *     t('services.' + id + 'Desc'). Keys live in src/i18n/messages.js (en/fr)
 *     and src/i18n/messages-ar.js (ar).
 *
 * Entry shape:
 *   id          {string}  unique key; drives i18n lookup
 *   icon        {string}  emoji shown in the tile
 *   status      {'live'|'coming_soon'}
 *   kind        {'lens'|'route'}  only present when status === 'live'
 *   lens        {string}  marketplace ?type= value  (kind === 'lens')
 *   subtype     {string}  optional — when present, Home strip adds ?sub=<subtype>
 *                         and Marketplace seeds selectedShopSubtype on load.
 *                         Only meaningful for kind === 'lens'.
 *   routeName   {string}  vue-router named route    (kind === 'route')
 *   accent      {string}  key into each surface's ACCENT_CLASSES map
 *
 * Use getServices(enabledVerticals) to get a status-adjusted list based on
 * platform.enabled_verticals from the customer session.
 */

import { FOOD, SHOPS, PHARMACY, RIDES, COURIER, DRIVER } from './verticals';

const _DEFINITIONS = [
  { id: FOOD,     icon: '🍽️', kind: 'lens',  lens: 'food',  accent: 'amber'   },
  { id: SHOPS,    icon: '🛍️', kind: 'lens',  lens: 'shop',  accent: 'indigo'  },
  { id: RIDES,    icon: '🚕', kind: 'route', routeName: 'ride', accent: 'emerald' },
  { id: PHARMACY, icon: '💊', kind: 'lens',  lens: 'shop', subtype: 'pharmacy', accent: 'rose'    },
  { id: COURIER,  icon: '📦', kind: 'route', routeName: 'send-package', accent: 'sky'     },
  { id: DRIVER,   icon: '🏍️', kind: 'route', routeName: 'driver',       accent: 'violet'  },
];

// Verticals that are always live regardless of the platform gate
// (food, driver, pharmacy are core; shops is a lens, not a backend endpoint).
const _ALWAYS_LIVE = new Set([FOOD, SHOPS, PHARMACY, DRIVER]);

/**
 * Returns the service list with status adjusted for the platform's enabled_verticals.
 * @param {string[]|null|undefined} enabledVerticals — platform.enabled_verticals from the session.
 *   When null/undefined (platform not loaded), all services are returned as-is (no gate).
 */
export function getServices(enabledVerticals) {
  const enabled = Array.isArray(enabledVerticals) ? new Set(enabledVerticals) : null;
  return _DEFINITIONS.map((svc) => {
    let live = true;
    if (enabled && !_ALWAYS_LIVE.has(svc.id)) {
      live = enabled.has(svc.id);
    }
    return { ...svc, status: live ? 'live' : 'coming_soon' };
  });
}

// Static export — rides is coming_soon by default (backend excludes it from VERTICALS_ENABLED
// default; it requires a separate licensed-car-driver supply). Use getServices(platform.enabled_verticals)
// for a fully dynamic, server-driven list.
const _STATIC_DISABLED = new Set(['rides']);
export const SERVICES = _DEFINITIONS.map((svc) => ({
  ...svc,
  status: _STATIC_DISABLED.has(svc.id) ? 'coming_soon' : 'live',
}));
