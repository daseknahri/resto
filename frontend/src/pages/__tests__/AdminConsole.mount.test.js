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
