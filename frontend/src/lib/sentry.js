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
