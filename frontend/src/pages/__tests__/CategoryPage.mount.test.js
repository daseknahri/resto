/**
 * Mount smoke test for CategoryPage.vue (~384 lines) — the customer-facing
 * "browse one category" page (category hero, in-category dish search, and a grid
 * of dish cards with quick-add / view-details).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, an unguarded browser
 * API, a bad import) was never caught by a test". CategoryPage runs a real
 * setup() with an onMounted (menu.fetchCategories when categories are empty), an
 * IMMEDIATE watch(() => props.slug, …, { immediate: true }) that SYNCHRONOUSLY
 * fires menu.fetchDishesByCategory(slug) + trackEvent() inside setup(), a second
 * watch on currentLocale, and several profile-derived computeds (isBrowseOnlyPlan,
 * isRestaurantOpen, dineInClosed → quickAddDisabled) that render against a
 * possibly-null tenant profile. shallowMount runs that real setup() while
 * auto-stubbing the heavy children (AppIcon, DishImage), so any such crash fails
 * CI here instead of in production.
 *
 * HOW THE PAGE READS ITS CATEGORY: purely from a PROP, not the route.
 *   defineProps({ slug: String })
 *   dishes          = menu.dishes[props.slug] || []          // dish list
 *   currentCategory = menu.categories.find(c => c.slug === props.slug)
 * So there is no useRoute() — only { useRouter } from vue-router. The identifier
 * arrives as the `slug` prop and both the category object and its dishes are
 * looked up in the MENU STORE. The loaded-case test therefore seeds the menu
 * store (not a route mock).
 *
 * SEEDING AVOIDS THE DEMO-DATA TRAP: menu.fetchCategories()/fetchDishesByCategory()
 * fall back to applyDemoMenuData() / demo fixtures when isPublicDemoHost() &&
 * !hasPublicDemoTenant() — that would REPLACE the whole menu.dishes object and
 * clobber a seeded fixture (and the tenant store's resolvedMeta getter reads the
 * same two host flags). Two defences:
 *   (1) runtimeHost is mocked so isPublicDemoHost()/hasPublicDemoTenant()=false →
 *       deterministic non-demo path (empty data → empty menu, never demo fixtures), and
 *   (2) the loaded case seeds tenant.meta + menu.categories + menu.dishes[slug] so
 *       the onMounted guard skips fetchCategories AND fetchDishesByCategory returns
 *       early (dishes[slug] already populated) → NO fetch fires at all.
 *
 * Pattern-faithful to pages/__tests__/DishPage.mount.test.js (its closest sibling:
 * customer page, prop identifier, menu-store lookup, runtimeHost + analytics mocks)
 * and Menu.mount.test.js: shallowMount (auto-stubs AppIcon/DishImage), real pinia
 * (menu/cart/tenant/toast run for real), URL-routed lib/api mock, useI18n mocked to
 * deterministic keys, vue-router mocked. CategoryPage uses NO IntersectionObserver /
 * ResizeObserver / scrollIntoView / matchMedia at mount, so those jsdom stubs are
 * unnecessary here.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Exact destructure CategoryPage uses: { currentLocale, formatPrice, itemCountLabel, t }.
// currentLocale MUST be ref-like ({ value }) — the page reads currentLocale.value as
// a watch source. The mocked `t` echoes its key (param-less) so own-template headings
// are assertable by key; formatPrice/itemCountLabel just stringify their input.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatPrice: (v) => String(v),
    itemCountLabel: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock. onMounted (menu.fetchCategories) + the immediate slug watch
// (menu.fetchDishesByCategory) fire GETs (/super-categories/, /categories/, /dishes/).
// Default: every GET resolves { data: {} } so the empty/no-results path renders for the
// default mount. _routes is here for parity with the sibling smoke tests (the loaded
// case avoids fetching entirely by seeding the store, so _routes stays unused).
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

// Force the deterministic NON-DEMO store path (see the SEEDING note above): empty data
// → empty menu, never the demo-fixture branch that would overwrite a seeded fixture (and
// the tenant store's resolvedMeta reads these same flags). importOriginal spread keeps
// every other real export intact for any other in-graph consumer.
vi.mock("../../lib/runtimeHost", async (importOriginal) => ({
  ...(await importOriginal()),
  isPublicDemoHost: () => false,
  hasPublicDemoTenant: () => false,
}));

// The immediate watch(() => props.slug, …, { immediate: true }) fires trackEvent
// synchronously in setup() whenever a slug is present. Mock it so the smoke test
// never touches real analytics / an api.post fan-out.
vi.mock("../../lib/analytics", () => ({ trackEvent: vi.fn() }));

// CategoryPage imports ONLY { useRouter } from vue-router; the template uses <RouterLink>
// as a global component (NOT imported), so it is stubbed via global.stubs below. useRoute
// is provided defensively for parity though CategoryPage does not read it. The factory
// references no local stub, so vi.hoisted is unnecessary here (same as DishPage / Menu).
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}));

import api from "../../lib/api";
import { useMenuStore } from "../../stores/menu";
import { useTenantStore } from "../../stores/tenant";
import CategoryPage from "../CategoryPage.vue";

const mountCategory = (props) =>
  shallowMount(CategoryPage, {
    props,
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
      },
    },
  });

// A dish as the results grid reads it. Only slug/name/price/is_available are needed;
// every other field the template touches (tags, options, option_groups, happy_hour,
// effective_price, image_url, description) is behind optional chaining / a truthy guard,
// so their absence is safe.
const loadedDish = (overrides = {}) => ({
  id: 10,
  slug: "harira",
  name: "Harira Soup",
  price: "20.00",
  is_available: true,
  ...overrides,
});

describe("CategoryPage — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // localStorage FIRST: the cart store hydrates from localStorage in its state
    // factory and the menu/tenant staleCache reads are localStorage-backed, so a
    // leaked write from a prior test would change what this test's fresh mount sees.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Unmount so the currentLocale/slug watchers stop between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default mount: slug present, menu empty ─────────────────────────────
  // The core guard. Stores are NOT seeded, so onMounted fires menu.fetchCategories()
  // and the immediate slug watch fires menu.fetchDishesByCategory("starters") against
  // the empty-data api mock; on the forced non-demo path they resolve to an empty menu,
  // so the dish list is empty and (after loading settles) the own-template no-results
  // empty state renders. Proves the async onMounted + immediate watch + full setup()
  // run without a crash.
  it("mounts without a setup() crash and renders the category hero for an empty menu", async () => {
    expect(() => {
      wrapper = mountCategory({ slug: "starters" });
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // onMounted + the immediate watch hit the api (the realistic cold-load path).
    expect(api.get).toHaveBeenCalled();
    // The hero kicker (category.kicker) is always rendered; mocked t echoes the key.
    expect(wrapper.text()).toContain("category.kicker");
    // Empty store → the slug is the fallback category name in the hero <h1>.
    expect(wrapper.text()).toContain("starters");
  });

  // ── (2) loaded category: seeded menu store ──────────────────────────────────
  // Seeds tenant.meta (a checkout-capable plan so quick-add is enabled) + menu.categories
  // + menu.dishes[slug] with a realistic dish. The onMounted guard sees categories present
  // → skips fetchCategories; the immediate watch's fetchDishesByCategory returns early
  // (dishes[slug] already populated) → NO fetch fires → menu.loading stays false → the
  // results grid (v-else-if="filteredDishes.length") renders each dish's own-template
  // <h3>{{ dish.name }}</h3>, and the hero <h1> shows the resolved category name.
  it("mounts a loaded category (results grid: category name + dish) without a crash", async () => {
    const tenant = useTenantStore();
    tenant.meta = { plan: { can_checkout: true, currency: "MAD" }, profile: {} };

    const menu = useMenuStore();
    menu.categories = [{ id: 1, slug: "starters", name: "Starters" }];
    menu.dishes = { starters: [loadedDish()] };

    expect(() => {
      wrapper = mountCategory({ slug: "starters" });
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Seeded state means both guarded onMounted/watch fetches were skipped entirely.
    expect(api.get).not.toHaveBeenCalled();
    // Own-template loaded signals: the hero <h1> category name and a dish-card <h3>.
    expect(wrapper.text()).toContain("Starters");
    expect(wrapper.text()).toContain("Harira Soup");
  });
});
