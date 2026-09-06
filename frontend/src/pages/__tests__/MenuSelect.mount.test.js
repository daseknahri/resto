/**
 * Mount smoke test for MenuSelect.vue (the menu / super-category selector, ~284
 * lines — a customer picks which published menu/section to browse for a restaurant).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined map access, unguarded null) was
 * never caught by a test". MenuSelect is exposed on several such fronts, all of
 * which run inside setup()/first-render:
 *   - a NON-immediate `watch(() => [menu.loading, publishedMenus.value.length], …)`
 *     — Vue still evaluates the source getter ONCE synchronously at registration,
 *     so `publishedMenus.value` (→ the menu store's superCategories) is read during
 *     setup against a possibly-empty store;
 *   - a stack of null-tenant-profile computeds rendered in the always-present hero
 *     (tenantName, isRestaurantOpen via lib/businessHours, statusLabel) that must
 *     tolerate a null profile;
 *   - an async onMounted that awaits menu.fetchCategories() and then calls
 *     maybeAutoRedirect(), which does router.replace(...) when there is EXACTLY ONE
 *     published menu.
 * shallowMount runs MenuSelect's real setup()/onMounted while auto-stubbing its one
 * imported child (AppIcon), so a crash in any of that fails CI here, not in prod.
 *
 * HOW THE PAGE READS ITS RESTAURANT: it does NOT take a restaurant id/slug from the
 * route or a prop. The tenant is resolved from the request subdomain into the Pinia
 * tenant/menu stores elsewhere; this page just calls menu.fetchCategories() (the api
 * client is subdomain-scoped) and renders menu.superCategories. So there is nothing
 * route-shaped to supply — the vue-router mock exists only because the page imports
 * useRouter and calls router.replace in the auto-redirect.
 *
 * Pattern-faithful to pages/__tests__/Menu.mount.test.js (same menu store, same
 * URL-routed lib/api mock, localStorage-first reset). API boundary: the menu STORE
 * (stores/menu.js), which fetches /super-categories/ + /categories/ through
 * lib/api. The page's card grid is a v-for over the store's superCategories, so the
 * loaded case seeds /super-categories/ (two entries — one would trip the
 * single-menu auto-redirect instead of rendering the list).
 *
 * MenuSelect imports ONLY { useRouter } from vue-router; RouterLink is a globally
 * resolved component (NOT imported), so the vue-router mock factory references no
 * local stub and vi.hoisted is unnecessary — a plain RouterLink stub in global.stubs
 * suffices (same as Menu / MarketplaceMenuPage). useRoute is provided defensively.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// MenuSelect destructures exactly { currentLocale, t } from useI18n(). currentLocale
// MUST be ref-like ({ value }) — statusLabel reads currentLocale.value on the
// closed-with-schedule path. The mocked `t` returns its key verbatim (param-less)
// so own-template headings are assertable by key.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// MenuSelect destructures { groupPlural, itemPlural } from useVocabulary(); both are
// used ONLY as t() params in the template, so plain strings are enough.
vi.mock("../../composables/useVocabulary", () => ({
  useVocabulary: () => ({ groupPlural: "items", itemPlural: "dishes" }),
}));

// URL-routed api mock: onMounted → menu.fetchCategories() drives
// api.get("/super-categories/") + api.get("/categories/"). Default: every GET
// resolves { data: {} } so the store normalizes to empty arrays and the empty path
// renders. Tests set _routes to drive the loaded path. _match / _routes are read
// ONLY inside the lazy vi.fn closures (never at module-eval time).
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

// MenuSelect imports ONLY { useRouter } from vue-router and calls router.replace in
// maybeAutoRedirect. useRoute is provided defensively (the page does not read it).
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import MenuSelect from "../MenuSelect.vue";

const mountPage = () =>
  shallowMount(MenuSelect, {
    global: {
      stubs: {
        // RouterLink is a GLOBAL component (not imported), so shallowMount does not
        // auto-stub it — a pass-through stub keeps slot content (the card) rendering.
        RouterLink: { template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

// A published super-category as the menu store normalizes it (normalizeSuperCategories
// spreads the row + defaults description/image_url). `name` MUST be a non-empty string:
// the card placeholder renders sc.name.charAt(0).toUpperCase(). `is_published !== false`
// keeps it in publishedMenus; `slug` feeds :key + the RouterLink target.
const superCat = (overrides = {}) => ({
  id: 1,
  slug: "food",
  name: "Food",
  position: 0,
  is_published: true,
  is_temporarily_disabled: false,
  category_count: 3,
  ...overrides,
});

describe("MenuSelect — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // localStorage FIRST: menu.fetchCategories' staleCache is localStorage-backed, so
    // a leaked write from a prior test would change what this test's fresh mount sees.
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

  // ── (1) empty menu: the core setup()/onMounted crash guard ──────────────────
  // With every GET resolving { data: {} }, the store normalizes to empty arrays and
  // the tenant profile is null. The watch source getter (reads publishedMenus →
  // store), the null-profile hero computeds (tenantName / isRestaurantOpen /
  // statusLabel), and the async onMounted (fetchCategories + maybeAutoRedirect) must
  // all run without throwing. The always-rendered hero <h1> falls back to the
  // tenant-name i18n key — the crash-guard anchor; the empty-state title confirms the
  // empty path rendered.
  it("mounts with an empty menu (empty path) without a setup() crash", async () => {
    // The white-screen bug class throws synchronously inside setup(), so mount()
    // itself would throw — this assertion is the guard.
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    // Let onMounted's fetchCategories settle (loading → false, empty state paints).
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // Hero <h1>{{ tenantName }}</h1> is always rendered; null profile → fallback key.
    expect(wrapper.text()).toContain("customerLayout.fallbackTenantName");
    // No super-categories → empty state title renders (menuSelect namespace).
    expect(wrapper.text()).toContain("menuSelect.emptyTitle");
  });

  // ── (2) loaded menu: real super-categories drive the own-template card grid ──
  // /super-categories/ returns TWO published super-categories (two, not one — a
  // single published menu trips maybeAutoRedirect's router.replace instead of
  // rendering the list). menu.fetchCategories() populates the store, publishedMenus
  // resolves, and the v-for renders each super-category's own-template <h3>{{ sc.name }}</h3>.
  it("renders a loaded menu (super-categories) from the page's own template without crashing", async () => {
    _routes = {
      "/super-categories/": {
        data: [
          superCat({ id: 1, slug: "food", name: "Food", position: 0 }),
          superCat({ id: 2, slug: "drinks", name: "Drinks", position: 1 }),
        ],
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    const text = wrapper.text();
    expect(wrapper.exists()).toBe(true);
    // Both super-category names render from MenuSelect.vue's own card <h3> template.
    expect(text).toContain("Food");
    expect(text).toContain("Drinks");
  });
});
