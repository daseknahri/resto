/**
 * Mount smoke test for DishPage.vue (~622 lines) — the customer dish-detail page
 * (hero image, chips, price, option groups/modifiers, add-to-cart, similar dishes,
 * lightbox).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, an unguarded browser
 * API, a bad import) was never caught by a test". DishPage runs a real setup()
 * with an async onMounted (tenant.fetchMeta + menu.fetchCategories +
 * menu.fetchDishesByCategory), an immediate watch that fires analytics on the
 * first dish, ~20 computeds (option selection, happy-hour pricing, closed-now
 * gates), a focus-trap, an IntersectionObserver, and a Teleport lightbox.
 * Mounting runs that real setup() so any such crash fails CI instead of prod.
 *
 * HOW THE PAGE READS ITS DISH: purely from PROPS, not the route.
 *   defineProps({ category: String, dish: String })   // both optional
 *   dishes = menu.dishes[props.category] || []
 *   dish   = dishes.find(d => d.slug === props.dish)
 * So there is no useRoute() — only { useRouter }. The identifier arrives as the
 * `category` + `dish` props, and the dish object is looked up in the MENU STORE.
 * The loaded-case test therefore seeds the menu store (not a route mock).
 *
 * SEEDING AVOIDS THE DEMO-DATA TRAP: menu.fetchCategories(), when it gets empty
 * data on a "public demo host", calls applyDemoMenuData() which REPLACES the
 * whole menu.dishes object — that would wipe a seeded fixture. Two defences:
 *   (1) runtimeHost is mocked so isPublicDemoHost()=false → deterministic
 *       non-demo store path (empty data → empty menu, never demo fixtures), and
 *   (2) the loaded case seeds tenant.meta + menu.categories + menu.dishes so all
 *       three onMounted guards are satisfied and NO fetch fires at all.
 *
 * Pattern-faithful to pages/__tests__/Cart.mount.test.js &
 * MarketplaceMenuPage.mount.test.js: shallowMount (auto-stubs AppIcon/DishImage/
 * QtyStepperButton), real pinia (the menu/cart/tenant/toast stores run for real),
 * URL-routed lib/api mock, useI18n mocked to deterministic keys, vue-router mocked.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Exact destructure DishPage uses: { currentLocale, formatPrice, t }.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatPrice: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock. onMounted's stores fire GETs (/meta/, /super-categories/,
// /categories/, /dishes/); default everything resolves empty so the not-found
// branch renders for the default mount. _routes is here for parity with the
// sibling smoke tests (unused by these two cases — every GET returns { data: {} }).
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

// Force the deterministic NON-DEMO store path (see the SEEDING note above):
// empty data → empty menu, never the demo-fixture branch that would overwrite a
// seeded dish. importOriginal spread keeps every other real export intact for any
// other in-graph consumer (currentHostname, isLocalTenantHost, …).
vi.mock("../../lib/runtimeHost", async (importOriginal) => ({
  ...(await importOriginal()),
  isPublicDemoHost: () => false,
  hasPublicDemoTenant: () => false,
}));

// The immediate watch(() => dish.value?.slug, …, { immediate: true }) fires
// trackEvent synchronously in setup() when a dish is present (loaded case). Mock
// it so the smoke test never touches real analytics / an api.post fan-out.
vi.mock("../../lib/analytics", () => ({ trackEvent: vi.fn() }));

// DishPage imports { useRouter } from 'vue-router'; the template uses <RouterLink>
// as a global (not imported), so it is stubbed via global.stubs below. useRoute is
// provided for parity/safety though DishPage does not read it.
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}));

import api from "../../lib/api";
import { useMenuStore } from "../../stores/menu";
import { useTenantStore } from "../../stores/tenant";
import DishPage from "../DishPage.vue";

const mountDish = (props) =>
  shallowMount(DishPage, {
    props,
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

// Option groups use min_select / max_select (NOT required / multi_select) and a
// DishOption has NO is_available — the real field names (live-shakeout bug #96).
// One required single-select group (radio branch) + one optional multi-select
// group (checkbox branch) exercises both option UIs and the min_select>0
// auto-select in watchEffect.
const loadedDish = () => ({
  id: 42,
  slug: "classic-burger",
  name: "Classic Burger",
  description: "A juicy grilled beef patty with lettuce and tomato.",
  price: "55.00",
  effective_price: "55.00",
  currency: "MAD",
  image_url: "",
  is_combo: false,
  combo_unavailable: false,
  is_available: true,
  is_schedule_available: true,
  happy_hour: null,
  tags: [],
  options: [],
  option_groups: [
    {
      id: 1,
      name: "Size",
      min_select: 1,
      max_select: 1,
      options: [
        { id: 101, name: "Regular", price_delta: "0.00" },
        { id: 102, name: "Large", price_delta: "10.00" },
      ],
    },
    {
      id: 2,
      name: "Extras",
      min_select: 0,
      max_select: 2,
      options: [
        { id: 201, name: "Cheese", price_delta: "5.00" },
        { id: 202, name: "Bacon", price_delta: "8.00" },
      ],
    },
  ],
});

describe("DishPage — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // The cart store hydrates from localStorage in its state factory; clear so
    // each test starts blank (and staleCache-backed menu/tenant reads start empty).
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // useFocusTrap/useVisibility register teardown in onBeforeUnmount — unmount so
    // nothing leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default mount: identifier present, menu empty ───────────────────────
  // The core guard. Stores are NOT seeded, so onMounted fires all three fetches
  // against the empty-data api mock; on the forced non-demo path they resolve to
  // an empty menu, so the dish lookup misses and the own-template NOT-FOUND branch
  // (v-else-if="!dish") renders. Proves the async onMounted + full setup() run
  // without a crash.
  it("mounts without a setup() crash and renders the not-found branch for a missing dish", async () => {
    expect(() => {
      wrapper = mountDish({ category: "burgers", dish: "does-not-exist" });
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // onMounted fetched (menu store hit the api) — the realistic cold-load path.
    expect(api.get).toHaveBeenCalled();
    // Own-template not-found heading (dishPage.notFoundTitle; mocked t echoes the key).
    expect(wrapper.text()).toContain("dishPage.notFoundTitle");
  });

  // ── (2) loaded dish: seeded menu store ──────────────────────────────────────
  // Seeds tenant.meta + menu.categories + menu.dishes[category] with a realistic
  // dish (name, price, description, two option groups). All three onMounted guards
  // are satisfied → no fetch fires → menu.loading stays false → the dish resolves
  // → the main (v-else) branch renders: hero, chips, title, and the option-group
  // fieldsets. Exercises the loaded template + the watchEffect auto-select.
  it("mounts a loaded dish (main branch: title + option groups) without a crash", async () => {
    const tenant = useTenantStore();
    tenant.meta = { plan: { can_checkout: true, currency: "MAD" }, profile: {} };

    const menu = useMenuStore();
    menu.categories = [{ slug: "burgers", name: "Burgers" }];
    menu.dishes = { burgers: [loadedDish()] };

    expect(() => {
      wrapper = mountDish({ category: "burgers", dish: "classic-burger" });
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Seeded state means the guarded onMounted fetches were skipped entirely.
    expect(api.get).not.toHaveBeenCalled();
    // Own-template loaded signals: the <h1> dish name and an option-group <legend>.
    expect(wrapper.text()).toContain("Classic Burger");
    expect(wrapper.text()).toContain("Size");
    expect(wrapper.text()).toContain("Extras");
  });
});
