/**
 * Sentry error tracking — Vue frontend.
 *
 * Called from main.js as `initSentry(app)` immediately after the
 * Vue application is created.  No-op when VITE_SENTRY_DSN is absent,
 * so local development is unaffected.
 *
 * Environment variables (all optional):
 *   VITE_SENTRY_DSN                    — Sentry project DSN
 *   VITE_SENTRY_ENVIRONMENT            — "production" | "staging" | …
 *   VITE_SENTRY_TRACES_SAMPLE_RATE     — 0.0–1.0 (default 0 = off)
 *   VITE_SENTRY_REPLAYS_SESSION_RATE   — 0.0–1.0 (default 0)
 *   VITE_APP_VERSION                   — release tag injected at build time
 */

let _initialized = false

/**
 * OPS-5-A: Tag every Sentry event with the current tenant's slug + id so SPA
 * errors are attributable to a specific restaurant.  Must be called from the
 * tenant store once the tenant object is loaded (slug and id are required).
 * No-op when Sentry is not initialised (DSN absent or SDK not yet loaded).
 */
export function setTenantContext(slug, id) {
  // Dynamic: Sentry may not be imported yet (it is loaded lazily in initSentry).
  // We use the global Sentry object if available, otherwise try a dynamic import.
  // This intentionally does NOT crash if Sentry is absent.
  try {
    // Sentry attaches itself to the module scope after initSentry resolves.
    // The safest cross-env approach is to call the module-level setTag if the
    // module is already in the module cache (it will be after initSentry fires).
    import('@sentry/vue').then((Sentry) => {
      if (typeof Sentry.setTag === 'function') {
        Sentry.setTag('tenant_slug', slug ?? null)
        Sentry.setTag('tenant_id', id ?? null)
      }
    }).catch(() => {
      // Sentry not installed / DSN absent — intentional no-op.
    })
  } catch {
    // Catch any synchronous error (e.g. import() not supported in test env).
  }
}

export function initSentry(app) {
  const dsn = (import.meta.env.VITE_SENTRY_DSN ?? '').trim()
  if (!dsn || _initialized) return

  // Dynamic import keeps Sentry out of the bundle when DSN is absent
  // (Vite inlines env vars at build time so dead-code elimination applies).
  Promise.all([
    import('@sentry/vue'),
    import('../router/index.js'),
  ])
    .then(([Sentry, routerModule]) => {
      if (_initialized) return // guard against race condition / HMR double-fire

      const router = routerModule.default ?? routerModule

      const tracesSampleRate = Number(
        import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || 0
      )
      const replaysSessionSampleRate = Number(
        import.meta.env.VITE_SENTRY_REPLAYS_SESSION_RATE || 0
      )
      const environment =
        (import.meta.env.VITE_SENTRY_ENVIRONMENT || '').trim() ||
        import.meta.env.MODE ||
        'production'
      const release =
        (import.meta.env.VITE_APP_VERSION || '').trim() || undefined

      const integrations = [
        Sentry.browserTracingIntegration({ router }),
      ]

      if (replaysSessionSampleRate > 0) {
        integrations.push(
          Sentry.replayIntegration({
            maskAllText: true,
            blockAllMedia: true,
          })
        )
      }

      Sentry.init({
        app,
        dsn,
        environment,
        release,
        integrations,
        tracesSampleRate,
        replaysSessionSampleRate,
        replaysOnErrorSampleRate: replaysSessionSampleRate > 0 ? 1.0 : 0,
        // Only propagate trace headers to same-origin requests
        tracePropagationTargets: [/^\//],
        // Suppress noisy browser / extension errors
        ignoreErrors: [
          'NetworkError',
          'Network request failed',
          'Failed to fetch',
          'Load failed',
          'ResizeObserver loop limit exceeded',
          'ResizeObserver loop completed with undelivered notifications',
        ],
        denyUrls: [
          /extensions\//i,
          /^chrome:\/\//i,
          /^chrome-extension:\/\//i,
          /^moz-extension:\/\//i,
        ],
      })

      _initialized = true
    })
    .catch((err) => {
      // Sentry init failure must never crash the app
      if (import.meta.env.DEV) {
        console.warn('[Sentry] init failed:', err)
      }
    })
}
