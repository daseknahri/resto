/**
 * Mount smoke test for OwnerBilling.vue (the owner subscription / billing page, ~825 lines).
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined map
 * access, bad import) was never caught by a test" (this very pass already caught a
 * real WaiterPage TDZ white-screen). Mounting the page runs its real setup() +
 * onMounted for real, so any such crash fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js +
 * pages/__tests__/SuperAppHub.mount.test.js (URL-routed api mock):
 *   - shallowMount + real pinia (setActivePinia(createPinia())) + a mocked lib/api
 *   - useI18n mocked to return deterministic keys ({ t, formatDateTime, currentLocale })
 *
 * Page-specific notes (verified by reading the source, not assumed):
 *   - It imports NO vue-router and uses NO <router-link> / dynamic component, so
 *     there is deliberately NO vue-router mock here.
 *   - It renders NO child components (all inline template + SVGs), so shallowMount
 *     has nothing to auto-stub; only the two built-in <Transition> wrappers are
 *     stubbed for determinism.
 *   - It has NO intervals / poll / visibilitychange / WebSocket / observers, so no
 *     timer leaks — afterEach unmount is plain hygiene.
 *   - onMounted → fetchAll() fires 4 GETs via Promise.allSettled:
 *       /tier-upgrade-targets/  /tier-upgrade-requests/  /dishes/  /owner/staff/
 *     Default: everything resolves empty ({ data: {} }) so the fresh-owner path
 *     renders. Test 2 sets _routes to drive the loaded (plan/usage/upgrade/invoice)
 *     path.
 *   - The plan/usage own-template is driven by the tenant store's `entitlements`
 *     GETTER, which reads `tenant.meta.entitlements` (returned verbatim when it's an
 *     object — that path carries max_dishes / max_staff_accounts the fallback omits).
 *     So test 2 seeds `tenant.meta` DIRECTLY (the page never calls fetchMeta at
 *     mount). useVocabulary is left REAL (it only uses the mocked `t` + real store).
 *   - staleCache: fetchAll reads the `owner.billing` cache first and returns early
 *     when it's still fresh (5-min TTL). Without localStorage.clear() in beforeEach,
 *     test 1's empty snapshot is served to test 2 as still-"fresh", so test 2 would
 *     never fetch its own _routes and its loaded assertions would fail.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatDateTime: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: onMounted fires 4 GETs (/tier-upgrade-targets/,
// /tier-upgrade-requests/, /dishes/, /owner/staff/) — all via Promise.allSettled.
// Default: everything resolves empty so the fresh-owner path renders. Tests set
// _routes to drive the loaded path.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import { useTenantStore } from "../../stores/tenant";
import OwnerBilling from "../OwnerBilling.vue";

const mountBilling = () =>
  shallowMount(OwnerBilling, {
    global: {
      stubs: {
        // Two <Transition name="billing-form"> wrappers; render the slot directly.
        Transition: { template: "<slot />" },
      },
    },
  });

describe("OwnerBilling — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // fetchAll() uses the REAL staleCache (localStorage-backed) under 'owner.billing'.
    // Without this clear, test 1's empty snapshot is served to test 2 as still-"fresh"
    // (within the 5-min TTL), so test 2 never fetches its _routes.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // No intervals/observers to leak here, but unmount for clean teardown + to run
    // the watcher's onUnmounted stop, matching the other mount-smoke tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) fresh owner: empty entitlements, no targets, no requests ──────────────
  // The core guard: the async onMounted (fetchAll's 4 allSettled GETs) and the
  // whole template must render with empty data and not throw. Tenant meta is null,
  // so every optional-chained entitlement getter falls back safely (tier → "Basic",
  // no usage rows, empty targets → "highest tier", empty history → "no requests").
  it("mounts a fresh owner (empty meta / no targets / no requests) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountBilling();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Current-plan heading (always rendered) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerBilling.yourPlan");
    // Request-history heading is always rendered too.
    expect(wrapper.text()).toContain("ownerBilling.historyTitle");
    // Empty targets → "you're on the highest tier" empty state.
    expect(wrapper.text()).toContain("ownerBilling.highestTier");
  });

  // ── (2) loaded plan: entitlements + usage + upgrade target + approved invoice ─
  // Drives the own-template branches that only run with real data:
  //   - tenant.entitlements (seeded via tenant.meta.entitlements) → plan features +
  //     usage-limit rows (max_dishes / max_staff_accounts vs the /dishes/ + /staff/
  //     counts, incl. the pct math + progressbar)
  //   - /tier-upgrade-targets/ → the upgrade grid + per-target targetFeatures()
  //   - /tier-upgrade-requests/ → the history list + formatDateTime + status pill +
  //     the approved-request invoice-download button
  it("mounts a loaded plan (entitlements + usage + upgrade target + approved invoice) without a crash", async () => {
    // entitlements is a GETTER off tenant.meta; when meta.entitlements is an object
    // it is returned verbatim (so max_dishes / max_staff_accounts survive). The page
    // never fetches /meta/ at mount, so seed the store state directly.
    useTenantStore().meta = {
      entitlements: {
        tier_code: "pro",
        tier_name: "Pro",
        can_checkout: true,
        can_whatsapp_order: true,
        max_languages: 3,
        max_dishes: 100,
        max_staff_accounts: 10,
      },
    };

    _routes = {
      "tier-upgrade-targets": {
        data: {
          targets: [
            {
              code: "premium",
              name: "Premium",
              can_request: true,
              is_active: true,
              can_checkout: true,
              can_whatsapp_order: true,
              max_languages: 5,
            },
          ],
          current_tier_code: "pro",
          current_tier_name: "Pro",
          has_pending_request: false,
        },
      },
      "tier-upgrade-requests": {
        data: [
          {
            id: 1,
            current_plan_name: "Basic",
            target_plan_name: "Pro",
            requested_at: new Date(Date.now() - 3 * 86400000).toISOString(),
            status: "approved",
            invoice_amount: "99.00",
            customer_note: "Please upgrade my plan",
            admin_note: "Approved — welcome to Pro",
          },
        ],
      },
      "/dishes/": { data: { count: 42 } },
      "/owner/staff/": { data: { count: 5 } },
    };

    expect(() => {
      wrapper = mountBilling();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerBilling.yourPlan");
    // Usage-limit rows rendered (max_dishes/max_staff > 0 + non-null counts).
    expect(wrapper.text()).toContain("ownerBilling.usageTitle");
    // Upgrade grid rendered (targets.length).
    expect(wrapper.text()).toContain("ownerBilling.upgradeTitle");
    // Approved request with invoice_amount → invoice-download button rendered.
    expect(wrapper.text()).toContain("ownerBilling.invoiceDownload");
  });
});
