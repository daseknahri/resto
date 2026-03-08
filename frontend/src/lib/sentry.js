import * as Sentry from "@sentry/vue";

const parseFloatEnv = (value, fallback = 0) => {
  if (value === undefined || value === null || String(value).trim() === "") return fallback;
  const parsed = Number.parseFloat(String(value));
  if (!Number.isFinite(parsed) || parsed < 0) return fallback;
  return parsed;
};

export const initSentry = (app) => {
  const dsn = String(import.meta.env.VITE_SENTRY_DSN || "").trim();
  if (!dsn) return;

  const environment =
    String(import.meta.env.VITE_SENTRY_ENVIRONMENT || "").trim() ||
    String(import.meta.env.MODE || "production").trim();
  const release = String(import.meta.env.VITE_SENTRY_RELEASE || "").trim() || undefined;
  const tracesSampleRate = parseFloatEnv(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE, 0);

  Sentry.init({
    app,
    dsn,
    environment,
    release,
    tracesSampleRate,
  });
};
