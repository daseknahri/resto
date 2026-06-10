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
 *   routeName   {string}  vue-router named route    (kind === 'route')
 *   accent      {string}  key into each surface's ACCENT_CLASSES map
 */
export const SERVICES = [
  { id: 'food',     icon: '🍽️', status: 'live',        kind: 'lens',  lens: 'food',  accent: 'amber'   },
  { id: 'shops',    icon: '🛍️', status: 'live',        kind: 'lens',  lens: 'shop',  accent: 'indigo'  },
  { id: 'rides',    icon: '🚕', status: 'live',        kind: 'route', routeName: 'ride', accent: 'emerald' },
  { id: 'pharmacy', icon: '💊', status: 'coming_soon',                               accent: 'rose'    },
  { id: 'courier',  icon: '📦', status: 'coming_soon',                               accent: 'sky'     },
];
