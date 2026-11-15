/**
 * Mount smoke test for AdminConsole.vue (the platform super-admin console, ~2395 lines).
 *
 * WHY: this is the app's recurring production bug class — a big page white-screens
 * because a setup()-time error (a TDZ ReferenceError, an undefined lookup-map, an
 * unguarded browser API) throws inside <script setup> and was never caught by a test.
 * AdminConsole runs a heavy setup(): ~40 refs, a dozen computeds, a setup-time
 * `inferDomainSuffix()` that reads window.location, four Pinia/composable wires
 * (toast / useI18n / useConfirmModal / usePromptModal), an onMounted that fires
 * `selectAdminView("operations")` (a Promise.all of /leads/ + /admin-tier-upgrade-requests/),
 * and six lazy watches. shallowMount runs the page's OWN setup() (the thing under
 * test) while auto-stubbing the heavy children (AdminConsoleLiveOrdersModal /
 * DeliveryPricingDrawer / DryRunImportModal / OnboardingPackage / ProvisioningJobs /
 * AppIcon), so any setup-time crash fails CI here instead of shipping a blank page.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js + CustomerAccount.mount.test.js
 * (URL-routed api mock), with two page-specific differences verified against the source:
 *   1. The api boundary is `lib/adminApi` (a SEPARATE axios instance), NOT `lib/api` —
 *      so the mock targets ../../lib/adminApi and must expose get/post/put/patch/delete
 *      (the page calls all five).
 *   2. The page imports NOTHING from vue-router (`grep "from 'vue-router'"` → no match).
 *      It uses <router-link> in its template via the app-level global registration, so
 *      there is no vue-router module to mock — only a RouterLink stub in global.stubs
 *      (which makes <router-link> resolve to a no-op <a> in the plugin-less test app).
 *      RouterLinkStub is a plain const (NOT referenced inside a vi.mock factory), so it
 *      needs no vi.hoisted — the TDZ trap only bites stubs used inside a hoisted factory.
 *
 * Left REAL (jsdom-safe): the toast store (real Pinia), useConfirmModal / usePromptModal
 * (pure module-level ref singletons — no setup side effects; only resolve on user action),
 * and lib/runtimeHost's getPrimaryPublicHost (pure over import.meta.env → "" in jsdom, so
 * inferDomainSuffix falls through to window.location.hostname). The page registers NO
 * interval / window listener / WebSocket at mount, but afterEach unmounts anyway to settle
 * the in-flight AbortController fetches and tear down the watches between tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in AdminConsole is { t, currentLocale } — the mock MUST return both
// or the setup destructure/formatDate throws. t returns the key verbatim (params appended)
// so assertions can target the stable i18n keys the page's own template renders; currentLocale
// is read as `currentLocale.value` inside formatDate's Intl.DateTimeFormat.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock for the SEPARATE admin axios instance (lib/adminApi). onMounted fires
// GET /leads/ + GET /admin-tier-upgrade-requests/. Default: everything resolves empty so the
// fresh-admin empty path renders; a test sets _routes to drive the loaded path. _match is a
// plain const referenced only from the lazy vi.fn closures (never a hoisted factory) → TDZ-safe.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/adminApi", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// The page does NOT import RouterLink from vue-router (no vue-router mock needed); it renders
// <router-link> via the app's global registration. In the plugin-less test app, a RouterLink
// stub in global.stubs makes <router-link> resolve to a no-op <a> instead of an unresolved
// custom element. Plain const is correct here (see file header, difference #2).
const RouterLinkStub = { name: "RouterLink", props: ["to"], template: "<a><slot /></a>" };

import AdminConsole from "../AdminConsole.vue";
import adminApi from "../../lib/adminApi";
import { useConfirmModal } from "../../composables/useConfirmModal";

const mountConsole = () =>
  shallowMount(AdminConsole, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
      },
    },
  });

describe("AdminConsole — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // TRAP: the toast/other stores are localStorage-backed (staleCache); clear it FIRST so a
    // cache write in one test can't be served as still-"fresh" to the next.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // No interval/listener/WS is registered at mount, but unmount settles the in-flight
    // AbortController fetches and tears down the six watches so nothing leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default admin mount: empty operations view ────────────────────────
  // The core guard: the whole setup() (inferDomainSuffix at setup, the onMounted
  // selectAdminView("operations") Promise.all, every computed the header/metrics read)
  // and the whole own-template must render with empty data and not throw. The header
  // kicker is the always-rendered crash anchor; the leads empty-state confirms the
  // default operations section rendered its own template on the empty (default) path.
  it("mounts the default (operations) admin view with empty data without a setup() crash", async () => {
    expect(() => {
      wrapper = mountConsole();
    }).not.toThrow();

    await flushPromises(); // onMounted → selectAdminView → Promise.all([fetchLeads, fetchUpgradeRequests])

    expect(wrapper.exists()).toBe(true);
    // Header kicker (always rendered, page's own template) — the crash-guard anchor.
    expect(wrapper.text()).toContain("adminConsole.superAdmin");
    // activeAdminView defaults to "operations" → activeAdminViewTitle = provisioningOperations.
    expect(wrapper.text()).toContain("adminConsole.provisioningOperations");
    // Empty /leads/ (default { data: {} } → leads.length falsy) → operations empty-state.
    expect(wrapper.text()).toContain("adminConsole.noLeadsPending");
  });

  // ── (2) loaded operations view: real leads + tier-upgrade payloads ────────
  // Drives the page's OWN loaded template (the operations section is not delegated to a
  // stubbed child): the leads-card v-for (leadStatusLabel map, previewFor/*Loading maps,
  // formatDate) and the tier-upgrade cards/table (upgradeStatusLabel/Class maps), plus the
  // operations activeAdminMetrics branch (leads.length / upgradeRequests.length). These are
  // the map-lookup + array-render paths that only run with non-empty payloads.
  it("mounts the operations view with real leads + tier-upgrade requests without a crash", async () => {
    _routes = {
      "/leads/": {
        data: [
          {
            id: 1,
            name: "Test Lead",
            status: "new",
            plan_code: "pro",
            email: "lead@example.com",
            phone: "0600000000",
            source: "web",
            notes: "wants delivery",
          },
        ],
      },
      "/admin-tier-upgrade-requests/": {
        data: [
          {
            id: 10,
            requested_at: "2026-01-01T10:00:00Z",
            status: "pending",
            tenant_slug: "chez-test",
            current_plan_name: "Free",
            target_plan_name: "Pro",
            payment_method: "cash",
            payment_reference: "TXN-1",
            target_plan_is_active: true,
          },
        ],
      },
    };

    expect(() => {
      wrapper = mountConsole();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Header still renders.
    expect(text).toContain("adminConsole.superAdmin");
    // Lead card rendered from the fetched payload (own-template v-for, not a stubbed child).
    expect(text).toContain("Test Lead");
    // Tier-upgrade request rendered from its fetched payload (own-template card/table).
    expect(text).toContain("chez-test");
  });

  // ── (3) delivery modal (D-11): marketplace rate fraction ↔ percent ────────
  // The backend stores marketplace_commission_pct as a FRACTION (0–1) while the
  // form holds PERCENT like delivery_commission_pct: the GET "0.15" must load as
  // 15 in the drawer form, and saving must PATCH 0.15 back (15 / 100).
  // _match picks the FIRST fragment that matches, so the specific delivery URL
  // is listed before the bare /admin-tenants/ list URL.
  it("loads the marketplace rate as percent and saves it back as a fraction", async () => {
    _routes = {
      "/admin-tenants/7/delivery/": {
        // Real GET envelope (sales/views.py): { tenant, delivery: {...} } —
        // openDeliveryModal reads res.data.delivery, not res.data.
        data: {
          tenant: { id: 7, slug: "chez-test", name: "Chez Test" },
          delivery: {
            delivery_fee: "20.00",
            delivery_base_fee: "5.00",
            delivery_per_km: "1.00",
            delivery_free_over: "0",
            delivery_minimum_order: "0",
            delivery_radius_km: null,
            delivery_zone_description: "",
            delivery_commission_pct: "10",
            marketplace_commission_pct: "0.15",
            platform_delivery_enabled: false,
          },
        },
      },
      "/admin-tenants/": {
        data: [{ id: 7, name: "Chez Test", slug: "chez-test" }],
      },
    };

    expect(() => {
      wrapper = mountConsole();
    }).not.toThrow();
    await flushPromises();

    // Switch to the tenants view (nav pill renders the mocked key verbatim).
    const tenantsBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "adminConsole.tenantLifecycleControls");
    expect(tenantsBtn).toBeTruthy();
    await tenantsBtn.trigger("click");
    await flushPromises();

    const deliveryBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "adminConsole.delivery.button");
    expect(deliveryBtn).toBeTruthy();
    await deliveryBtn.trigger("click");
    await flushPromises();

    const drawer = wrapper.findComponent({ name: "AdminConsoleDeliveryPricingDrawer" });
    expect(drawer.exists()).toBe(true);
    expect(drawer.props("form").marketplace_commission_pct).toBe(15);
    expect(drawer.props("form").delivery_commission_pct).toBe(10);

    await drawer.vm.$emit("submit");
    await flushPromises();

    const patchCall = adminApi.patch.mock.calls.find(([url]) =>
      url.includes("/admin-tenants/7/delivery/")
    );
    expect(patchCall).toBeTruthy();
    expect(patchCall[1].marketplace_commission_pct).toBe(0.15);
    expect(patchCall[1].delivery_commission_pct).toBe(10);
  });
});

describe("AdminConsole — provision confirms first (A2-12)", () => {
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

  // Exact match: the nav has a "provisioningOperations" view button whose
  // text CONTAINS "adminConsole.provision" as a substring — the shared
  // substring findButton would click that instead of the lead's provision
  // button (it comes first in DOM order).
  const findProvisionButton = () =>
    wrapper.findAll("button").find((b) => b.text().trim() === "adminConsole.provision");

  const mountWithLead = async () => {
    _routes = {
      "/leads/": { data: [{ id: 7, name: "Chez Test", email: "owner@example.com", status: "new" }] },
      "/lead-provision-preview/7/": { data: { resolved_slug: "chez-test", resolved_domain: "chez-test.example.com", input_domain: "chez-test.example.com", collision: false } },
    };
    wrapper = mountConsole();
    await flushPromises();
    return wrapper;
  };

  it("provision confirms first; cancelling skips the PUT", async () => {
    await mountWithLead();
    await findProvisionButton().trigger("click");
    await flushPromises();
    // The ConfirmModal itself lives in App.vue, not in this page's tree —
    // assert the confirm the page actually requested via the real singleton.
    const modal = useConfirmModal();
    expect(modal.visible.value).toBe(true);
    expect(modal.options.value.title).toBe("adminConsole.provisionConfirmTitle");
    expect(modal.options.value.body).toContain("Chez Test");
    const { _settle } = useConfirmModal();
    _settle(false);
    await flushPromises();
    expect(adminApi.put).not.toHaveBeenCalled();
  });

  it("confirming the provision fires the PUT", async () => {
    await mountWithLead();
    await findProvisionButton().trigger("click");
    await flushPromises();
    const { _settle } = useConfirmModal();
    adminApi.put.mockResolvedValue({ data: { tenant_url: "https://chez-test.example.com", tenant: { id: 1 } } });
    _settle(true);
    await flushPromises();
    expect(adminApi.put).toHaveBeenCalledWith("/lead-provision/7/", expect.anything());
  });
});

// usePromptModal is imported here (hoisted) for the A2-40 approve test only:
// the base tests above never call prompt(). The prompt singleton mirrors
// useConfirmModal (module-level ref singleton, resolved on user action via
// _settle); the test resolves it through _settle with a fallback chain and
// fails loudly if the API differs — see the A2-40 test note.
import { usePromptModal } from "../../composables/usePromptModal";

describe("AdminConsole — Run 8 G3b W10 (A2-37..A2-53)", () => {
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
    vi.useRealTimers();
  });

  const leadFixture = (id, name, status) => ({
    id,
    name,
    status,
    plan_code: "pro",
    email: `${name.toLowerCase().replace(/ /g, "-")}@example.com`,
    phone: "0600000000",
    source: "web",
    notes: "",
  });

  const mountWithLeads = async (leads) => {
    _routes = {
      "/leads/": { data: leads },
      "/admin-tier-upgrade-requests/": { data: [] },
    };
    wrapper = mountConsole();
    await flushPromises();
    return wrapper;
  };

  const switchView = async (label) => {
    const btn = wrapper.findAll("button").find((b) => b.text().trim() === label);
    expect(btn).toBeTruthy();
    await btn.trigger("click");
    await flushPromises();
  };

  // ── A2-37: leads default to actionable; live leads hidden; status filter sends ?status= ──
  it("A2-37 defaults to actionable leads and filters live leads out until selected", async () => {
    await mountWithLeads([
      leadFixture(1, "Alpha Lead", "new"),
      leadFixture(2, "Beta Lead", "live"),
    ]);
    expect(wrapper.text()).toContain("Alpha Lead");
    expect(wrapper.text()).not.toContain("Beta Lead");
    expect(wrapper.text()).toContain("adminConsole.leadsShowing");

    // The leads filter is the first <select> in the operations view.
    const leadsSelect = wrapper.findAll("select")[0];
    await leadsSelect.setValue("live");
    await flushPromises();
    const leadCall = adminApi.get.mock.calls.find(
      ([url, cfg]) => url.includes("/leads/") && cfg?.params?.status === "live"
    );
    expect(leadCall).toBeTruthy();
    expect(wrapper.text()).toContain("Beta Lead");
    expect(wrapper.text()).not.toContain("Alpha Lead");
  });

  it("A2-37 search narrows the lead list client-side", async () => {
    await mountWithLeads([leadFixture(1, "Alpha Lead", "new"), leadFixture(2, "Beta Lead", "new")]);
    wrapper.vm.leadSearch = "beta";
    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain("Beta Lead");
    expect(wrapper.text()).not.toContain("Alpha Lead");
  });

  // ── A2-38 + A2-48: provision refetches leads; the package is stamped with an issue time ──
  it("A2-38/A2-48 provision refetches the lead list and stamps the package issue time", async () => {
    await mountWithLeads([leadFixture(7, "Chez Test", "new")]);
    const findProvisionButton = () =>
      wrapper.findAll("button").find((b) => b.text().trim() === "adminConsole.provision");
    await findProvisionButton().trigger("click");
    await flushPromises();
    const { _settle } = useConfirmModal();
    adminApi.put.mockResolvedValue({ data: { tenant_url: "https://chez-test.example.com", tenant: "chez-test" } });
    _settle(true);
    await flushPromises();
    expect(adminApi.put).toHaveBeenCalledWith("/lead-provision/7/", expect.anything());
    // Initial load + the post-provision refetch.
    const leadCalls = adminApi.get.mock.calls.filter(([url]) => url.includes("/leads/"));
    expect(leadCalls.length).toBeGreaterThanOrEqual(2);
    const pkg = wrapper.findComponent({ name: "AdminConsoleOnboardingPackage" });
    expect(pkg.exists()).toBe(true);
    expect(pkg.props("provisionedAt")).toBeGreaterThan(0);
  });

  // ── A2-39: upgrades default to status=pending; 200 rows surface the cap note ──
  it("A2-39 upgrades default to pending and show the cap note at 200 rows", async () => {
    const rows = Array.from({ length: 200 }, (_, i) => ({
      id: 100 + i,
      requested_at: "2026-01-01T10:00:00Z",
      status: "pending",
      tenant_slug: `chez-test-${i}`,
      current_plan_name: "Free",
      target_plan_name: "Pro",
      payment_method: "cash",
      payment_reference: "",
      target_plan_is_active: true,
    }));
    _routes = {
      "/leads/": { data: [] },
      "/admin-tier-upgrade-requests/": { data: rows },
    };
    wrapper = mountConsole();
    await flushPromises();
    const upCall = adminApi.get.mock.calls.find(
      ([url, cfg]) => url.includes("/admin-tier-upgrade-requests/") && cfg?.params?.status === "pending"
    );
    expect(upCall).toBeTruthy();
    expect(wrapper.text()).toContain("adminConsole.upgradeCappedNote");
  });

  // ── A2-40: approve collects an optional invoice amount and sends it ──
  // NOTE: assumes usePromptModal mirrors useConfirmModal's _settle(value)
  // resolver (both are module-level ref singletons per this file's header).
  // If the prompt API differs, this test fails loudly — fix the resolver here.
  it("A2-40 approve sends the prompted invoice amount", async () => {
    _routes = {
      "/leads/": { data: [] },
      "/admin-tier-upgrade-requests/": {
        data: [
          {
            id: 10,
            requested_at: "2026-01-01T10:00:00Z",
            status: "pending",
            tenant_slug: "chez-test",
            current_plan_name: "Free",
            target_plan_name: "Pro",
            payment_method: "cash",
            payment_reference: "TXN-1",
            target_plan_is_active: true,
          },
        ],
      },
    };
    wrapper = mountConsole();
    await flushPromises();
    const approveBtn = wrapper.findAll("button").find((b) => b.text().trim() === "adminConsole.approve");
    expect(approveBtn).toBeTruthy();
    await approveBtn.trigger("click");
    await flushPromises();
    const promptModal = usePromptModal();
    const settlePrompt = promptModal._settle ?? promptModal._resolve ?? promptModal.resolve;
    expect(typeof settlePrompt).toBe("function");
    settlePrompt("TXN-9"); // payment reference
    await flushPromises();
    settlePrompt("ok"); // admin note
    await flushPromises();
    settlePrompt("499.00"); // invoice amount
    await flushPromises();
    const putCall = adminApi.put.mock.calls.find(([url]) =>
      url.includes("/admin-tier-upgrade-requests/10/decision/")
    );
    expect(putCall).toBeTruthy();
    expect(putCall[1]).toEqual(expect.objectContaining({ decision: "approve", invoice_amount: 499 }));
  });

  // ── A2-41: alerts fetch 200, page at 30, and surface the cap ──
  it("A2-41 alerts show the count line and the cap note past 200", async () => {
    const rows = Array.from({ length: 200 }, (_, i) => ({
      id: 200 + i,
      name: `Alert Lead ${i}`,
      status: "new",
      tenant_slug: "chez-test",
      phone: "0600000000",
      email: "a@example.com",
      reminder_count: 0,
      created_at: "2026-01-01T10:00:00Z",
      follow_up_due_at: "2026-01-01T10:30:00Z",
      sla_state: "overdue",
    }));
    _routes = {
      "/leads/": { data: [] },
      "/admin-tier-upgrade-requests/": { data: [] },
      "/admin-reservation-alerts/": {
        data: {
          results: rows,
          counts: { overdue: 250, due_soon: 0, total_alerts: 250 },
          thresholds: { overdue_minutes: 30, due_soon_minutes: 10 },
        },
      },
      "/provision-jobs/": { data: [] },
      "/admin-audit-logs/": { data: { results: [], pagination: { page: 1, total: 0, total_pages: 1, has_next: false, has_prev: false } } },
    };
    wrapper = mountConsole();
    await flushPromises();
    await switchView("adminConsole.reservationFollowUpSla");
    expect(wrapper.text()).toContain("adminConsole.alertsShowing");
    expect(wrapper.text()).toContain("adminConsole.alertsCappedNote");
    // Page 1 shows the first 30 of the 200 fetched rows (paging, not a silent cut).
    expect(wrapper.text()).toContain("Alert Lead 0");
    expect(wrapper.text()).not.toContain("Alert Lead 199");
  });

  // ── A2-42: audit filters are sent as ?action= / ?tenant= / ?q= ──
  it("A2-42 audit filters send action/tenant/q params", async () => {
    _routes = {
      "/leads/": { data: [] },
      "/admin-tier-upgrade-requests/": { data: [] },
      "/admin-reservation-alerts/": { data: { results: [], counts: { overdue: 0, due_soon: 0, total_alerts: 0 }, thresholds: {} } },
      "/provision-jobs/": { data: [] },
      "/admin-audit-logs/": { data: { results: [], pagination: { page: 1, total: 0, total_pages: 1, has_next: false, has_prev: false } } },
    };
    wrapper = mountConsole();
    await flushPromises();
    await switchView("adminConsole.reservationFollowUpSla");
    wrapper.vm.adminPanels.audit = true;
    await wrapper.vm.$nextTick();
    await flushPromises();
    const searchInput = wrapper.find('input[placeholder="adminConsole.auditSearchPlaceholder"]');
    expect(searchInput.exists()).toBe(true);
    await searchInput.setValue("lead_provisioned");
    const applyBtn = wrapper.findAll("button").find((b) => b.text().trim() === "adminConsole.auditApplyFilters");
    await applyBtn.trigger("click");
    await flushPromises();
    const auditCall = adminApi.get.mock.calls.find(
      ([url, cfg]) => url.includes("/admin-audit-logs/") && cfg?.params?.q === "lead_provisioned"
    );
    expect(auditCall).toBeTruthy();
  });

  // ── A2-43: tenant search sends ?q= ──
  it("A2-43 tenant search sends the q param", async () => {
    _routes = {
      "/leads/": { data: [] },
      "/admin-tier-upgrade-requests/": { data: [] },
      "/admin-tenants/": {
        data: [
          { id: 7, name: "Chez Test", slug: "chez-test", lifecycle_status: "active", plan_name: "Pro", primary_domain: "chez-test.example.com", owner_username: "owner", subscription_end_date: null },
        ],
      },
    };
    wrapper = mountConsole();
    await flushPromises();
    await switchView("adminConsole.tenantLifecycleControls");
    const searchInput = wrapper.find('input[placeholder="adminConsole.tenantSearchPlaceholder"]');
    expect(searchInput.exists()).toBe(true);
    await searchInput.setValue("chez");
    const applyBtn = wrapper.findAll("button").find((b) => b.text().trim() === "adminConsole.tenantSearchApply");
    await applyBtn.trigger("click");
    await flushPromises();
    const tenantCall = adminApi.get.mock.calls.find(
      ([url, cfg]) => url.includes("/admin-tenants/") && cfg?.params?.q === "chez"
    );
    expect(tenantCall).toBeTruthy();
  });

  // ── A2-44 + A2-45: delivery save error surfaces in the drawer; dirty close confirms ──
  const mountWithDeliveryTenant = async () => {
    _routes = {
      "/leads/": { data: [] },
      "/admin-tier-upgrade-requests/": { data: [] },
      "/admin-tenants/7/delivery/": {
        data: {
          tenant: { id: 7, slug: "chez-test", name: "Chez Test" },
          delivery: {
            delivery_fee: "20.00",
            delivery_base_fee: "5.00",
            delivery_per_km: "1.00",
            delivery_free_over: "0",
            delivery_minimum_order: "0",
            delivery_radius_km: null,
            delivery_zone_description: "",
            delivery_commission_pct: "10",
            marketplace_commission_pct: "0.15",
            platform_delivery_enabled: false,
          },
        },
      },
      "/admin-tenants/": {
        data: [
          { id: 7, name: "Chez Test", slug: "chez-test", lifecycle_status: "active", plan_name: "Pro", primary_domain: "chez-test.example.com", owner_username: "owner", subscription_end_date: null },
        ],
      },
    };
    wrapper = mountConsole();
    await flushPromises();
    await switchView("adminConsole.tenantLifecycleControls");
    const deliveryBtn = wrapper.findAll("button").find((b) => b.text() === "adminConsole.delivery.button");
    expect(deliveryBtn).toBeTruthy();
    await deliveryBtn.trigger("click");
    await flushPromises();
    return wrapper.findComponent({ name: "AdminConsoleDeliveryPricingDrawer" });
  };

  it("A2-44 a failed delivery save surfaces an error on the drawer", async () => {
    const drawer = await mountWithDeliveryTenant();
    expect(drawer.exists()).toBe(true);
    adminApi.patch.mockRejectedValueOnce(new Error("Invalid delivery_commission_pct (0–100)"));
    await drawer.vm.$emit("submit");
    await flushPromises();
    expect(drawer.props("error")).toBeTruthy();
  });

  it("A2-45 closing the delivery drawer with unsaved edits asks first", async () => {
    const drawer = await mountWithDeliveryTenant();
    expect(drawer.exists()).toBe(true);
    wrapper.vm.deliveryForm.delivery_fee = 99;
    await wrapper.vm.$nextTick();
    await drawer.vm.$emit("close");
    await flushPromises();
    expect(useConfirmModal().visible.value).toBe(true);
    const { _settle } = useConfirmModal();
    _settle(true);
    await flushPromises();
    expect(wrapper.vm.deliveryModal.open).toBe(false);
  });

  // ── A2-46: live orders poll while open; the modal gets the true count + cap ──
  it("A2-46 live orders poll while open and receive the true count", async () => {
    vi.useFakeTimers();
    _routes = {
      "/leads/": { data: [] },
      "/admin-tier-upgrade-requests/": { data: [] },
      "/admin-tenants/": {
        data: [
          { id: 7, name: "Chez Test", slug: "chez-test", lifecycle_status: "active", plan_name: "Pro", primary_domain: "chez-test.example.com", owner_username: "owner", subscription_end_date: null },
        ],
      },
      "/admin/tenants/7/live-orders/": {
        data: {
          results: [{ order_number: "1", status: "pending", order_type: "delivery", total: "10", currency: "MAD", created_at: "2026-01-01T10:00:00Z", customer_phone: "" }],
          active_order_count: 250,
          capped: true,
          limit: 200,
        },
      },
    };
    wrapper = mountConsole();
    await flushPromises();
    await switchView("adminConsole.tenantLifecycleControls");
    const liveBtn = wrapper.findAll("button").find((b) => b.text().includes("adminConsole.liveOrders.button"));
    expect(liveBtn).toBeTruthy();
    await liveBtn.trigger("click");
    await flushPromises();
    const modal = wrapper.findComponent({ name: "AdminConsoleLiveOrdersModal" });
    expect(modal.exists()).toBe(true);
    expect(modal.props("count")).toBe(250);
    expect(modal.props("capped")).toBe(true);
    const callsBefore = adminApi.get.mock.calls.filter(([url]) => url.includes("/live-orders/")).length;
    await vi.advanceTimersByTimeAsync(30000);
    await flushPromises();
    const callsAfter = adminApi.get.mock.calls.filter(([url]) => url.includes("/live-orders/")).length;
    expect(callsAfter).toBeGreaterThan(callsBefore);
  });

  // ── A2-47: jobs total header + retry re-runs the provision path ──
  it("A2-47 jobs receive the true total and retry re-provisions the failed lead", async () => {
    const failedJob = { id: 5, lead_id: 7, lead_name: "Chez Test", tenant_slug: "", status: "failed", log: "boom", created_at: "2026-01-01T10:00:00Z", updated_at: "2026-01-01T10:00:00Z" };
    _routes = {
      "/leads/": { data: [] },
      "/admin-tier-upgrade-requests/": { data: [] },
      "/admin-reservation-alerts/": { data: { results: [], counts: { overdue: 0, due_soon: 0, total_alerts: 0 }, thresholds: {} } },
      "/provision-jobs/": { data: [failedJob], headers: { "x-total-count": "250" } },
      "/admin-audit-logs/": { data: { results: [], pagination: { page: 1, total: 0, total_pages: 1, has_next: false, has_prev: false } } },
    };
    wrapper = mountConsole();
    await flushPromises();
    await switchView("adminConsole.reservationFollowUpSla");
    const jobs = wrapper.findComponent({ name: "AdminConsoleProvisioningJobs" });
    expect(jobs.exists()).toBe(true);
    expect(jobs.props("total")).toBe(250);
    await jobs.vm.$emit("retry", failedJob);
    await flushPromises();
    expect(useConfirmModal().visible.value).toBe(true);
    const { _settle } = useConfirmModal();
    adminApi.put.mockResolvedValue({ data: { tenant_url: "https://chez-test.example.com", tenant: "chez-test" } });
    _settle(true);
    await flushPromises();
    expect(adminApi.put).toHaveBeenCalledWith("/lead-provision/7/", expect.anything());
  });

  // ── A2-49: dirty plan flags show an inline notice, not the page-top error ──
  it("A2-49 refreshing plan flags with unsaved changes shows an inline notice", async () => {
    _routes = {
      "/leads/": { data: [] },
      "/admin-tier-upgrade-requests/": { data: [] },
      "/admin-plan-feature-flags/": {
        data: { plans: [{ plan_code: "pro", plan_name: "Pro", plan_is_active: true, feature_flags: [{ key: "x", label: "X", description: "", enabled: false, config: null }] }] },
      },
    };
    wrapper = mountConsole();
    await flushPromises();
    await switchView("adminConsole.planFeatureFlags");
    // STAGING FIX (G3b W10): the flags list renders only behind the collapsed
    // planFlags panel (adminPanels.planFlags starts false) — expand it first,
    // or no checkbox exists to check.
    const showFlagsBtn = wrapper.findAll("button").find((b) => b.text().trim() === "adminConsole.show");
    expect(showFlagsBtn).toBeTruthy();
    await showFlagsBtn.trigger("click");
    await flushPromises();
    const checkbox = wrapper.find('input[type="checkbox"]');
    expect(checkbox.exists()).toBe(true);
    await checkbox.setChecked(true);
    await flushPromises();
    expect(wrapper.vm.planFlagDirtyKeys.size).toBe(1);
    const refreshBtn = wrapper.findAll("button").find((b) => b.text().trim() === "common.refresh *");
    expect(refreshBtn).toBeTruthy();
    await refreshBtn.trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("adminConsole.unsavedFlagChanges");
    expect(wrapper.vm.error).toBeFalsy();
  });

  // ── A2-50: monitoring Refresh fetches collapsed panels too ──
  it("A2-50 monitoring Refresh fetches alerts, jobs and audit even when collapsed", async () => {
    _routes = {
      "/leads/": { data: [] },
      "/admin-tier-upgrade-requests/": { data: [] },
      "/admin-reservation-alerts/": { data: { results: [], counts: { overdue: 0, due_soon: 0, total_alerts: 0 }, thresholds: {} } },
      "/provision-jobs/": { data: [] },
      "/admin-audit-logs/": { data: { results: [], pagination: { page: 1, total: 0, total_pages: 1, has_next: false, has_prev: false } } },
    };
    wrapper = mountConsole();
    await flushPromises();
    await switchView("adminConsole.reservationFollowUpSla");
    wrapper.vm.adminPanels.alerts = false;
    wrapper.vm.adminPanels.jobs = false;
    wrapper.vm.adminPanels.audit = false;
    await wrapper.vm.$nextTick();
    const countCalls = (frag) => adminApi.get.mock.calls.filter(([url]) => url.includes(frag)).length;
    const before = {
      alerts: countCalls("/admin-reservation-alerts/"),
      jobs: countCalls("/provision-jobs/"),
      audit: countCalls("/admin-audit-logs/"),
    };
    const headerRefresh = wrapper.findAll("button").find((b) => b.text().trim() === "common.refresh");
    expect(headerRefresh).toBeTruthy();
    await headerRefresh.trigger("click");
    await flushPromises();
    expect(countCalls("/admin-reservation-alerts/")).toBeGreaterThan(before.alerts);
    expect(countCalls("/provision-jobs/")).toBeGreaterThan(before.jobs);
    expect(countCalls("/admin-audit-logs/")).toBeGreaterThan(before.audit);
  });

  // ── A2-51: import files over 2 MB are rejected before parsing ──
  it("A2-51 an oversize import file is rejected before any API call", async () => {
    _routes = {
      "/leads/": { data: [] },
      "/admin-tier-upgrade-requests/": { data: [] },
      "/admin-tenants/": {
        data: [
          { id: 7, name: "Chez Test", slug: "chez-test", lifecycle_status: "active", plan_name: "Pro", primary_domain: "chez-test.example.com", owner_username: "owner", subscription_end_date: null },
        ],
      },
    };
    wrapper = mountConsole();
    await flushPromises();
    await switchView("adminConsole.tenantLifecycleControls");
    const bigFile = new File([new ArrayBuffer(2 * 1024 * 1024 + 1)], "big.json", { type: "application/json" });
    await wrapper.vm.handleTenantImportFile(
      { id: 7, slug: "chez-test" },
      { target: { files: [bigFile], value: "" } }
    );
    await flushPromises();
    expect(adminApi.post).not.toHaveBeenCalled();
    expect(wrapper.vm.error).toBeTruthy();
  });

  // ── A2-53: no emoji on the Live orders button; AppIcon eye is used ──
  it("A2-53 the Live orders button uses AppIcon eye, not the emoji", async () => {
    _routes = {
      "/leads/": { data: [] },
      "/admin-tier-upgrade-requests/": { data: [] },
      "/admin-tenants/": {
        data: [
          { id: 7, name: "Chez Test", slug: "chez-test", lifecycle_status: "active", plan_name: "Pro", primary_domain: "chez-test.example.com", owner_username: "owner", subscription_end_date: null },
        ],
      },
    };
    wrapper = mountConsole();
    await flushPromises();
    await switchView("adminConsole.tenantLifecycleControls");
    expect(wrapper.text()).not.toContain("\u{1F441}");
    const eyeIcons = wrapper
      .findAllComponents({ name: "AppIcon" })
      .filter((c) => c.props("name") === "eye");
    expect(eyeIcons.length).toBeGreaterThanOrEqual(1);
  });
});
