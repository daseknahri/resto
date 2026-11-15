/**
 * Mount smoke test for OwnerCustomers.vue (the owner customer-CRM page, ~739 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, an unguarded browser
 * API) was never caught by a test" (this pass already caught a real WaiterPage TDZ
 * white-screen). OwnerCustomers is a busy owner surface — an onMounted that fires
 * GET /owner/customers/, a summary/segment/tier chip trio built from computeds, a
 * debounced-search watcher, and a card v-for whose per-row helpers do real work
 * (initials(), formatAmount() via Intl.NumberFormat, formatDate() via
 * Intl.DateTimeFormat, parseFloat(wallet_balance), avg_review/trust_score
 * .toFixed(1), segment/tier class maps). Mounting runs all of that for real, so a
 * crash in setup() or the initial render fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerReservations.mount.test.js (the closest
 * proven shape: an owner page that imports NOTHING from 'vue-router'):
 *   - shallowMount (auto-stubs the only child component, AppIcon)
 *   - real pinia (the toast store runs for real) + a mocked lib/api
 *   - useI18n mocked to exactly { t } (the page's real destructure — verified: the
 *     page defines its OWN formatAmount/formatDate locally and pulls only `t`)
 *
 * NOT mocked / not needed (all verified against the source):
 *   - vue-router: the page imports nothing from it, so no mock / no vi.hoisted
 *     RouterLink stub is required (that stub is only needed when RouterLink is a
 *     static import, else the hoisted factory hits a "0 test" TDZ).
 *   - lib/adminApi: the page's only api boundary is the default export of lib/api.
 *   - No staleCache / interval / WebSocket / IntersectionObserver / scrollIntoView
 *     is touched at mount (the lone timer is the search-debounce setTimeout, armed
 *     only when searchQuery changes — never at mount). localStorage.clear() is kept
 *     as beforeEach hygiene and afterEach still unmounts, both as cheap insurance.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    // t returns the key verbatim (params, when present, are appended so the raw
    // key path is still asserted-on, e.g. ownerCustomers.resultCount).
    // formatAmount delegates to lib/intlFormatters.formatCurrencyString(
    // currentLocale.value,…), so currentLocale must be provided (ref-like { value }).
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: onMounted fires GET /owner/customers/. Default: everything
// resolves { data: {} } so the empty-state path renders. Tests set _routes to drive
// the loaded path. _routes/_match are plain (not vi.hoisted): they're only read
// lazily inside the vi.fn callback when api.get is invoked at mount — never during
// the hoisted factory's own evaluation — so there is no TDZ.
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

import OwnerCustomers from "../OwnerCustomers.vue";

const mountPage = () =>
  shallowMount(OwnerCustomers, {
    global: {
      // The grant-points modal lives in a <Teleport to="body">; it's closed at
      // mount so nothing teleports, but stub it to keep the render self-contained.
      stubs: { Teleport: { template: "<slot />" } },
    },
  });

// A realistic customer row with the fields the page's own template + per-row
// helpers read: name/segment/type (avatar + badge maps), order_count (tier map),
// total_spend/avg_order_value/currency (formatAmount), wallet_balance string
// (parseFloat), loyalty_points, avg_review/review_count + trust_score (.toFixed(1)),
// last_order_at (formatDate), phone/email (tel:/wa.me/mailto builders), owner_notes.
const customer = (overrides = {}) => ({
  id: 1,
  customer_id: 101,
  name: "Sara Bennani",
  type: "account",
  segment: "returning",
  phone: "+212612345678",
  email: "sara@example.com",
  order_count: 12,
  total_spend: 1450,
  avg_order_value: 120,
  currency: "MAD",
  wallet_balance: "75.50",
  loyalty_points: 340,
  avg_review: 4.5,
  review_count: 8,
  trust_score: 9.2,
  last_order_at: "2026-08-30T18:00:00Z",
  owner_notes: "Prefers spicy",
  ...overrides,
});

describe("OwnerCustomers — mount smoke", () => {
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

  // ── (1) empty / default mount ──────────────────────────────────────────────
  // The core guard: the onMounted loadCustomers(true) GET + the whole template
  // (header, controls, tier/segment chip computeds, empty state) must render with
  // empty data ({ data: {} } → results: []) and not throw.
  it("mounts with empty data (no customers) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (always rendered, outside every v-if) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerCustomers.title");
    expect(wrapper.text()).toContain("ownerCustomers.kicker");
    // loading resolves false + no filters set → the empty-state branch renders.
    expect(wrapper.text()).toContain("ownerCustomers.emptyState");
  });

  // ── (2) loaded state with a realistic customers payload ────────────────────
  // Drives the card v-for + every per-row helper (initials, segment/tier class
  // maps, formatAmount via Intl.NumberFormat, wallet parseFloat, avg_review/
  // trust_score .toFixed, formatDate) AND the summary chip trio — the own-template
  // paths that only run with a non-empty customers array + a summary object. The
  // second row (anonymous, undefined wallet, null review/trust, order_count 1)
  // exercises the alternate branches of those same guards.
  it("mounts with a loaded customers payload without a crash", async () => {
    _routes = {
      "/owner/customers/": {
        data: {
          results: [
            customer(),
            customer({
              id: 2,
              customer_id: 102,
              name: "Youssef Alami",
              type: "anonymous",
              segment: "new",
              order_count: 1,
              total_spend: 60,
              avg_order_value: 60,
              wallet_balance: undefined,
              loyalty_points: 0,
              avg_review: null,
              review_count: 0,
              trust_score: null,
              owner_notes: "",
            }),
          ],
          has_more: false,
          summary: { total: 2, new: 1, returning: 1, at_risk: 0 },
        },
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerCustomers.title");
    // The card v-for rendered both loaded rows (proves the loaded-list path +
    // every per-row helper ran clean).
    expect(wrapper.text()).toContain("Sara Bennani");
    expect(wrapper.text()).toContain("Youssef Alami");
  });
});

// ── S1-C / B-14 appended tests ──────────────────────────────────────────────
// Same page-aware trick as the ratings file: the base api mock ignores call
// params, so these tests replace api.get's implementation per test (get is a
// vi.fn; beforeEach's clearAllMocks only clears calls). The import below is
// hoisted, so it may sit here at the append point.
import api from "../../lib/api";

const findButtonByText = (w, text) =>
  w.findAll("button").find((b) => b.text().includes(text));

describe("OwnerCustomers — S1-C B-14 load-more failure (appended)", () => {
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

  const pageOne = () => ({
    data: {
      results: [
        customer(),
        customer({ id: 2, customer_id: 102, name: "Youssef Alami" }),
      ],
      has_more: true,
      summary: { total: 3, new: 1, returning: 1, at_risk: 0 },
    },
  });

  // ── (3) append-page failure: error + Retry shown, button kept, rows kept ───
  it("shows an error + Retry and keeps Load more when the next page fails", async () => {
    api.get.mockImplementation((url, opts) => {
      if ((opts?.params?.offset ?? 0) === 0) return Promise.resolve(pageOne());
      return Promise.reject(new Error("network down"));
    });

    wrapper = mountPage();
    await flushPromises();

    expect(wrapper.text()).toContain("Sara Bennani");
    expect(findButtonByText(wrapper, "ownerCustomers.loadMore").exists()).toBe(true);

    await findButtonByText(wrapper, "ownerCustomers.loadMore").trigger("click");
    await flushPromises();

    // The failure is no longer silent: inline error + explicit Retry, and the
    // Load more button stays visible for a retry (hasMore was not cleared).
    expect(wrapper.text()).toContain("ownerCustomers.loadMoreError");
    expect(findButtonByText(wrapper, "common.retry").exists()).toBe(true);
    expect(findButtonByText(wrapper, "ownerCustomers.loadMore").exists()).toBe(true);
    // Already-loaded rows are not lost by the failed append.
    expect(wrapper.text()).toContain("Sara Bennani");
    expect(wrapper.text()).toContain("Youssef Alami");
  });

  // ── (4) append-page success clears the error and ends the list ────────────
  it("appends the next page on Load more and clears any earlier error", async () => {
    let calls = 0;
    api.get.mockImplementation((url, opts) => {
      if ((opts?.params?.offset ?? 0) === 0) return Promise.resolve(pageOne());
      calls += 1;
      if (calls === 1) return Promise.reject(new Error("network down"));
      return Promise.resolve({
        data: {
          results: [customer({ id: 3, customer_id: 103, name: "Khadija Idrissi" })],
          has_more: false,
        },
      });
    });

    wrapper = mountPage();
    await flushPromises();

    // First attempt fails → error shown.
    await findButtonByText(wrapper, "ownerCustomers.loadMore").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("ownerCustomers.loadMoreError");

    // Retry via the inline Retry button succeeds → row appended, error gone,
    // Load more gone (has_more false), end-of-list count shown.
    await findButtonByText(wrapper, "common.retry").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Khadija Idrissi");
    expect(wrapper.text()).not.toContain("ownerCustomers.loadMoreError");
    expect(findButtonByText(wrapper, "ownerCustomers.loadMore")).toBeUndefined();
    expect(wrapper.text()).toContain("ownerCustomers.resultCount");
  });
});

describe("OwnerCustomers — S1-I B-15 wa.me links", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    // The B-14 describe above leaves a mockImplementation on api.get
    // (clearAllMocks does not remove implementations). Restore the base
    // URL-routed implementation or this describe renders pageOne() instead
    // of its own _routes seed (Sara default phone, summary total 3).
    api.get.mockRestore();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // B-15: a national-format guest-order phone ("06…") must link to
  // wa.me/212… — the raw-digits link wa.me/06… is dead. An E.164 phone links
  // unchanged. Asserted on the rendered href (wrapper.html), not the helper.
  it("builds wa.me links with the 212 country code for national-format phones (B-15)", async () => {
    _routes = {
      "/owner/customers/": {
        data: {
          results: [
            customer({ phone: "0678901234" }),
            customer({
              id: 2,
              customer_id: 102,
              name: "Youssef Alami",
              type: "anonymous",
              segment: "new",
              order_count: 1,
              total_spend: 60,
              avg_order_value: 60,
              wallet_balance: undefined,
              loyalty_points: 0,
              avg_review: null,
              review_count: 0,
              trust_score: null,
              owner_notes: "",
              phone: "+212612345678",
            }),
          ],
          has_more: false,
          summary: { total: 2, new: 1, returning: 1, at_risk: 0 },
        },
      },
    };

    wrapper = mountPage();
    await flushPromises();

    const html = wrapper.html();
    expect(html).toContain("https://wa.me/212678901234");
    expect(html).not.toContain("wa.me/0678901234");
    expect(html).toContain("https://wa.me/212612345678");
  });
});

// ── G4b-C (B-22 tier-tab counts / B-23 grant validation) — appended ─────────
// Imports are hoisted, so these resolve to the same (mocked api / real
// useConfirmModal) modules as the imports at the top of the file. useConfirmModal
// is left REAL, matching OwnerOrders: confirm() returns a promise settled by
// _settle(true/false) in the test, so the negative-grant gate is exercised
// without rendering a modal.
import { useConfirmModal } from "../../composables/useConfirmModal";
import { nextTick } from "vue";

describe("OwnerCustomers — G4b-C (B-22 / B-23)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    // The B-14 describe leaves a mockImplementation on api.get (clearAllMocks
    // does not remove implementations); restore the base URL-routed impl.
    api.get.mockRestore();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // Two loaded rows, server total 3, one more page to load: the tier tabs must
  // count the LOADED page only, while the segment "All" chip counts the server
  // total. Sara (12 orders) is VIP, Youssef (1 order) is New.
  const _mountTwoOfThree = async () => {
    _routes = {
      "/owner/customers/": {
        data: {
          results: [
            customer(),
            customer({
              id: 2,
              customer_id: 102,
              name: "Youssef Alami",
              type: "anonymous",
              segment: "new",
              order_count: 1,
              total_spend: 60,
              avg_order_value: 60,
              wallet_balance: undefined,
              loyalty_points: 0,
              avg_review: null,
              review_count: 0,
              trust_score: null,
              owner_notes: "",
            }),
          ],
          has_more: true,
          summary: { total: 3, new: 1, returning: 1, at_risk: 0 },
        },
      },
    };
    wrapper = mountPage();
    await flushPromises();
    expect(wrapper.text()).toContain("Sara Bennani");
    return wrapper;
  };

  // Open the grant-points modal for Sara (the only account-type row, so the
  // only "Grant points" button). Teleport is stubbed inline, so the modal
  // inputs are findable by id.
  const _openGrantModal = async () => {
    await _mountTwoOfThree();
    await findButtonByText(wrapper, "ownerCustomers.grantPointsBtn").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("ownerCustomers.grantPointsTitle");
    return wrapper.find("#grant-delta-101");
  };

  // ── B-22: tier tabs are labelled as loaded-page counts ───────────────────
  it("B-22: tier tabs count the loaded page (2) while segment All counts the server total (3), and the loaded-page note renders", async () => {
    await _mountTwoOfThree();
    expect(wrapper.text()).toContain("ownerCustomers.tierCountsNote");
    // The tier "All" tab and the segment "All" tab share the segmentAll label;
    // the tier row comes first in the DOM, so [0] is the tier tab (loaded 2)
    // and [1] is the segment tab (server total 3).
    const allTabs = wrapper
      .findAll("button")
      .filter((b) => b.text().includes("ownerCustomers.segmentAll"));
    expect(allTabs).toHaveLength(2);
    expect(allTabs[0].text()).toContain("(2)");
    expect(allTabs[1].text()).toContain("(3)");
    // Per-tier counts likewise cover the loaded rows only: 1 VIP, 1 New.
    expect(
      wrapper.findAll("button").find((b) => b.text().includes("ownerCustomers.tierVIP")).text()
    ).toContain("(1)");
    expect(
      wrapper.findAll("button").find((b) => b.text().includes("ownerCustomers.tierNew")).text()
    ).toContain("(1)");
  });

  // ── B-23: zero delta is rejected ─────────────────────────────────────────
  it("B-23: a zero delta is rejected with an inline error and posts nothing", async () => {
    const deltaInput = await _openGrantModal();
    await deltaInput.setValue("0");
    await findButtonByText(wrapper, "ownerCustomers.grantPointsSubmit").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("ownerCustomers.grantPointsZero");
    expect(api.post).not.toHaveBeenCalled();
  });

  // ── B-23: junk deltas are rejected (parseInt("10abc") used to yield 10) ──
  it("B-23: junk deltas (10abc, 10.5) are rejected with an inline error and post nothing", async () => {
    const deltaInput = await _openGrantModal();
    // "10abc" cannot be typed into a type=number input (jsdom sanitises it to
    // ""), so set the bound value directly — the submit button is disabled
    // only while loading, so set-then-click is safe here (see harness lessons).
    wrapper.vm.grantModal.delta = "10abc";
    await nextTick();
    await findButtonByText(wrapper, "ownerCustomers.grantPointsSubmit").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("ownerCustomers.grantPointsInvalid");
    expect(api.post).not.toHaveBeenCalled();
    // A fractional delta is junk too (whole numbers only).
    await deltaInput.setValue("10.5");
    await findButtonByText(wrapper, "ownerCustomers.grantPointsSubmit").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("ownerCustomers.grantPointsInvalid");
    expect(api.post).not.toHaveBeenCalled();
  });

  // ── B-23: a positive grant posts directly, with no confirm gate ──────────
  it("B-23: a positive grant posts the delta + reason with no confirm dialog", async () => {
    const deltaInput = await _openGrantModal();
    await deltaInput.setValue("25");
    await wrapper.find("#grant-reason-101").setValue("Good customer");
    await findButtonByText(wrapper, "ownerCustomers.grantPointsSubmit").trigger("click");
    await flushPromises();
    expect(useConfirmModal().visible.value).toBe(false);
    expect(api.post).toHaveBeenCalledWith("/owner/customers/101/loyalty-grant/", {
      delta: 25,
      reason: "Good customer",
    });
    expect(wrapper.text()).not.toContain("ownerCustomers.grantPointsTitle");
  });

  // ── B-23: a negative delta confirms first, then deducts ──────────────────
  it("B-23: a negative delta asks for confirmation and posts only after approval", async () => {
    const deltaInput = await _openGrantModal();
    await deltaInput.setValue("-5");
    await findButtonByText(wrapper, "ownerCustomers.grantPointsSubmit").trigger("click");
    await flushPromises();
    // No POST before the owner approves the confirm dialog.
    expect(api.post).not.toHaveBeenCalled();
    useConfirmModal()._settle(true);
    await flushPromises();
    await flushPromises();
    expect(api.post).toHaveBeenCalledWith("/owner/customers/101/loyalty-grant/", {
      delta: -5,
      reason: "",
    });
  });

  // ── B-23: declining the negative-grant confirm posts nothing ─────────────
  it("B-23: declining the negative-grant confirm posts nothing and leaves the modal open", async () => {
    const deltaInput = await _openGrantModal();
    await deltaInput.setValue("-5");
    await findButtonByText(wrapper, "ownerCustomers.grantPointsSubmit").trigger("click");
    await flushPromises();
    useConfirmModal()._settle(false);
    await flushPromises();
    expect(api.post).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("ownerCustomers.grantPointsTitle");
  });
});
