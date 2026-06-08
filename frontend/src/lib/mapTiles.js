// Centralised map-tile configuration.
//
// Default = OpenStreetMap's public tile server — fine for development, but OSM's
// tile usage policy forbids heavy commercial traffic. Before real production
// volume, set a tile provider in the frontend build env:
//
//   VITE_MAP_TILE_URL=https://api.maptiler.com/maps/streets/{z}/{x}/{y}.png?key=YOUR_KEY
//   VITE_MAP_TILE_ATTRIBUTION=© MapTiler © OpenStreetMap contributors
//
// (MapTiler / Mapbox / Stadia all have free tiers that cover this scale; or
// self-host tiles.) No code change needed — every map reads from here.

const DEFAULT_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
const DEFAULT_ATTRIBUTION = '&copy; OpenStreetMap contributors';

export const tileUrl = import.meta.env.VITE_MAP_TILE_URL || DEFAULT_URL;
export const tileAttribution = import.meta.env.VITE_MAP_TILE_ATTRIBUTION || DEFAULT_ATTRIBUTION;

/**
 * Add the configured tile layer to a Leaflet map.
 * @param {*} L      the (lazily-imported) Leaflet module
 * @param {*} map    a Leaflet map instance
 * @param {object} opts extra tileLayer options (merged over the defaults)
 * @returns the created tile layer
 */
export function addTileLayer(L, map, opts = {}) {
  return L.tileLayer(tileUrl, { maxZoom: 19, attribution: tileAttribution, ...opts }).addTo(map);
}
