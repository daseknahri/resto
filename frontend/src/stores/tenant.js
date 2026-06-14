import { defineStore } from "pinia";
import api from "../lib/api";
import { DEMO_TENANT_META } from "../lib/demoMenu";
import { translate } from "../i18n/translate";
import { hasPublicDemoTenant, isPublicDemoHost } from "../lib/runtimeHost";
import { useCartStore } from "./cart";
import { readCache, isFresh, writeCache } from "../lib/staleCache";
import { setTenantContext } from "../lib/sentry";

const META_CACHE = "meta";
const META_TTL   = 5 * 60 * 1000; // 5 minutes

export const useTenantStore = defineStore("tenant", {
  state: () => ({ meta: null, loading: false, error: null }),
  getters: {
    resolvedMeta(state) {
      if (state.meta) return state.meta;
      if (isPublicDemoHost() && !hasPublicDemoTenant()) return DEMO_TENANT_META;
      return null;
    },
    entitlements() {
      const e = this.resolvedMeta?.entitlements;
      if (e && typeof e === "object") return e;
      const plan = this.resolvedMeta?.plan || {};
      const canCheckout = plan.can_checkout === true;
      // Truthful per-plan gating: an ordering channel is available only when its plan
      // flag is set. In-app cart ordering needs at least one submission channel.
      const canWhatsapp = plan.can_whatsapp_order === true;
      const canInAppOrder = canCheckout || canWhatsapp;
      return {
        tier_code: plan.tier_code || plan.code || "",
        tier_name: plan.tier_name || plan.name || "",
        ordering_mode: canCheckout ? "checkout" : canWhatsapp ? "whatsapp" : canInAppOrder ? "in_app" : "menu_only",
        can_order: canCheckout || canWhatsapp || canInAppOrder,
        can_checkout: canCheckout,
        can_whatsapp_order: canWhatsapp,
        can_in_app_order: canInAppOrder,
        max_languages: plan.max_languages || 1,
        is_active: plan.is_active !== false,
      };
    },
    isBrowseOnlyPlan() {
      const mode = this.entitlements?.ordering_mode;
      if (mode) return mode === "menu_only";
      return false;
    },
    /** The tenant's business vertical (restaurant | cafe | bakery | grocery | retail | pharmacy). */
    businessType() {
      return this.resolvedMeta?.profile?.business_type || "restaurant";
    },
    /**
     * Restaurant-only capability flags derived (server-side) from business_type.
     * Falls back to the full restaurant set when absent so older cached metas or
     * a missing profile never hide features from an existing restaurant.
     */
    capabilities() {
      const full = { tables: true, dine_in: true, waiter: true, kitchen: true, reservations: true };
      const caps = this.resolvedMeta?.profile?.capabilities;
      return caps && typeof caps === "object" ? { ...full, ...caps } : full;
    },
    /**
     * Check if a plan feature flag is enabled.
     * TODO: restore per-flag gating once tier work is complete.
     * For now always returns true so all owner features are accessible for testing.
     */
    hasFlag() {
      // All feature flags are enabled by default; the key is intentionally ignored.
      return () => true;
    },
    /** True when payment is overdue but still within the grace period window. */
    isInGracePeriod(state) {
      const raw = state.meta?.payment_overdue_since;
      if (!raw) return false;
      const graceDays = Number(state.meta?.grace_period_days ?? 7) || 7;
      const expiresAt = new Date(raw);
      expiresAt.setDate(expiresAt.getDate() + graceDays);
      return new Date() < expiresAt;
    },
    /** True when the grace period has fully elapsed (overdue and no longer in grace). */
    graceExpired(state) {
      const raw = state.meta?.payment_overdue_since;
      if (!raw) return false;
      const graceDays = Number(state.meta?.grace_period_days ?? 7) || 7;
      const expiresAt = new Date(raw);
      expiresAt.setDate(expiresAt.getDate() + graceDays);
      return new Date() >= expiresAt;
    },
    /** Number of days remaining in the grace period, or null if not overdue. */
    graceDaysRemaining(state) {
      const raw = state.meta?.payment_overdue_since;
      if (!raw) return null;
      const graceDays = Number(state.meta?.grace_period_days ?? 7) || 7;
      const expiresAt = new Date(raw);
      expiresAt.setDate(expiresAt.getDate() + graceDays);
      const now = new Date();
      if (now >= expiresAt) return 0;
      return Math.ceil((expiresAt - now) / (1000 * 60 * 60 * 24));
    },
  },
  actions: {
    mergeProfile(profile) {
      if (!this.meta || !profile || typeof profile !== "object") return;
      this.meta = {
        ...this.meta,
        profile: {
          ...(this.meta.profile || {}),
          ...profile,
        },
      };
    },
    syncCartEntitlements() {
      const cart = useCartStore();
      const canCheckout = this.entitlements?.can_checkout === true;
      const canWhatsapp = this.entitlements?.can_whatsapp_order === true;
      const canInAppOrder = this.entitlements?.can_in_app_order !== false;
      cart.setCanCheckout(canCheckout);
      cart.setCanWhatsapp(canWhatsapp);
      if (!canCheckout && !canWhatsapp && !canInAppOrder && cart.items.length) {
        cart.clear();
      }
    },
    async fetchMeta() {
      const isDemo = isPublicDemoHost() && !hasPublicDemoTenant();

      // ── 1. Serve stale cache instantly ──────────────────────────────────────
      // On repeat visits the tenant colours, name, and profile appear immediately
      // (zero loading state) while we revalidate in the background.
      const cached = readCache(META_CACHE);
      if (cached && !isDemo) {
        this.meta = cached;
        this.syncCartEntitlements();
        // OPS-5-A: tag Sentry with this tenant so SPA errors are attributable
        setTenantContext(cached.slug ?? cached.profile?.slug ?? null, cached.id ?? null);
        this.loading = false;
        // Still fresh → no network call needed this visit
        if (isFresh(META_CACHE, META_TTL)) return;
        // Stale → fall through to background revalidate without a spinner,
        // since the user already sees a fully-rendered UI from cache.
      } else {
        this.loading = true;
        this.error = null;
      }

      // ── 2. Fetch fresh data (foreground on first visit, background on stale) ─
      try {
        const res = await api.get("/meta/", { params: { force_locale: 1 } });
        this.meta = res.data;
        if (!isDemo) writeCache(META_CACHE, res.data);
        this.syncCartEntitlements();
        // OPS-5-A: update Sentry tenant context with fresh data
        setTenantContext(res.data?.slug ?? res.data?.profile?.slug ?? null, res.data?.id ?? null);
      } catch (err) {
        if (!cached) {
          // First visit with no cache — surface the error so the user knows
          this.error = isDemo ? null : translate("tenantStore.loadFailed");
          this.syncCartEntitlements();
          if (!isDemo) console.error(err);
        }
        // Background revalidation failed → silently keep stale data.
        // The user already sees a working UI; we'll retry on the next page load.
      } finally {
        this.loading = false;
      }
    },
  },
});
