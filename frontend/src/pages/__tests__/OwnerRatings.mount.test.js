/**
 * Mount smoke test for OwnerRatings.vue (the owner ratings/reviews page, ~473 lines).
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined map
 * access, bad import) was never caught by a test". Mounting the page runs its real
 * setup() + async onMounted(fetchRatings) for real, so a crash in any of it —
 * setup, the fetch, or the data-driven computeds/v-fors (summary / scoreCounts /
 * scorePercent / filtered) — fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js +
 * pages/__tests__/SuperAppHub.mount.test.js (URL-routed api mock + vi.hoisted
 * RouterLink stub):
 *   - shallowMount (auto-stubs AppIcon)
 *   - real pinia (the toast store runs for real) + a mocked lib/api
 *   - useI18n + vue-router mocked
 *
 * The useConfirmModal composable and the staleCache lib are left REAL: they are
 * jsdom-safe (useConfirmModal is pure module-level refs; staleCache falls through
 * to the mocked network on an empty cache). OwnerRatings reads/writes staleCache
 * under key "owner.ratings", so beforeEach clears localStorage — otherwise test
 * 1's write is served to test 2 as a still-fresh cache and its /owner/ratings/
 * mock payload is never read. No intervals/observers/WebSocket run at mount, but
 * afterEach unmounts for hygiene.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatNumber: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: onMounted fires GET /owner/ratings/. Default: everything
// resolves empty so the empty-state path renders. Tests set _routes to drive the
// loaded path.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// OwnerRatings imports { RouterLink } from 'vue-router'.
// vi.hoisted: the vi.mock('vue-router') factory below is hoisted above the imports
// and runs during import evaluation — before a plain `const` in the file body would
// initialize — so referencing a plain const there hits the TDZ ("0 test" collection
// error). vi.hoisted makes the stub available to the hoisted factory.
const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import OwnerRatings from "../OwnerRatings.vue";

const mountRatings = () =>
  shallowMount(OwnerRatings, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

// Realistic rating row shape (matches the fields the template reads).
const rating = (overrides = {}) => ({
  id: 1,
  score: 5,
  comment: "",
  customer_name: "",
  order_number: "A100",
  created_at: new Date("2026-01-15T12:30:00Z").toISOString(),
  owner_reply: "",
  owner_reply_at: null,
  ...overrides,
});

describe("OwnerRatings — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // fetchRatings() uses the REAL staleCache (localStorage-backed) under key
    // "owner.ratings". Without this clear, test 1's payload is served to test 2
    // from a still-fresh cache (5-min TTL), so test 2 never reads its /owner/
    // ratings/ mock.
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

  // ── (1) default mount: empty ratings ──────────────────────────────────────
  // The core guard: setup() + the async onMounted fetch must render with empty
  // data and not throw. The header always renders; the empty state resolves once
  // the fetch settles (res.data ?? [] → no ratings → !ratings.length branch).
  it("mounts with no ratings (default/empty) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountRatings();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (always rendered) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerRatings.title");
    expect(wrapper.text()).toContain("ownerRatings.kicker");
    // Empty state (no ratings) — distinct from the error state.
    expect(wrapper.text()).toContain("ownerRatings.emptyTitle");
  });

  // ── (2) loaded: real ratings payload ──────────────────────────────────────
  // Drives the data-only paths that only run with a non-empty ratings array: the
  // summary stats (reduce/filter), the score-distribution bar (scoreCounts.forEach
  // + scorePercent), the filter pills, and the per-rating v-for (stars, score
  // badge, customer/order row, comment, and both reply branches — one existing
  // reply + one "add reply"). A render crash in any of these surfaces here.
  it("mounts a loaded ratings list without a crash and renders a rating", async () => {
    _routes = {
      "/owner/ratings/": {
        data: {
          ratings: [
            rating({
              id: 1,
              score: 5,
              comment: "Great food, fast delivery!",
              customer_name: "Sara Bennani",
              order_number: "A100",
              owner_reply: "Thank you Sara!",
              owner_reply_at: new Date("2026-01-16T09:00:00Z").toISOString(),
            }),
            rating({
              id: 2,
              score: 3,
              comment: "A bit cold on arrival.",
              customer_name: "Omar Alami",
              order_number: "A101",
            }),
          ],
        },
      },
    };

    expect(() => {
      wrapper = mountRatings();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerRatings.title");
    // Loaded rows rendered (the v-for + comment/customer template paths ran).
    expect(wrapper.text()).toContain("Great food, fast delivery!");
    expect(wrapper.text()).toContain("Sara Bennani");
    // Summary block rendered (summary computed non-null → its labels appear).
    expect(wrapper.text()).toContain("ownerRatings.totalRatings");
  });

  // ── (3) regression: headline uses the SERVER aggregate, not the 50-row page ──
  // The list endpoint paginates at 50 but returns all-time count/average. The
  // headline must show those server aggregates, NOT the mean/length of the loaded
  // page — the bug was that a tenant with >50 ratings saw an average of only the
  // newest 50 and a total capped at 50. Here the loaded page is 2 rows averaging
  // 2.0, while the server reports 200 ratings averaging 4.6.
  it("shows the server's all-time count + average, not the loaded-page sample", async () => {
    _routes = {
      "/owner/ratings/": {
        data: {
          count: 200,     // all-time total (server aggregate over the full set)
          average: 4.6,   // all-time average (server aggregate)
          ratings: [rating({ id: 1, score: 2 }), rating({ id: 2, score: 2 })],
        },
      },
    };

    wrapper = mountRatings();
    await flushPromises();

    const text = wrapper.text();
    // All-time total (200), not the 2 loaded rows.
    expect(text).toContain("200");
    // All-time average (4.6), not the loaded-page mean of 2.0.
    expect(text).toContain("4.6");
    expect(text).not.toContain("2.0");
    // The distribution bars cover only the loaded page → honest caption shown.
    expect(text).toContain("ownerRatings.distributionNote");
  });
});

// ── S1-C / B-05 appended tests ──────────────────────────────────────────────
// The base api mock ignores call params, so these tests drive page-aware
// behaviour by replacing api.get's implementation per test (the mock's get is
// a vi.fn; beforeEach's clearAllMocks only clears calls, not an implementation
// set inside the test body). The import below is hoisted, so it may sit here
// at the append point.
import api from "../../lib/api";

const findButtonByText = (w, text) =>
  w.findAll("button").find((b) => b.text().includes(text));

describe("OwnerRatings — S1-C B-05 pagination (appended)", () => {
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

  // ── (4) Load more appends page 2, updates the visible count, ends the list ──
  it("loads page 2 on Load more, shows the count, then the all-loaded note", async () => {
    api.get.mockImplementation((url, opts) => {
      const page = opts?.params?.page ?? 1;
      if (page === 1) {
        return Promise.resolve({
          data: {
            count: 120,
            average: 4.5,
            page: 1,
            page_size: 50,
            has_more: true,
            ratings: [
              rating({ id: 1, score: 5, comment: "First page one", customer_name: "Sara Bennani" }),
              rating({ id: 2, score: 4, comment: "First page two", customer_name: "Omar Alami" }),
            ],
          },
        });
      }
      return Promise.resolve({
        data: {
          count: 120,
          average: 4.5,
          page: 2,
          page_size: 50,
          has_more: false,
          ratings: [
            rating({ id: 3, score: 3, comment: "Second page one", customer_name: "Youssef Alami" }),
          ],
        },
      });
    });

    wrapper = mountRatings();
    await flushPromises();

    // Page 1 on screen + the visible count names the server total (120), not
    // just the loaded rows — the B-05 disclosure.
    expect(wrapper.text()).toContain("ownerRatings.showingCount");
    expect(wrapper.text()).toContain('{"loaded":2,"total":120}');
    expect(wrapper.text()).toContain("First page one");
    expect(wrapper.text()).not.toContain("Second page one");
    const loadMoreBtn = findButtonByText(wrapper, "ownerRatings.loadMore");
    expect(loadMoreBtn.exists()).toBe(true);

    await loadMoreBtn.trigger("click");
    await flushPromises();

    // Page 2 appended (page 1 rows kept), count updated, list ended.
    expect(wrapper.text()).toContain("First page one");
    expect(wrapper.text()).toContain("Second page one");
    expect(wrapper.text()).toContain('{"loaded":3,"total":120}');
    expect(findButtonByText(wrapper, "ownerRatings.loadMore")).toBeUndefined();
    expect(wrapper.text()).toContain("ownerRatings.allLoaded");
  });

  // ── (5) Load-more failure toasts + keeps the button for retry ─────────────
  it("keeps Load more + shows an inline Retry when page 2 fails", async () => {
    api.get.mockImplementation((url, opts) => {
      const page = opts?.params?.page ?? 1;
      if (page === 1) {
        return Promise.resolve({
          data: {
            count: 120,
            average: 4.5,
            page: 1,
            page_size: 50,
            has_more: true,
            ratings: [rating({ id: 1, score: 5, comment: "First page one" })],
          },
        });
      }
      return Promise.reject(new Error("network down"));
    });

    wrapper = mountRatings();
    await flushPromises();
    expect(wrapper.text()).toContain("First page one");

    await findButtonByText(wrapper, "ownerRatings.loadMore").trigger("click");
    await flushPromises();

    // Failure is surfaced (inline error) and the owner can retry: the Load
    // more button is still there and an explicit Retry renders too.
    expect(wrapper.text()).toContain("ownerRatings.loadMoreError");
    expect(findButtonByText(wrapper, "ownerRatings.loadMore").exists()).toBe(true);
    expect(findButtonByText(wrapper, "common.retry").exists()).toBe(true);
    // Already-loaded rows are not lost by the failed append.
    expect(wrapper.text()).toContain("First page one");
  });
});
