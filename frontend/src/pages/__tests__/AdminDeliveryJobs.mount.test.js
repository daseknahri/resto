/**
 * Mount smoke test for AdminDeliveryJobs.vue (the platform-admin delivery-jobs
 * monitor, ~233 lines — every delivery job across all tenants: status, driver,
 * restaurant, payout, live poll).
 *
 * WHY: this is the app's recurring production bug class — an admin/ops page
 * white-screens because a setup()-time error (a TDZ ReferenceError, an undefined
 * lookup, an unguarded browser API, a bad Intl currency call) throws inside
 * <script setup> and was never caught by a test. AdminDeliveryJobs' setup() wires
 * one composable (useI18n), builds `fmtMoney` (an Intl.NumberFormat currency:MAD
 * over currentLocale.value) and `fmtDate` (Intl.DateTimeFormat), maps status →
 * label (with the at_restaurant branch delegating to the pure `pickupLabelKey`
 * helper), and runs an onMounted that fires a single GET /admin/delivery-jobs/,
 * registers a 20s setInterval poll, and adds a document 'visibilitychange'
 * listener. shallowMount runs the page's OWN setup() + own template (the header,
 * the status-filter chips, and — in the loaded path — BOTH the desktop jobs table
 * AND the mobile card list, each a v-for over `jobs`) while auto-stubbing the only
 * child (AppIcon), so any setup-time crash fails CI here instead of shipping a
 * blank page.
 *
 * Pattern-faithful to pages/__tests__/AdminRides.mount.test.js +
 * AdminCustomers.mount.test.js (URL-routed api mock + real pinia + mocked useI18n),
 * with the page-specific differences verified against the source:
 *   1. The api boundary is ONLY `lib/api` (`import api from '../lib/api'`, line 139
 *      — grep confirms there is NO `lib/adminApi` on this page, unlike AdminRides).
 *      One mocked module, one URL-routed matcher. onMounted GETs
 *      /admin/delivery-jobs/ (with a `{ params }` arg the matcher ignores). The
 *      list handler is `Array.isArray(res.data) ? res.data : (res.data?.results
 *      || [])`, so the default `{ data: {} }` → not-an-array → results undefined →
 *      `[]` → the empty-state branch renders. The loaded payload is therefore a
 *      BARE ARRAY under `data` (not `{ results }`), unlike AdminCustomers.
 *   2. The page imports NOTHING from vue-router (`grep "router-link|RouterLink|
 *      vue-router"` → no match) and renders NO <router-link> — so there is no
 *      router module to mock and no vi.hoisted RouterLink stub is needed.
 *
 * Left REAL (jsdom-safe, and none touched at mount):
 *   - `pickupLabelKey` from lib/deliveryVocab — a pure (businessType, variant) →
 *     i18n-key string function, only reached from statusLabel when a job's status
 *     is 'at_restaurant'. Case 2 includes one such job so this real branch runs.
 * The page registers a 20s `setInterval(fetchJobs)` (POLL_MS, line 221) + a
 * document 'visibilitychange' listener at mount, and onUnmounted clears BOTH
 * (clearInterval + removeEventListener, lines 227-232). The 20s interval never
 * elapses within a test, and afterEach unmount runs that onUnmounted so neither the
 * timer nor the listener leaks between tests (mirrors AdminRides/OwnerHome afterEach).
 * No observer / scrollIntoView / WebSocket is used at mount, so no jsdom stubs are needed.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in AdminDeliveryJobs is { t, currentLocale } — the mock MUST
// return both or the setup destructure throws, and fmtMoney/fmtDate read
// `currentLocale.value` as the locale arg of Intl.NumberFormat(currency:MAD) /
// Intl.DateTimeFormat. t echoes the key (params appended) so assertions can target
// the stable i18n keys the page's own template renders.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// One URL-routed matcher for the single mocked axios instance (lib/api). The one
// mount GET (/admin/delivery-jobs/) defaults to `{ data: {} }` so the empty path
// renders; a test sets _routes to drive the loaded path. _routes/_match are
// module-level and referenced ONLY from the lazy vi.fn closures below (which run at
// CALL time, never in the hoisted factory body) → TDZ-safe. Exposes
// get/post/put/patch/delete for shape-parity (the page only uses api.get).
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// useConfirmModal is a vue-ref-only singleton (no DOM), but confirm() returns a
// promise that only the global ConfirmModal settles — in tests it would hang
// forever. Mock it with a controllable vi.fn (default: confirmed).
vi.mock("../../composables/useConfirmModal", () => {
  const fn = vi.fn(() => Promise.resolve(true));
  globalThis.__w6ConfirmMock = fn;
  return { useConfirmModal: () => ({ confirm: fn }) };
});

import AdminDeliveryJobs from "../AdminDeliveryJobs.vue";
import api from "../../lib/api";

const mountPage = () => shallowMount(AdminDeliveryJobs);

// A realistic delivery-job row as the /admin/delivery-jobs/ list ships it:
// order_number, tenant name/id, a nested driver object, business_type, status, a
// STRING driver_payout (as the API serializes decimals), and a created_at ISO — the
// exact fields the table + card-list v-fors read.
const job = (overrides = {}) => ({
  id: 9001,
  order_number: "1042",
  tenant_id: 3,
  tenant_name: "Pizza Palace",
  driver: { id: 7, name: "Mohamed Driver", phone: "0622334455" },
  business_type: "restaurant",
  status: "delivered",
  driver_payout: "18.50",
  created_at: "2026-02-01T10:25:00Z",
  ...overrides,
});

describe("AdminDeliveryJobs — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // TRAP: any localStorage-backed store (staleCache) must start clean so a cache
    // write in one test can't be served as still-"fresh" to the next.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // AdminDeliveryJobs registers a 20s setInterval poll + a 'visibilitychange'
    // listener at mount; unmount runs onUnmounted → clearInterval +
    // removeEventListener so neither leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default mount: empty jobs list ────────────────────────────────────
  // The core guard: the whole setup() (the useI18n wire, fmtMoney + fmtDate, the
  // status-label maps, the onMounted GET /admin/delivery-jobs/ + the interval/
  // listener registration) and the whole own-template must render with empty data
  // and not throw. The H1 title is the always-rendered crash anchor; the empty-state
  // key confirms the jobs fetch resolved down its empty branch (default { data: {} }
  // → not an array → results undefined → [] → !jobs.length → empty state).
  it("mounts with an empty jobs list (default mount GET) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises(); // onMounted → fetchJobs → GET /admin/delivery-jobs/

    expect(wrapper.exists()).toBe(true);
    // Header H1 (always rendered, page's own template) — the crash-guard anchor.
    expect(wrapper.text()).toContain("adminDeliveryJobs.title");
    // Empty /admin/delivery-jobs/ (default { data: {} } → jobs.length 0) → the
    // empty-state branch, confirming the jobs-table path resolved without throwing.
    expect(wrapper.text()).toContain("adminDeliveryJobs.empty");
  });

  // ── (2) loaded mount: real jobs (assigned+delivered + unassigned+searching + at_restaurant) ──
  // Drives the page's OWN loaded templates (no child delegation): the desktop jobs
  // table v-for AND the mobile card-list v-for over `jobs` (order_number /
  // tenant_name-or-#id / driver-name-or-phone-or-unassigned branch /
  // statusClass+statusLabel — incl. the at_restaurant → pickupLabelKey branch /
  // fmtMoney(driver_payout) Intl-currency + fmtDate(created_at) Intl-date). These
  // are the array-render + Intl paths that only run with a non-empty jobs array.
  it("mounts with a loaded jobs list (assigned + unassigned + at_restaurant rows, string payouts) without a crash", async () => {
    _routes = {
      "/admin/delivery-jobs/": {
        data: [
          job({ id: 9001, status: "delivered", tenant_name: "Pizza Palace" }),
          job({
            id: 9002,
            order_number: "1043",
            tenant_name: "", // → falls back to '#' + tenant_id in the template
            tenant_id: 5,
            driver: null, // exercises the "unassigned" v-else branch
            status: "searching",
            driver_payout: "0.00",
            created_at: "2026-02-02T09:00:00Z",
          }),
          job({
            id: 9003,
            order_number: "1044",
            driver: { id: 8, phone: "0633445566" }, // no name → phone fallback
            status: "at_restaurant", // → statusLabel delegates to pickupLabelKey
            business_type: "pharmacy", // → deliveryVocab.atPickupPharmacy
            driver_payout: "12.00",
          }),
        ],
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Header still renders.
    expect(text).toContain("adminDeliveryJobs.title");
    // Loaded table branch: colOrder renders ONLY in the v-else data-views block
    // (jobs.length && !loading && !fetchError), so it proves the loaded path ran.
    expect(text).toContain("adminDeliveryJobs.colOrder");
    // A job row rendered from the fetched payload (own-template v-for, not a stubbed
    // child) — the loaded discriminator (appears nowhere in the empty/chrome path).
    expect(text).toContain("Pizza Palace");
    // status:'delivered' → statusLabel via the static STATUS_LABELS map.
    expect(text).toContain("adminDeliveryJobs.statusDelivered");
    // The driver-less second job → the "unassigned" label, which renders ONLY inside
    // the jobs v-for's `v-else` (never in the header/chips), proving the mixed-row
    // array-render path ran.
    expect(text).toContain("adminDeliveryJobs.unassigned");
    // The at_restaurant + pharmacy job → statusLabel delegates to the real
    // pickupLabelKey helper → deliveryVocab.atPickupPharmacy, proving that branch ran.
    expect(text).toContain("deliveryVocab.atPickupPharmacy");
  });
});

/**
 * MERGE NOTE (Run 8 G3a): append this describe block to
 * frontend/src/pages/__tests__/AdminDeliveryJobs.mount.test.js (after pulling it),
 * adapting the _routes / mount helper names to that file's existing ones.
 * Assumes the file's existing URL-routed api mock + mocked useI18n (keys render
 * as `ns.key` / `ns.key({json})`, as in AdminRides.mount.test.js).
 *
 * Covers:
 *   A2-06 — background refresh keeps rows (no skeleton flash); a failed
 *           background refresh keeps rows and shows the retry banner.
 *   A2-07 — envelope total + cap note + pagination sends page/page_size.
 */

const findButton = (wrapper, text) =>
  wrapper.findAll("button").find((b) => b.text().includes(text));

const jobRow = (id, order_number) => ({
  id,
  order_number,
  tenant_id: 7,
  tenant_name: "Chez Test",
  driver: null,
  status: "searching",
  driver_payout: "25.00",
  created_at: "2026-11-01T10:00:00Z",
  business_type: "restaurant",
});

describe("AdminDeliveryJobs — refresh + pagination (A2-06/A2-07)", () => {
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

  const mountWith = async (jobsPayload) => {
    _routes = { "/admin/delivery-jobs/": { data: jobsPayload } };
    wrapper = mountPage();
    await flushPromises();
    return wrapper;
  };

  it("shows the server total and the cap note; Next sends page 2 (A2-07)", async () => {
    await mountWith({
      results: [jobRow(1, "A1"), jobRow(2, "A2")],
      total: 250,
      page: 1,
      page_size: 100,
    });
    expect(wrapper.text()).toContain('adminDeliveryJobs.totalLabel({"count":250})');
    expect(wrapper.text()).toContain('adminDeliveryJobs.showingLatest({"count":2,"total":250})');
    expect(wrapper.text()).toContain('adminDeliveryJobs.pageOf({"page":1,"pages":3})');
    await findButton(wrapper, "adminDeliveryJobs.nextPage").trigger("click");
    await flushPromises();
    expect(api.get).toHaveBeenCalledWith(
      "/admin/delivery-jobs/",
      expect.objectContaining({ params: expect.objectContaining({ page: 2, page_size: 100 }) }),
    );
  });

  it("background refresh keeps the loaded rows visible (A2-06)", async () => {
    await mountWith({
      results: [jobRow(1, "A1")],
      total: 1,
      page: 1,
      page_size: 100,
    });
    expect(wrapper.text()).toContain("#A1");
    const pending = new Promise(() => {});
    api.get.mockReturnValueOnce(pending);
    await findButton(wrapper, "adminDeliveryJobs.refresh").trigger("click");
    await flushPromises();
    // Rows stay rendered while the background refresh is in flight — no skeletons.
    expect(wrapper.text()).toContain("#A1");
    expect(wrapper.find(".ui-skeleton").exists()).toBe(false);
  });

  it("failed background refresh keeps rows and shows the retry banner (A2-06)", async () => {
    await mountWith({
      results: [jobRow(1, "A1")],
      total: 1,
      page: 1,
      page_size: 100,
    });
    api.get.mockRejectedValueOnce(new Error("poll down"));
    await findButton(wrapper, "adminDeliveryJobs.refresh").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("#A1");
    expect(wrapper.text()).toContain("adminDeliveryJobs.refreshFailed");
  });
});

/**
 * Run 8 G3b W6 — A2-14 / A2-16 / A2-17 / A2-18 / A2-19 / A2-20.
 * Appended (never overwriting the base + G3a blocks above).
 */
const w6job = (overrides = {}) => ({
  id: 9001,
  order_number: "1042",
  tenant_id: 3,
  tenant_name: "Pizza Palace",
  driver: { id: 7, name: "Mohamed Driver", phone: "0622334455" },
  business_type: "restaurant",
  status: "delivered",
  driver_payout: "18.50",
  delivery_fee: "25.00",
  platform_commission: "6.50",
  distance_km: 3.2,
  pickup_address: "12 Rue Test, Casablanca",
  delivery_address: "8 Ave Client, Casablanca",
  created_at: "2026-02-01T10:25:00Z",
  assigned_at: "2026-02-01T10:30:00Z",
  picked_up_at: null,
  delivered_at: null,
  failed_at: null,
  failure_reason: "",
  failure_note: "",
  resolution: "",
  ...overrides,
});

describe("AdminDeliveryJobs — W6 gaps (A2-14/A2-16/A2-17/A2-18/A2-19/A2-20)", () => {
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

  const mountWithJobs = async (jobsPayload, tenantsPayload) => {
    _routes = { "/admin/delivery-jobs/": { data: jobsPayload } };
    if (tenantsPayload) _routes["/admin-tenants/"] = { data: tenantsPayload };
    wrapper = mountPage();
    await flushPromises();
    return wrapper;
  };

  const payoutCell = (amount) =>
    wrapper.findAll("td").find((td) => td.text().includes(amount));

  it("A2-14: an unknown status falls back to the translated unknown label, not Searching", async () => {
    await mountWithJobs([w6job({ status: "bogus_future" })]);
    expect(wrapper.text()).toContain("adminDeliveryJobs.statusUnknown");
  });

  it("A2-16: payout is green only for delivered jobs; other statuses are neutral + labelled if-delivered", async () => {
    await mountWithJobs([
      w6job({ id: 9001, status: "delivered", driver_payout: "18.50" }),
      w6job({ id: 9002, order_number: "1043", status: "failed", driver_payout: "12.00" }),
    ]);
    expect(payoutCell("18.50").classes()).toContain("text-emerald-300");
    expect(payoutCell("12.00").classes()).toContain("text-slate-400");
    expect(wrapper.text()).toContain("adminDeliveryJobs.payoutIfDelivered");
  });

  it("A2-16: a delivered-only board never shows the if-delivered label", async () => {
    await mountWithJobs([w6job({ status: "delivered" })]);
    expect(wrapper.text()).not.toContain("adminDeliveryJobs.payoutIfDelivered");
  });

  it("A2-17: a failed job shows its translated failure reason, note and resolution", async () => {
    await mountWithJobs([
      w6job({
        status: "failed",
        failure_reason: "customer_no_show",
        failure_note: "No answer at door",
        resolution: "redispatched",
      }),
    ]);
    const text = wrapper.text();
    expect(text).toContain(
      'adminDeliveryJobs.failureReason({"reason":"adminDeliveryJobs.failureCustomerNoShow"})',
    );
    expect(text).toContain('adminDeliveryJobs.failureNote({"note":"No answer at door"})');
    expect(text).toContain(
      'adminDeliveryJobs.resolutionLine({"resolution":"adminDeliveryJobs.resolutionRedispatched"})',
    );
  });

  it("A2-18: tenant filter sends ?tenant_id= to the list endpoint", async () => {
    await mountWithJobs(
      { results: [w6job()], total: 1, page: 1, page_size: 100 },
      { results: [{ id: 3, name: "Pizza Palace" }] },
    );
    const select = wrapper.find("#jobs-tenant-filter");
    expect(select.exists()).toBe(true);
    expect(select.text()).toContain("Pizza Palace");
    await select.setValue("3");
    await flushPromises();
    expect(api.get).toHaveBeenCalledWith(
      "/admin/delivery-jobs/",
      expect.objectContaining({ params: expect.objectContaining({ tenant_id: "3" }) }),
    );
  });

  it("A2-18: search filters the loaded page by order / restaurant / driver", async () => {
    await mountWithJobs([
      w6job({ id: 9001, order_number: "1042", tenant_name: "Pizza Palace" }),
      w6job({ id: 9002, order_number: "1043", tenant_name: "Chez Test", driver: { id: 8, name: "Karim" } }),
    ]);
    expect(wrapper.text()).toContain("Chez Test");
    await wrapper.find("#jobs-search").setValue("pizza");
    await flushPromises();
    expect(wrapper.text()).toContain("Pizza Palace");
    expect(wrapper.text()).not.toContain("Chez Test");
  });

  it("A2-18: Details expands a job with driver, addresses and timeline", async () => {
    await mountWithJobs([w6job({ status: "assigned" })]);
    await findButton(wrapper, "adminDeliveryJobs.details").trigger("click");
    await flushPromises();
    const text = wrapper.text();
    expect(text).toContain("adminDeliveryJobs.detailTimeline");
    expect(text).toContain("12 Rue Test, Casablanca");
    expect(text).toContain("8 Ave Client, Casablanca");
  });

  it("A2-19: Re-dispatch on a failed job confirms, POSTs the action and updates the row", async () => {
    const failed = w6job({
      status: "failed",
      failure_reason: "customer_no_show",
      failure_note: "No answer at door",
      resolution: "",
    });
    await mountWithJobs([failed]);
    await findButton(wrapper, "adminDeliveryJobs.details").trigger("click");
    await flushPromises();
    api.post.mockResolvedValueOnce({
      data: {
        ok: true,
        resolution: "redispatched",
        job: { ...failed, status: "searching", failure_reason: "", failure_note: "", resolution: "redispatched" },
      },
    });
    await findButton(wrapper, "adminDeliveryJobs.redispatch").trigger("click");
    await flushPromises();
    expect(globalThis.__w6ConfirmMock).toHaveBeenCalledWith(
      expect.objectContaining({ title: "adminDeliveryJobs.redispatchConfirmTitle" }),
    );
    expect(api.post).toHaveBeenCalledWith("/admin/delivery-jobs/9001/action/", { action: "redispatch" });
    // The row re-rendered as searching: the failure-reason line is gone.
    expect(wrapper.text()).not.toContain("adminDeliveryJobs.failureReason");
  });

  it("A2-19: Cancel on an active job POSTs cancel and the Cancel button leaves the row", async () => {
    const active = w6job({ status: "searching" });
    await mountWithJobs([active]);
    await findButton(wrapper, "adminDeliveryJobs.details").trigger("click");
    await flushPromises();
    api.post.mockResolvedValueOnce({
      data: { ok: true, resolution: "cancelled", job: { ...active, status: "cancelled" } },
    });
    await findButton(wrapper, "adminDeliveryJobs.cancelJob").trigger("click");
    await flushPromises();
    expect(api.post).toHaveBeenCalledWith("/admin/delivery-jobs/9001/action/", { action: "cancel" });
    expect(findButton(wrapper, "adminDeliveryJobs.cancelJob")).toBeUndefined();
  });

  it("A2-19: declining the confirm dialog posts nothing", async () => {
    await mountWithJobs([w6job({ status: "failed", failure_reason: "other" })]);
    await findButton(wrapper, "adminDeliveryJobs.details").trigger("click");
    await flushPromises();
    globalThis.__w6ConfirmMock.mockResolvedValueOnce(false);
    await findButton(wrapper, "adminDeliveryJobs.redispatch").trigger("click");
    await flushPromises();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("A2-20: with a status filter the chip shows the filtered count with its filter label", async () => {
    await mountWithJobs({
      results: [w6job({ status: "delivered" })],
      total: 250,
      page: 1,
      page_size: 100,
    });
    expect(wrapper.text()).toContain('adminDeliveryJobs.totalLabel({"count":250})');
    await findButton(wrapper, "adminDeliveryJobs.statusDelivered").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain(
      'adminDeliveryJobs.filteredTotalLabel({"count":250,"filter":"adminDeliveryJobs.statusDelivered"})',
    );
  });
});
