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
