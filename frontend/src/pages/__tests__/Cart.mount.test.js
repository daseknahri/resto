/**
 * Mount smoke test for Cart.vue (the cart + checkout page, ~2464 lines) — the
 * highest-value surface in the app.
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, an unguarded browser
 * API, a bad import) was never caught by a test". Cart.vue is especially exposed:
 * an async onMounted (fetchCustomer / saved-addresses / loyalty / COD-eligibility
 * + express-checkout & reorder-context restore + analytics + a keydown listener),
 * ~40 computeds (delivery pricing, ETA, wallet, loyalty, closed-now gates), and a
 * Leaflet map. Mounting runs the real setup() so any such crash fails CI here
 * instead of in production.
 *
 * THE LEAFLET TRAP (handled): the Leaflet map is LAZY. initLeafletMap() — which
 * does the dynamic import('leaflet') + addTileLayer() — is called ONLY from
 * watch(showMapModal) when the in-app map modal opens (a user action:
 * openInAppMapPicker / useCurrentLocation). A default cart mount never touches
 * Leaflet, so no `leaflet` mock is needed (Cart.vue has no static leaflet import);
 * ../../lib/mapTiles is still mocked defensively so no test can ever trip the
 * tile-layer boundary. Neither case drives the delivery-map step.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js (URL-routed api
 * mock, vi.hoisted RouterLink stub, real pinia, afterEach unmount):
 *   - shallowMount (auto-stubs the heavy Cart* children + the two modals)
 *   - real pinia — the cart/tenant/customer stores run for real, so the tests
 *     seed them to drive the empty-cart and loaded-order-panel branches
 *   - useI18n mocked to deterministic keys ({ formatPrice, itemCountLabel,
 *     formatDateTime, t } — the exact destructure Cart.vue uses)
 *   - vue-router mocked (Cart.vue imports { useRouter }; child components import
 *     { RouterLink })
 *
 * NOTE: tenant.isBrowseOnlyPlan is TRUE for an unconfigured tenant (an empty plan
 * derives ordering_mode="menu_only"), which renders the browse-only banner and
 * HIDES the whole order panel + empty state. A real checkout tenant can order, so
 * both tests seed an orderable plan (can_checkout) to exercise the real
 * empty-cart and order-panel render paths. Cart.vue's onMounted does NOT fetch
 * meta, so seeding the store directly is authoritative.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatPrice: (v) => String(v),
    itemCountLabel: (v) => String(v),
    formatDateTime: (v) => String(v),
  }),
}));

// URL-routed api mock: onMounted fires GETs (/customer/session/, and for a
// signed-in customer /customer/addresses/, /customer/loyalty/config/,
// /order-eligibility/) + an analytics POST. Default: everything resolves empty so
// the guest path renders. _routes is here for parity with the sibling smoke tests.
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

// Defensive: the Leaflet tile-layer boundary. Never reached by a default mount
// (the map is lazy — see the file header), but mocked so no test can trip it.
vi.mock("../../lib/mapTiles", () => ({ addTileLayer: vi.fn() }));

// Cart.vue imports { useRouter } from 'vue-router'; the template uses <RouterLink>
// and CartEmptyState.vue imports { RouterLink }. vi.hoisted: the vi.mock factory is
// hoisted above the imports and runs during import evaluation — before a plain
// const in the file body would initialize — so referencing a plain const there
// hits the TDZ ("0 test" collection error). vi.hoisted makes the stub available to
// the hoisted factory.
const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import { useCartStore } from "../../stores/cart";
import { useTenantStore } from "../../stores/tenant";
import Cart from "../Cart.vue";
import CartEmptyState from "../../components/CartEmptyState.vue";
import CartLineItem from "../../components/CartLineItem.vue";

const mountCart = () =>
  shallowMount(Cart, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

// A real checkout tenant can place orders (can_checkout). Without this,
// isBrowseOnlyPlan is true and the browse-only banner replaces the whole order
// panel + empty state — so seed it to exercise the real checkout render paths.
const seedOrderableTenant = () => {
  useTenantStore().meta = {
    plan: { can_checkout: true, currency: "MAD" },
    profile: {},
  };
};

describe("Cart — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // Cart persists items + fulfillment/express context to localStorage and the
    // cart store's state factory hydrates from it — clear so each test starts blank.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // onMounted registers a window keydown listener; onBeforeUnmount removes it.
    // Unmount so no listener/state leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) empty cart ────────────────────────────────────────────────────────
  // The core guard: the async onMounted + the whole template must render for an
  // empty cart and not throw. With an orderable tenant, the empty-cart branch
  // (<CartEmptyState v-else-if="!cart.items.length" />) renders and the order
  // panel stays absent.
  it("mounts with an empty cart without a setup() crash (empty-state branch)", async () => {
    seedOrderableTenant();

    expect(() => {
      wrapper = mountCart();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Empty-cart branch rendered (own-template v-else-if="!cart.items.length").
    // CartEmptyState is the extracted empty-state child (its heading is
    // cartPage.cartEmpty); asserting the child rendered proves the branch was taken.
    expect(wrapper.findComponent(CartEmptyState).exists()).toBe(true);
    // …and no line items for an empty cart.
    expect(wrapper.findAllComponents(CartLineItem).length).toBe(0);
  });

  // ── (2) non-empty cart ────────────────────────────────────────────────────
  // Seeds one real cart line so the main order panel renders: the item v-for
  // (CartLineItem), the delivery-pricing / ETA / wallet / loyalty computeds, the
  // order summary + CTA, and the guest sign-in wall — the own-template paths that
  // only run with a non-empty cart. Fulfillment stays on the default ('', NOT
  // delivery), so the delivery-map step / Leaflet is never touched.
  it("mounts a non-empty cart (order panel + line item) without a crash", async () => {
    seedOrderableTenant();
    const cart = useCartStore();
    cart.add({ slug: "burger", name: "Burger", price: 50, qty: 2, currency: "MAD" });
    expect(cart.items.length).toBe(1); // sanity: the seed took

    expect(() => {
      wrapper = mountCart();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // The item v-for ran over the seeded cart.
    expect(wrapper.findAllComponents(CartLineItem).length).toBe(1);
    // Own-template heading: the guest sign-in wall renders inside the order panel
    // (proves the non-empty, non-browse-only main branch rendered).
    expect(wrapper.text()).toContain("cartPage.orderAuthRequired");
  });
});
