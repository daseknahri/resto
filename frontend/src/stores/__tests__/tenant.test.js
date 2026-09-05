/**
 * Unit tests for useTenantStore — the tenant/meta store.
 *
 * Priority: the PURE GETTERS (entitlements plan→ordering-mode matrix, browse-only
 * plan, business type, capability flags, feature flags, and the billing
 * grace-period date math). Each is driven by assigning `store.meta` directly.
 *
 * On the jsdom host (localhost) `isPublicDemoHost()` is false — VITE_PLATFORM_PUBLIC_HOSTS
 * is empty and "localhost" matches no menu/admin/api root — so `resolvedMeta`
 * returns `store.meta` verbatim. That means the getters need NO host/demo mocking:
 * set `store.meta` and read the getter.
 *
 * fetchMeta is covered lightly (success + 404-not-found + generic error) with the
 * api + staleCache boundaries mocked so the tests are deterministic and never leak
 * a cached payload between cases (staleCache is backed by real localStorage, which
 * persists across tests within a file).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useTenantStore } from "../tenant";

// api is mocked in every store test (avoids importing the real axios client).
// Getters never touch it; fetchMeta drives it explicitly per-test.
vi.mock("../../lib/api", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));
import api from "../../lib/api";

// staleCache is backed by real localStorage, which persists across tests within a
// file. Mock it so fetchMeta always sees a deterministic "no cache" and a write in
// one test never leaks into the next.
vi.mock("../../lib/staleCache", () => ({
  readCache: vi.fn(() => null),
  isFresh: vi.fn(() => false),
  writeCache: vi.fn(),
}));

// Identity translate so the fetchMeta error branch asserts a stable key.
vi.mock("../../i18n/translate", () => ({
  translate: (key) => key,
}));

/** ISO string for `n` days before now — used to make the grace-period math relative to NOW. */
const daysAgoISO = (n) => new Date(Date.now() - n * 86400000).toISOString();

describe("useTenantStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  // ── entitlements: the plan → ordering-mode matrix ─────────────────────────────
  describe("entitlements getter", () => {
    it("plan.can_checkout:true → ordering_mode 'checkout', orderable, can_checkout true", () => {
      const store = useTenantStore();
      store.meta = { plan: { can_checkout: true } };
      const e = store.entitlements;
      expect(e.ordering_mode).toBe("checkout");
      expect(e.can_order).toBe(true);
      expect(e.can_checkout).toBe(true);
    });

    it("plan.can_whatsapp_order:true (no checkout) → ordering_mode 'whatsapp'", () => {
      const store = useTenantStore();
      store.meta = { plan: { can_whatsapp_order: true } };
      const e = store.entitlements;
      expect(e.ordering_mode).toBe("whatsapp");
      expect(e.can_checkout).toBe(false);
      expect(e.can_whatsapp_order).toBe(true);
      expect(e.can_order).toBe(true);
    });

    it("neither flag → ordering_mode 'menu_only', can_order false", () => {
      const store = useTenantStore();
      store.meta = { plan: {} };
      const e = store.entitlements;
      expect(e.ordering_mode).toBe("menu_only");
      expect(e.can_order).toBe(false);
      expect(e.can_checkout).toBe(false);
      expect(e.can_whatsapp_order).toBe(false);
    });

    it("max_languages defaults to 1 and is_active defaults to true", () => {
      const store = useTenantStore();
      store.meta = { plan: {} };
      const e = store.entitlements;
      expect(e.max_languages).toBe(1);
      expect(e.is_active).toBe(true);
    });

    it("is_active is false only when plan.is_active === false", () => {
      const store = useTenantStore();
      store.meta = { plan: { is_active: false } };
      expect(store.entitlements.is_active).toBe(false);
    });

    it("an explicit meta.entitlements object is returned verbatim (NOT derived from plan)", () => {
      const store = useTenantStore();
      const explicit = { ordering_mode: "custom", can_checkout: false, foo: "bar" };
      // plan says checkout, but a present entitlements object must win untouched.
      store.meta = { entitlements: explicit, plan: { can_checkout: true } };
      expect(store.entitlements).toEqual(explicit);
      expect(store.entitlements.ordering_mode).toBe("custom");
    });
  });

  // ── isBrowseOnlyPlan ──────────────────────────────────────────────────────────
  describe("isBrowseOnlyPlan getter", () => {
    it("true when entitlements.ordering_mode is 'menu_only'", () => {
      const store = useTenantStore();
      store.meta = { plan: {} };
      expect(store.isBrowseOnlyPlan).toBe(true);
    });

    it("false when the plan can checkout", () => {
      const store = useTenantStore();
      store.meta = { plan: { can_checkout: true } };
      expect(store.isBrowseOnlyPlan).toBe(false);
    });
  });

  // ── businessType ──────────────────────────────────────────────────────────────
  describe("businessType getter", () => {
    it("reads meta.profile.business_type", () => {
      const store = useTenantStore();
      store.meta = { profile: { business_type: "cafe" } };
      expect(store.businessType).toBe("cafe");
    });

    it("defaults to 'restaurant' when absent", () => {
      const store = useTenantStore();
      store.meta = { profile: {} };
      expect(store.businessType).toBe("restaurant");
    });
  });

  // ── capabilities ──────────────────────────────────────────────────────────────
  describe("capabilities getter", () => {
    it("returns the full restaurant set when profile.capabilities is absent (fallback)", () => {
      const store = useTenantStore();
      store.meta = { profile: {} };
      expect(store.capabilities).toEqual({
        tables: true,
        dine_in: true,
        waiter: true,
        kitchen: true,
        reservations: true,
      });
    });

    it("merges served capabilities over the full set, overriding only the given flags", () => {
      const store = useTenantStore();
      store.meta = { profile: { capabilities: { waiter: false } } };
      expect(store.capabilities).toEqual({
        tables: true,
        dine_in: true,
        waiter: false, // the only overridden flag
        kitchen: true,
        reservations: true,
      });
    });
  });

  // ── hasFlag: returns a lookup FUNCTION ────────────────────────────────────────
  describe("hasFlag getter", () => {
    it("returns a function that defaults to true when feature_flags is not an array", () => {
      const store = useTenantStore();
      store.meta = {}; // no feature_flags served
      expect(typeof store.hasFlag).toBe("function");
      expect(store.hasFlag("anything")).toBe(true);
    });

    it("returns the matching row's enabled === true, and false for an absent key", () => {
      const store = useTenantStore();
      store.meta = {
        feature_flags: [
          { key: "a", enabled: true },
          { key: "b", enabled: false },
        ],
      };
      expect(store.hasFlag("a")).toBe(true);
      expect(store.hasFlag("b")).toBe(false); // present but disabled
      expect(store.hasFlag("missing")).toBe(false); // absent key
    });
  });

  // ── billing grace-period date math (deterministic: overdue set relative to NOW) ─
  describe("billing grace-period getters", () => {
    it("in grace: overdue 3 days ago, default 7-day grace → in grace, not expired, ~4 days left", () => {
      const store = useTenantStore();
      store.meta = { payment_overdue_since: daysAgoISO(3) };
      expect(store.isInGracePeriod).toBe(true);
      expect(store.graceExpired).toBe(false);
      // ceil(~4 days); band tolerates midnight/DST boundary drift.
      expect(store.graceDaysRemaining).toBeGreaterThanOrEqual(3);
      expect(store.graceDaysRemaining).toBeLessThanOrEqual(5);
    });

    it("expired: overdue 10 days ago, default 7-day grace → expired, not in grace, 0 days left", () => {
      const store = useTenantStore();
      store.meta = { payment_overdue_since: daysAgoISO(10) };
      expect(store.isInGracePeriod).toBe(false);
      expect(store.graceExpired).toBe(true);
      expect(store.graceDaysRemaining).toBe(0);
    });

    it("honors a custom grace_period_days (3-day grace, overdue 5 days ago → expired)", () => {
      const store = useTenantStore();
      // With the default 7-day grace this would still be IN grace; the custom
      // 3-day window proves grace_period_days is actually read.
      store.meta = { payment_overdue_since: daysAgoISO(5), grace_period_days: 3 };
      expect(store.graceExpired).toBe(true);
      expect(store.isInGracePeriod).toBe(false);
      expect(store.graceDaysRemaining).toBe(0);
    });

    it("not overdue: no payment_overdue_since → false / false / null", () => {
      const store = useTenantStore();
      store.meta = {};
      expect(store.isInGracePeriod).toBe(false);
      expect(store.graceExpired).toBe(false);
      expect(store.graceDaysRemaining).toBeNull();
    });
  });

  // ── mergeProfile action ───────────────────────────────────────────────────────
  describe("mergeProfile action", () => {
    it("is a no-op when meta is null", () => {
      const store = useTenantStore();
      store.meta = null;
      store.mergeProfile({ business_type: "cafe" });
      expect(store.meta).toBeNull();
    });

    it("is a no-op when profile is not an object", () => {
      const store = useTenantStore();
      store.meta = { profile: { business_type: "restaurant" } };
      store.mergeProfile("nope");
      store.mergeProfile(null);
      expect(store.meta.profile).toEqual({ business_type: "restaurant" });
    });

    it("shallow-merges into meta.profile, preserving existing profile keys and other meta fields", () => {
      const store = useTenantStore();
      store.meta = { profile: { a: 1, b: 2 }, slug: "acme" };
      store.mergeProfile({ b: 3, c: 4 });
      expect(store.meta.profile).toEqual({ a: 1, b: 3, c: 4 });
      expect(store.meta.slug).toBe("acme"); // sibling meta fields untouched
    });
  });

  // ── fetchMeta action (lightly covered; api + cache boundaries mocked) ──────────
  describe("fetchMeta action", () => {
    it("populates meta from a successful GET /meta/ and clears loading", async () => {
      const data = {
        id: 7,
        slug: "acme",
        plan: { can_checkout: true },
        profile: { business_type: "cafe" },
      };
      api.get.mockResolvedValueOnce({ data });
      const store = useTenantStore();
      await store.fetchMeta();
      expect(api.get).toHaveBeenCalledWith("/meta/", { params: { force_locale: 1 } });
      expect(store.meta).toEqual(data);
      expect(store.loading).toBe(false);
      expect(store.notFound).toBe(false);
    });

    it("sets notFound on a 404 with no cache", async () => {
      api.get.mockRejectedValueOnce({ response: { status: 404 } });
      const store = useTenantStore();
      await store.fetchMeta();
      expect(store.notFound).toBe(true);
      expect(store.meta).toBeNull();
      expect(store.loading).toBe(false);
    });

    it("surfaces a load error on a non-404 failure without marking notFound", async () => {
      const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
      api.get.mockRejectedValueOnce(new Error("boom"));
      const store = useTenantStore();
      await store.fetchMeta();
      expect(store.notFound).toBe(false);
      expect(store.error).toBe("tenantStore.loadFailed");
      expect(store.loading).toBe(false);
      errSpy.mockRestore();
    });
  });
});
