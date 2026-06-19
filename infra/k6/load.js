/**
 * Kepoli / Resto — k6 load & stress harness   (R22)
 *
 * Three built-in scenarios run sequentially in one execution:
 *   smoke  — 2 VU × 2 min:  verify all endpoints return correct codes
 *   ramp   — 0 → VUS_RAMP → 0 over ~11 min:  find the breaking point
 *   soak   — VUS_SOAK for SOAK_DURATION:  catch leaks, pool exhaustion
 *
 * ENVIRONMENT VARIABLES (all have sensible defaults for localhost):
 *   BASE_URL       public/marketplace origin, e.g. https://kepoli.com
 *   TENANT_URL     one tenant origin,          e.g. https://demo.kepoli.com
 *                  (defaults to BASE_URL — set if the tenant has a different host)
 *   MENU_SLUG      restaurant slug used in /api/marketplace/menu/<slug>/
 *                  e.g. "demo-resto"            (default: "demo")
 *   VUS_RAMP       peak VU count for the ramp scenario  (default: 50)
 *   VUS_SOAK       constant VU count for soak            (default: 20)
 *   SOAK_DURATION  soak duration as a k6 string          (default: "10m")
 *                  set to "60m" for a real overnight soak
 *
 * TYPICAL USAGE:
 *   # Quick smoke against local dev
 *   k6 run infra/k6/load.js
 *
 *   # Full ramp against staging
 *   BASE_URL=https://staging.kepoli.com \
 *   TENANT_URL=https://demo.staging.kepoli.com \
 *   MENU_SLUG=demo-resto \
 *   VUS_RAMP=100 \
 *   SOAK_DURATION=30m \
 *   k6 run infra/k6/load.js
 *
 *   # Smoke only (skip ramp + soak)
 *   k6 run --duration 2m --vus 2 infra/k6/load.js
 *
 * THRESHOLDS (all must pass for exit 0):
 *   http_req_failed          < 1 %   (HTTP error rate across all routes)
 *   http_req_duration p(95)  < 2 s   (overall)
 *   health route p(95)       < 200 ms
 *   meta   route p(95)       < 500 ms
 *   menu   route p(95)       < 1000 ms
 *   marketplace route p(95)  < 1500 ms
 */

import http from 'k6/http';
import { sleep, check, group } from 'k6';
import { Rate } from 'k6/metrics';

// ── config ───────────────────────────────────────────────────────────────────

const BASE_URL       = (__ENV.BASE_URL      || 'http://localhost:8000').replace(/\/$/, '');
const TENANT_URL     = (__ENV.TENANT_URL    || BASE_URL).replace(/\/$/, '');
const MENU_SLUG      = __ENV.MENU_SLUG      || 'demo';
const VUS_RAMP       = parseInt(__ENV.VUS_RAMP      || '50');
const VUS_SOAK       = parseInt(__ENV.VUS_SOAK      || '20');
const SOAK_DURATION  = __ENV.SOAK_DURATION  || '10m';

// ── scenarios + thresholds ───────────────────────────────────────────────────

export const options = {
  scenarios: {
    // 1. Smoke: prove all endpoints return 200 under minimal load.
    smoke: {
      executor: 'constant-vus',
      vus: 2,
      duration: '2m',
      tags: { scenario: 'smoke' },
    },
    // 2. Ramp: find the saturation point — p95 latency, error rate, CPU, pool.
    ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      startTime: '2m',          // begins after smoke
      stages: [
        { duration: '2m', target: Math.ceil(VUS_RAMP * 0.2) },
        { duration: '3m', target: Math.ceil(VUS_RAMP * 0.5) },
        { duration: '4m', target: VUS_RAMP },
        { duration: '2m', target: 0 },
      ],
      tags: { scenario: 'ramp' },
    },
    // 3. Soak: watch for memory leaks, DB connection exhaustion, cache drift.
    soak: {
      executor: 'constant-vus',
      vus: VUS_SOAK,
      startTime: '13m',         // begins after ramp
      duration: SOAK_DURATION,
      tags: { scenario: 'soak' },
    },
  },

  thresholds: {
    // Global error gate — anything above 1% is a fail.
    http_req_failed: ['rate<0.01'],

    // Overall p95 across all routes.
    http_req_duration: ['p(95)<2000'],

    // Per-route SLOs (tagged via http.get options).
    'http_req_duration{route:health}':      ['p(95)<200'],
    'http_req_duration{route:meta}':        ['p(95)<500'],
    'http_req_duration{route:categories}':  ['p(95)<800'],
    'http_req_duration{route:dishes}':      ['p(95)<1000'],
    'http_req_duration{route:marketplace}': ['p(95)<1500'],
    'http_req_duration{route:directory}':   ['p(95)<1500'],
    'http_req_duration{route:mkt_menu}':    ['p(95)<1500'],
  },
};

// ── helpers ──────────────────────────────────────────────────────────────────

/** Build http.get / http.post params that tag the request for threshold routing. */
function p(route, extra) {
  return { tags: { route }, ...extra };
}

/**
 * Assert status 200 + non-empty body; log a warning (don't abort) on failure
 * so the ramp/soak scenarios continue to accumulate latency data even when
 * the server starts to degrade.
 */
function assertOk(res, label) {
  check(res, {
    [`${label} → 200`]:      r => r.status === 200,
    [`${label} → has body`]: r => r.body && r.body.length > 10,
  });
}

// ── traffic profile ──────────────────────────────────────────────────────────
//
// Approximate real-traffic mix based on a typical restaurant SaaS:
//   ~15 % health + misc
//   ~35 % marketplace browse (most anonymous traffic)
//   ~15 % directory browse
//   ~35 % tenant menu load (per-restaurant page)
//
// Each VU rolls once per iteration and lands in one of the four groups.

export default function () {
  const roll = Math.random();

  // ── 1. Health (15 %) ─────────────────────────────────────────────────────
  if (roll < 0.15) {
    group('health', () => {
      const res = http.get(`${BASE_URL}/api/health/`, p('health'));
      assertOk(res, 'GET /api/health/');
    });
    sleep(1);
    return;
  }

  // ── 2. Marketplace browse (35 %) ─────────────────────────────────────────
  if (roll < 0.50) {
    group('marketplace', () => {
      // Landing page: browse all restaurants
      const r1 = http.get(`${BASE_URL}/api/marketplace/`, p('marketplace'));
      assertOk(r1, 'GET /api/marketplace/');
      sleep(0.5);

      // Click into a restaurant menu
      const r2 = http.get(
        `${BASE_URL}/api/marketplace/menu/${MENU_SLUG}/`,
        p('mkt_menu'),
      );
      assertOk(r2, `GET /api/marketplace/menu/${MENU_SLUG}/`);
    });
    sleep(2);
    return;
  }

  // ── 3. Directory browse (15 %) ───────────────────────────────────────────
  if (roll < 0.65) {
    group('directory', () => {
      const res = http.get(`${BASE_URL}/api/directory/`, p('directory'));
      assertOk(res, 'GET /api/directory/');
    });
    sleep(2);
    return;
  }

  // ── 4. Tenant menu load (35 %) ───────────────────────────────────────────
  // Simulates a customer landing on a restaurant's own page:
  // meta → category list → dish list (the three cached requests a page triggers).
  group('tenant_menu', () => {
    const r1 = http.get(`${TENANT_URL}/api/meta/`, p('meta'));
    assertOk(r1, 'GET /api/meta/');
    sleep(0.3);

    const r2 = http.get(`${TENANT_URL}/api/categories/`, p('categories'));
    assertOk(r2, 'GET /api/categories/');
    sleep(0.3);

    const r3 = http.get(`${TENANT_URL}/api/dishes/`, p('dishes'));
    assertOk(r3, 'GET /api/dishes/');
  });
  sleep(3);
}
