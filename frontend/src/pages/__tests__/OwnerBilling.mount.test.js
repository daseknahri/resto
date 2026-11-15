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
 *     plus branchStore.load() → GET /branches/ for the statement branch filter
 *     (Run 7 step 6). Default _routes return { data: {} } → no branches → the
 *     filter stays hidden, so tests 1–2 are unaffected.
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
import api from "../../lib/api";
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

  // ── (3) multi-branch: filter renders, branch choice rides the PDF download ──
  // The wiring's contract: a chosen branch must reach the backend as
  // ?branch=<id> on GET /owner/commission-statement/?format=pdf (FO1 filters
  // the live preview from it); "All locations" sends no branch param.
  it("shows the branch filter with >1 branch and passes ?branch= on the PDF download", async () => {
    _routes = {
      "/branches/": {
        data: {
          branches: [
            { id: 1, slug: "centre", name: "Centre", is_default: true },
            { id: 2, slug: "nord", name: "Nord" },
          ],
        },
      },
    };

    expect(() => {
      wrapper = mountBilling();
    }).not.toThrow();
    await flushPromises();

    const select = wrapper.find("#commission-branch");
    expect(select.exists()).toBe(true);
    expect(select.text()).toContain("ownerBilling.commissionBranchAll");
    expect(select.text()).toContain("Centre");
    expect(select.text()).toContain("Nord");
    // Preview-only semantics are surfaced, not silent.
    expect(wrapper.text()).toContain("ownerBilling.commissionBranchHint");

    // jsdom has no URL.createObjectURL — stub it so the download completes.
    const realCreate = URL.createObjectURL;
    const realRevoke = URL.revokeObjectURL;
    URL.createObjectURL = vi.fn(() => "blob:fake");
    URL.revokeObjectURL = vi.fn();
    try {
      await select.setValue("2");
      const downloadBtn = wrapper
        .findAll("button")
        .find((b) => b.text() === "ownerBilling.commissionDownload");
      expect(downloadBtn).toBeTruthy();
      await downloadBtn.trigger("click");
      await flushPromises();
    } finally {
      URL.createObjectURL = realCreate;
      URL.revokeObjectURL = realRevoke;
    }

    // D-03: the mount-time preview GET (no format param) also hits
    // commission-statement, so the PDF call must be picked by its param.
    const stmtCall = api.get.mock.calls.find(
      ([url, cfg]) =>
        url.includes("commission-statement") && cfg?.params?.format === "pdf"
    );
    expect(stmtCall).toBeTruthy();
    expect(stmtCall[1].params.branch).toBe("2");
    expect(stmtCall[1].params.format).toBe("pdf");
  });

  // ── (5) statement preview (D-03): provisional summary + orders + COD pill ─
  // The preview GET fires on mount; the mocked t returns keys verbatim, so the
  // assertions target keys + the raw money strings fmtStatementMoney builds
  // ("MAD 120.00" — currency + 2dp). The single-currency payload keeps the
  // per-currency table hidden; the two orders exercise both Payment pills.
  it("renders the statement preview (provisional badge + summary + orders + COD/Paid pills)", async () => {
    _routes = {
      "commission-statement": {
        data: {
          issued: false,
          year: 2026,
          month: 6,
          branch_filter: { applied: true },
          // Field names are the real GET envelope (menu/views.py
          // OwnerCommissionStatementView.get): summary total_revenue /
          // total_commission, orders total / commission_amount / created_at.
          summary: {
            order_count: 2,
            total_revenue: "120.00",
            total_commission: "12.00",
            net_payout: "108.00",
            currency: "MAD",
          },
          per_currency: [
            {
              currency: "MAD",
              order_count: 2,
              total_revenue: "120.00",
              total_commission: "12.00",
              net_payout: "108.00",
            },
          ],
          orders: [
            {
              order_number: "ORD-1",
              created_at: "2026-06-15T10:00:00Z",
              total: "100.00",
              commission_amount: "10.00",
              net_payout: "90.00",
              currency: "MAD",
              payment_status: "unpaid",
              is_cod: true,
            },
            {
              order_number: "ORD-2",
              created_at: "2026-06-16T10:00:00Z",
              total: "20.00",
              commission_amount: "2.00",
              net_payout: "18.00",
              currency: "MAD",
              payment_status: "paid",
              is_cod: false,
            },
          ],
        },
      },
    };

    expect(() => {
      wrapper = mountBilling();
    }).not.toThrow();
    await flushPromises();

    const text = wrapper.text();
    expect(text).toContain("ownerBilling.statementProvisional");
    expect(text).toContain("MAD 120.00");
    expect(text).toContain("MAD 12.00");
    expect(text).toContain("MAD 108.00");
    expect(text).toContain("ORD-1");
    expect(text).toContain("ORD-2");
    expect(text).toContain("2026-06-15"); // created_at sliced to the date
    expect(text).toContain("ownerBilling.statementCod");
    expect(text).toContain("ownerBilling.statementPaid");
    // Not issued yet → the Issue action is offered.
    expect(
      wrapper.findAll("button").some((b) => b.text() === "ownerBilling.statementIssue")
    ).toBe(true);
  });

  // ── (6) issue flow (D-04): past month → POST /issue/ → issued badge ──────
  it("issues a past month from the preview (POST /issue/ → issued badge + rev)", async () => {
    const year = new Date().getFullYear();
    _routes = {
      "commission-statement": {
        data: {
          issued: false,
          year,
          month: 6,
          branch_filter: { applied: true },
          summary: { order_count: 1, total_revenue: "50.00", total_commission: "5.00", net_payout: "45.00", currency: "MAD" },
          per_currency: [],
          orders: [],
        },
      },
    };

    expect(() => {
      wrapper = mountBilling();
    }).not.toThrow();
    await flushPromises();

    // Move off the current month (the default) so the issue goes straight
    // through — the current month needs the inline confirm instead (test 7).
    await wrapper.find("#commission-month").setValue("6");
    await flushPromises();

    api.post.mockResolvedValueOnce({
      data: {
        issued: true,
        revision: 1,
        issued_at: "2026-07-01T10:00:00Z",
        year,
        month: 6,
        branch_filter: { applied: true },
        summary: { order_count: 1, total_revenue: "50.00", total_commission: "5.00", net_payout: "45.00", currency: "MAD" },
        per_currency: [],
        orders: [],
      },
    });

    const issueBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "ownerBilling.statementIssue");
    expect(issueBtn).toBeTruthy();
    await issueBtn.trigger("click");
    await flushPromises();

    expect(api.post).toHaveBeenCalledWith("/owner/commission-statement/issue/", {
      year,
      month: 6,
    });
    expect(wrapper.text()).toContain('ownerBilling.statementIssuedBadge({"rev":1})');
    expect(wrapper.text()).not.toContain("ownerBilling.statementProvisional");
  });

  // ── (7) current month (D-04 + D-09): inline confirm, then confirm_current ─
  it("asks for inline confirmation on the current month and sends confirm_current", async () => {
    const year = new Date().getFullYear();
    const month = new Date().getMonth() + 1;
    _routes = {
      "commission-statement": {
        data: {
          issued: false,
          year,
          month,
          branch_filter: { applied: true },
          summary: { order_count: 0, total_revenue: "0.00", total_commission: "0.00", net_payout: "0.00", currency: "MAD" },
          per_currency: [],
          orders: [],
        },
      },
    };

    expect(() => {
      wrapper = mountBilling();
    }).not.toThrow();
    await flushPromises();

    const issueBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "ownerBilling.statementIssue");
    expect(issueBtn).toBeTruthy();
    await issueBtn.trigger("click");
    await flushPromises();

    // No POST yet — the inline confirm strip is shown instead.
    expect(api.post).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("ownerBilling.statementConfirmCurrent");

    const anywayBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "ownerBilling.statementIssueAnyway");
    expect(anywayBtn).toBeTruthy();
    await anywayBtn.trigger("click");
    await flushPromises();

    expect(api.post).toHaveBeenCalledWith("/owner/commission-statement/issue/", {
      year,
      month,
      confirm_current: true,
    });
  });

  // ── (4) single branch: no choice, no filter, download stays account-level ──
  it("hides the branch filter with a single branch (no real choice)", async () => {
    _routes = {
      "/branches/": {
        data: { branches: [{ id: 1, slug: "centre", name: "Centre", is_default: true }] },
      },
    };

    expect(() => {
      wrapper = mountBilling();
    }).not.toThrow();
    await flushPromises();

    expect(wrapper.find("#commission-branch").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("ownerBilling.commissionBranchHint");
  });
});
// ── G4b-F (B-40) — appended by Run 8 G4b, cluster F ──────────────────────────
// Imports are hoisted, so these resolve to the same (mocked api / real
// useConfirmModal) modules as the imports at the top of the file.
import { useConfirmModal } from "../../composables/useConfirmModal";

describe("OwnerBilling — G4b-F (B-40 upgrade confirm / statement years)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // One requestable upgrade target; the request form appears after selecting it.
  const _mountWithTarget = async () => {
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
    };
    wrapper = mountBilling();
    await flushPromises();

    const targetBtn = wrapper.find('button[aria-label="Premium"]');
    expect(targetBtn.exists()).toBe(true);
    await targetBtn.trigger("click");
    await flushPromises();

    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "ownerBilling.submitRequest");
    expect(submitBtn).toBeTruthy();
    return submitBtn;
  };

  // B-40: the upgrade request must confirm first — a pending request blocks
  // further requests, so a one-tap POST was too easy to fire by mistake.
  it("B-40: upgrade request asks for confirmation (plan named, not danger) and posts only after approval", async () => {
    const submitBtn = await _mountWithTarget();
    await submitBtn.trigger("click");
    await flushPromises();

    // No POST before the owner approves the confirm dialog.
    expect(api.post).not.toHaveBeenCalledWith("/tier-upgrade-requests/", expect.anything());
    expect(useConfirmModal().visible.value).toBe(true);
    const opts = useConfirmModal().options.value;
    expect(opts.title).toContain("ownerBilling.upgradeConfirmTitle");
    expect(opts.title).toContain("Premium");
    expect(opts.danger).toBe(false);

    useConfirmModal()._settle(true);
    await flushPromises();
    await flushPromises();

    expect(api.post).toHaveBeenCalledWith("/tier-upgrade-requests/", {
      target_plan_code: "premium",
      customer_note: "",
    });
  });

  it("B-40: declining the upgrade confirm posts nothing", async () => {
    const submitBtn = await _mountWithTarget();
    await submitBtn.trigger("click");
    await flushPromises();

    useConfirmModal()._settle(false);
    await flushPromises();

    expect(api.post).not.toHaveBeenCalled();
  });

  // B-40: the statement year select used to go back only 3 years, so older
  // statements were unreachable. It now reaches back 10 years.
  it("B-40: commission year select reaches back 10 years", async () => {
    wrapper = mountBilling();
    await flushPromises();

    const year = new Date().getFullYear();
    const options = wrapper
      .find("#commission-year")
      .findAll("option")
      .map((o) => o.text());
    expect(options).toContain(String(year));
    expect(options).toContain(String(year - 10));
    expect(options).not.toContain(String(year - 11));
  });
});
