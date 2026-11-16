/**
 * Mount smoke test for Menu.vue (the customer storefront menu page, ~1102 lines).
 *
 * WHY: this is the single most-visited customer surface (every diner who opens a
 * restaurant lands here) and it had NO mount test. The app's recurring production
 * bug class is "a page white-screens on load because a setup()-time error (TDZ,
 * undefined map access, unguarded browser API) was never caught by a test".
 * Menu.vue is especially exposed: an `immediate` watch that runs applyMenuTheme
 * SYNCHRONOUSLY inside setup() (touches localStorage + matchMedia), a second
 * `immediate` watch that runs syncSelection, an async onMounted that awaits
 * menu.fetchCategories() and then news up an IntersectionObserver + a
 * ResizeObserver (neither exists in jsdom) and wires scroll/resize listeners, and
 * a dozen profile-/order-derived computeds (isRestaurantOpen, statusLabel,
 * visibleCategories, …) that render against a possibly-null tenant profile.
 * shallowMount runs Menu.vue's real setup() while auto-stubbing its heavy children
 * (AppIcon, DishCard), so a crash in any of that fails CI here, not in production.
 *
 * HOW THE PAGE READS ITS RESTAURANT: it does NOT take a restaurant id/slug from
 * the route or a prop. The tenant is resolved from the request subdomain into the
 * Pinia tenant/menu stores elsewhere; this page just calls menu.fetchCategories()
 * (the api client is subdomain-scoped). The page's only route read is the OPTIONAL
 * route.params.tableSlug (dine-in QR context), and its only prop is the OPTIONAL
 * `menuSlug` super-category filter (default ''). So the vue-router mock supplies
 * params: {} (no table context) and no prop is passed — the realistic "customer
 * opens the menu" path.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js +
 * WaiterPage.mount.test.js (URL-routed api mock, real pinia, localStorage-first
 * reset, unmount-in-afterEach):
 *   - shallowMount (auto-stubs AppIcon / DishCard)
 *   - real pinia (menu / tenant / cart / customer / toast stores run for real) +
 *     a URL-routed lib/api mock (default { data: {} }; per-test _routes)
 *   - useI18n / useVocabulary / useReorder / lib/analytics / vue-router mocked
 *   - IntersectionObserver + ResizeObserver + matchMedia stubbed (jsdom lacks them)
 *
 * Menu.vue imports ONLY { useRoute } from vue-router (RouterLink is a globally
 * resolved component, NOT imported), so the vue-router mock factory does not
 * reference any local stub and vi.hoisted is unnecessary here — a plain RouterLink
 * stub in global.stubs suffices (same as MarketplaceMenuPage / WaiterPage).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Menu destructures exactly { currentLocale, formatPrice, t } from useI18n().
// currentLocale MUST be ref-like ({ value }) — the page reads currentLocale.value
// in statusLabel and in a watch source. The mocked `t` returns its key verbatim
// (param-less) so own-template headings are assertable by key.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatPrice: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// Menu destructures { groupPlural } from useVocabulary() (used only as a t() param).
vi.mock("../../composables/useVocabulary", () => ({
  useVocabulary: () => ({ groupPlural: "items" }),
}));

// Menu destructures { reorderFromOrder, hydrateServerHistory } from useReorder().
// hydrateServerHistory() is fired (best-effort) at mount; stub both to no-ops so
// the test stays focused on Menu.vue's OWN setup rather than useReorder internals.
vi.mock("../../composables/useReorder", () => ({
  useReorder: () => ({
    reorderFromOrder: vi.fn(),
    hydrateServerHistory: vi.fn(),
  }),
}));

// trackEvent('menu_view', …) fires at the end of onMounted — stub it out.
vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

// URL-routed api mock: onMounted drives menu.fetchCategories() (→ /super-categories/,
// /categories/) and fetchLoyaltyConfig() (→ /customer/loyalty/config/). Default:
// every GET resolves { data: {} } so the empty/loading path renders. Tests set
// _routes to drive the loaded path. _match / _routes are read ONLY inside the lazy
// vi.fn closures (never at module-eval time).
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// Menu imports ONLY { useRoute } from vue-router; useRouter is provided defensively.
// route.params.tableSlug is the optional dine-in context — absent here.
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import Menu from "../Menu.vue";

// jsdom provides none of these; Menu.vue news up the two observers in onMounted and
// reads matchMedia in applyMenuTheme (the 'system' color-scheme branch). No-op them
// so the full onMounted/setup wiring runs instead of throwing an async rejection.
class NoopObserver {
  constructor(cb) {
    this.cb = cb;
  }
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}

const mountMenu = () =>
  shallowMount(Menu, {
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

// A published category as the menu store normalizes it. super_category_slug MUST be
// present and consistent: the page derives a single super-category from it, then
// filters visibleCategories by it — a mismatch (e.g. undefined) would filter every
// category out and render nothing. 'menu' matches the store's own fallback.
const category = (overrides = {}) => ({
  id: 1,
  slug: "starters",
  name: "Starters",
  position: 0,
  super_category_slug: "menu",
  super_category_name: "Menu",
  dishes: [
    { id: 10, slug: "soup", name: "Harira Soup", price: "20.00", is_available: true },
  ],
  ...overrides,
});

describe("Menu — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // localStorage FIRST: menu.fetchCategories' staleCache and applyMenuTheme's
    // 'ui-color-scheme' read are localStorage-backed, so a leaked write from a
    // prior test would change what this test's fresh mount sees.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    // jsdom has no Element.prototype.scrollIntoView; Menu smooth-scrolls the active
    // category pill into view on mount/selection (Menu.vue:909), which would throw an
    // unhandled TypeError. Stub it as a no-op.
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal("IntersectionObserver", NoopObserver);
    vi.stubGlobal("ResizeObserver", NoopObserver);
    vi.stubGlobal("matchMedia", (query) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent() {
        return false;
      },
    }));
  });

  afterEach(() => {
    // onMounted disconnects both observers + removes the scroll/resize listeners on
    // unmount; unmounting keeps listeners/observers from leaking between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    vi.unstubAllGlobals();
  });

  // ── (1) empty menu: the core setup()/onMounted crash guard ────────────────
  // With every GET resolving { data: {} }, menu.categories stays empty and the
  // tenant profile is null. The synchronous `immediate` watches (applyMenuTheme +
  // syncSelection), the async onMounted (fetchCategories + observer/listener
  // wiring), and the null-profile computeds (isRestaurantOpen / statusLabel /
  // tenantName) must all run without throwing. The always-rendered hero <h1>
  // falls back to the tenant-name i18n key — the crash-guard anchor.
  it("mounts with an empty menu (loading/empty path) without a setup() crash", async () => {
    // The white-screen bug class throws synchronously inside setup(), so mount()
    // itself would throw — this assertion is the guard.
    expect(() => {
      wrapper = mountMenu();
    }).not.toThrow();

    // Let onMounted's fetchCategories / fetchLoyaltyConfig settle.
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // Hero <h1> is always rendered; null profile → fallback tenant-name key.
    expect(wrapper.text()).toContain("customerLayout.fallbackTenantName");
    // No categories fetched → the category-name section headers are absent.
    expect(wrapper.text()).not.toContain("Starters");
  });

  // ── (2) loaded menu: real categories drive the own-template sections ──────
  // /categories/ returns two published categories, so menu.fetchCategories()
  // populates the store, the derived super-category + syncSelection resolve, and
  // visibleCategories drives the v-for that renders each category's own-template
  // <h2>{{ cat.name }}</h2> (DishCard is a stubbed child, so the assertion targets
  // the page's own category headings, not child content).
  it("renders a loaded menu (categories) from the page's own template without crashing", async () => {
    _routes = {
      "/categories/": {
        data: [
          category({ id: 1, slug: "starters", name: "Starters", position: 0 }),
          category({ id: 2, slug: "tagines", name: "Tagines", position: 1 }),
        ],
      },
    };

    expect(() => {
      wrapper = mountMenu();
    }).not.toThrow();

    await flushPromises();

    const text = wrapper.text();
    expect(wrapper.exists()).toBe(true);
    // Both category names render from Menu.vue's own <h2> / category-pill template.
    expect(text).toContain("Starters");
    expect(text).toContain("Tagines");
  });
});

// ── C-10: reviews carousel arrow keys in RTL ────────────────────────────────
// In RTL, scrollLeft is negative-based (Chrome), so ArrowRight must scroll the
// carousel the opposite way from LTR. scrollReviewsCarousel flips the sign
// when the document dir is rtl; these tests assert the scrollBy call args in
// both directions. NOTE: there is no file-level beforeEach in this file -- the
// base describe's hook (observers / matchMedia / localStorage + pinia) does not
// run here, so this describe stubs them itself in its own beforeEach. The
// scrollBy mock (jsdom has no layout, so clientWidth is 0 and the step is the
// 160 floor) plus the document.dir setup/teardown are also in that hook.
describe("Menu — reviews carousel RTL (C-10)", () => {
  let wrapper;
  let origScrollBy;

  beforeEach(() => {
    // Isolation + observers (same as the base describe): the C-10 tests mount
    // Menu.vue, whose mounted hook news up an IntersectionObserver -- without
    // the stub it throws an unhandled rejection in jsdom. There is no
    // file-level beforeEach; the base describe's hook does not run here.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal("IntersectionObserver", NoopObserver);
    vi.stubGlobal("ResizeObserver", NoopObserver);
    vi.stubGlobal("matchMedia", (query) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent() {
        return false;
      },
    }));
    origScrollBy = Element.prototype.scrollBy;
    Element.prototype.scrollBy = vi.fn();
    document.documentElement.dir = "";
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    Element.prototype.scrollBy = origScrollBy;
    document.documentElement.dir = "";
    vi.unstubAllGlobals();
  });

  // resolvedMeta returns state.meta, so seeding tenant.meta drives the
  // recentReviews computed the carousel renders from. The tenant store is
  // imported dynamically: this file has no top-level store import and the
  // base must stay an exact prefix, so nothing may be added above.
  const mountWithReviews = async () => {
    const { useTenantStore } = await import("../../stores/tenant");
    const tenant = useTenantStore();
    tenant.meta = {
      profile: {},
      recent_reviews: [{ score: 5, comment: "Great food, loved it" }],
    };
    wrapper = mountMenu();
    await flushPromises();
    return wrapper;
  };

  it("LTR: ArrowRight scrolls forward (+step), ArrowLeft scrolls back (-step)", async () => {
    await mountWithReviews();
    const carousel = wrapper.find('[role="group"]');
    expect(carousel.exists()).toBe(true);
    expect(wrapper.text()).toContain("Great food, loved it");

    await carousel.trigger("keydown", { key: "ArrowRight" });
    expect(Element.prototype.scrollBy).toHaveBeenCalledWith({
      left: 160,
      behavior: "smooth",
    });

    await carousel.trigger("keydown", { key: "ArrowLeft" });
    expect(Element.prototype.scrollBy).toHaveBeenCalledWith({
      left: -160,
      behavior: "smooth",
    });
  });

  it("RTL: ArrowRight scrolls the opposite way (-step), ArrowLeft forward (+step)", async () => {
    document.documentElement.dir = "rtl";
    await mountWithReviews();
    const carousel = wrapper.find('[role="group"]');
    expect(carousel.exists()).toBe(true);

    await carousel.trigger("keydown", { key: "ArrowRight" });
    expect(Element.prototype.scrollBy).toHaveBeenCalledWith({
      left: -160,
      behavior: "smooth",
    });

    await carousel.trigger("keydown", { key: "ArrowLeft" });
    expect(Element.prototype.scrollBy).toHaveBeenCalledWith({
      left: 160,
      behavior: "smooth",
    });
  });
});
