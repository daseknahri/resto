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

// URL-routed api mock: onMounted fires GETs (/customer/session/,
// /promo-code-check/?auto=1, and for a signed-in customer /customer/addresses/,
// /customer/loyalty/config/, /order-eligibility/) + an analytics POST. Default:
// everything resolves empty so the guest path renders. _routes is here for parity
// with the sibling smoke tests.
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

import api from "../../lib/api";
import { useCartStore } from "../../stores/cart";
import { useCustomerStore } from "../../stores/customer";
import { useTenantStore } from "../../stores/tenant";
import { useToastStore } from "../../stores/toast";
import Cart from "../Cart.vue";
import CartEmptyState from "../../components/CartEmptyState.vue";
import CartLineItem from "../../components/CartLineItem.vue";
import CartOrderSummary from "../../components/CartOrderSummary.vue";

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

// ── H3: a rejected cart line must be actionable ─────────────────────────────
// The place-order endpoints reject unorderable lines as
// { code: "items_unavailable", slugs: [...] } (the WhatsApp / checkout-intent endpoints use
// `unavailable_slugs`). Cart.vue used to read only the latter, so the red "Unavailable items…
// Remove" block was unreachable and the customer got a generic error.
describe("Cart — items_unavailable rejection (H3)", () => {
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

  const mountWithBurger = async () => {
    seedOrderableTenant();
    useCartStore().add({ slug: "burger", name: "Burger", price: 50, qty: 1, currency: "MAD" });
    wrapper = mountCart();
    await flushPromises();
  };

  const rejection = (data) => ({ response: { status: 400, data } });

  it("reads the place-order `slugs` field, names the line (not the slug) and shows the Remove block", async () => {
    await mountWithBurger();

    const msg = wrapper.vm.mapOrderApiError(rejection({ code: "items_unavailable", slugs: ["burger"] }));
    await flushPromises();

    // The error text names the cart line, never the raw slug.
    expect(msg).toBe('cartPage.itemsUnavailable({"items":"Burger"})');
    expect(wrapper.vm.unavailableSlugs).toEqual(["burger"]);
    // The (previously unreachable) red block renders with the line name + a Remove button.
    expect(wrapper.text()).toContain('cartPage.unavailableItemsDetected({"items":"Burger"})');
    expect(wrapper.text()).toContain("cartPage.removeUnavailableItems");
  });

  it("still honours the legacy `unavailable_slugs` field (WhatsApp / checkout-intent)", async () => {
    await mountWithBurger();
    wrapper.vm.mapOrderApiError(rejection({ code: "items_unavailable", unavailable_slugs: ["burger"] }));
    expect(wrapper.vm.unavailableSlugs).toEqual(["burger"]);
  });

  it("Remove drops exactly the rejected line from the cart and clears the block", async () => {
    await mountWithBurger();
    const cart = useCartStore();
    cart.add({ slug: "fries", name: "Fries", price: 20, qty: 1, currency: "MAD" });
    await flushPromises();
    wrapper.vm.mapOrderApiError(rejection({ code: "items_unavailable", slugs: ["burger"] }));
    await flushPromises();

    const removeBtn = wrapper.findAll("button").find((b) => b.text().includes("cartPage.removeUnavailableItems"));
    expect(removeBtn).toBeTruthy();
    await removeBtn.trigger("click");
    await flushPromises();

    expect(cart.items.map((i) => i.slug)).toEqual(["fries"]);
    expect(wrapper.vm.unavailableSlugs).toEqual([]);
  });

  it("lowering a quantity lapses a stale rejection so the customer can retry", async () => {
    await mountWithBurger();
    const cart = useCartStore();
    cart.increment(cart.items[0].key); // 2 → so a decrement below is a real edit
    await flushPromises();
    wrapper.vm.mapOrderApiError(rejection({ code: "items_unavailable", slugs: ["burger"] }));
    expect(wrapper.vm.unavailableSlugs).toEqual(["burger"]);

    cart.decrement(cart.items[0].key);
    await flushPromises();
    expect(wrapper.vm.unavailableSlugs).toEqual([]);
  });

  it("re-syncs the stale wallet balance on a 402 wallet_insufficient", async () => {
    await mountWithBurger();
    const customerStore = useCustomerStore();
    const spy = vi.spyOn(customerStore, "fetchCustomer");
    const msg = wrapper.vm.mapOrderApiError(rejection({ code: "wallet_insufficient" }));
    expect(msg).toBe("cartPage.walletInsufficientError");
    expect(spy).toHaveBeenCalledWith(true);
  });
});

// ── M1: "Cash on handover" + "Schedule for later" ────────────────────────────
// The server honours cash only for IMMEDIATE orders; a scheduled order silently falls back
// to the wallet. The cart must not promise cash while scheduling.
describe("Cart — cash on handover vs scheduled order (M1)", () => {
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

  it("hides the cash option, explains why, and pays from the wallet while scheduling", async () => {
    seedOrderableTenant();
    useCustomerStore().setCustomer({ id: 1, name: "Ali", wallet_balance: "500.00" });
    useCartStore().add({ slug: "burger", name: "Burger", price: 50, qty: 1, currency: "MAD" });
    _routes["/order-eligibility/"] = { data: { cod_eligible: true } };
    wrapper = mountCart();
    await flushPromises();

    wrapper.vm.fulfillmentType = "pickup";
    wrapper.vm.paymentMethod = "cash";
    await flushPromises();

    // Immediate order: cash is offered and chosen.
    expect(wrapper.vm.codChosen).toBe(true);
    expect(wrapper.text()).toContain("cartPage.payMethodCash");
    expect(wrapper.vm.buildPayload().payment_method).toBe("cash");

    // Schedule for later: cash is neither offered nor chosen; the wallet is charged.
    wrapper.vm.scheduleEnabled = true;
    await flushPromises();
    expect(wrapper.vm.codChosen).toBe(false);
    expect(wrapper.text()).not.toContain("cartPage.payMethodCash");
    expect(wrapper.text()).not.toContain("cartPage.payCashOnHandoverTitle");
    expect(wrapper.text()).toContain("cartPage.cashNotForScheduled");
    const payload = wrapper.vm.buildPayload();
    expect(payload.payment_method).toBeUndefined();
    expect(payload.use_wallet).toBe(true);

    // Back to ASAP: the customer's cash choice is restored.
    wrapper.vm.scheduleEnabled = false;
    await flushPromises();
    expect(wrapper.vm.codChosen).toBe(true);
  });
});

// ── M8 / L6 / L14: the cart must quote what checkout charges and credits ─────
describe("Cart — checkout preview parity (auto promo, points, replay)", () => {
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
    api.post.mockImplementation(() => Promise.resolve({ data: {} }));
  });

  const LUNCH_10 = { name: "Lunch 10%", promo_type: "percentage", discount_value: "10.00", min_order_amount: "50.00" };

  // A signed-in pickup customer with a 100 MAD cart. The default 10% tip adds 10, so the
  // charge is 100 - promo + 10.
  const mountPickup = async ({ wallet = "105.00", price = 100, customer = {} } = {}) => {
    seedOrderableTenant();
    useCustomerStore().setCustomer({ id: 1, name: "Ali", wallet_balance: wallet, ...customer });
    useCartStore().add({ slug: "burger", name: "Burger", price, qty: 1, currency: "MAD" });
    wrapper = mountCart();
    await flushPromises();
    wrapper.vm.fulfillmentType = "pickup";
    await flushPromises();
  };

  it("previews the auto-applied promo and wallet-gates on the discounted total (M8)", async () => {
    _routes["/promo-code-check/?auto=1"] = { data: { auto_promos: [LUNCH_10] } };
    await mountPickup({ wallet: "105.00" });

    expect(api.get).toHaveBeenCalledWith("/promo-code-check/?auto=1");
    const summary = wrapper.findComponent(CartOrderSummary);
    expect(summary.props("promoDiscount")).toBe(10);
    expect(summary.props("promoLabel")).toBe("Lunch 10%");
    expect(wrapper.vm.orderGrandTotal).toBe(100);
    // 105 covers the real 100 charge — the old 110 preview wrongly demanded a top-up.
    expect(wrapper.vm.prepayShortfall).toBe(false);
    expect(wrapper.vm.validateForm()).toBe(true);
    // No code entered → no promo_code sent; the server auto-applies the same promo.
    expect(wrapper.vm.buildPayload().promo_code).toBeUndefined();
  });

  it("skips an auto promo whose minimum the cart doesn't reach", async () => {
    _routes["/promo-code-check/?auto=1"] = { data: { auto_promos: [LUNCH_10] } };
    await mountPickup({ price: 40 });
    expect(wrapper.vm.promoDiscount).toBe(0);
    expect(wrapper.findComponent(CartOrderSummary).props("promoLabel")).toBe("");
  });

  it("a typed code REPLACES the auto promo (server rule) and says when that costs more", async () => {
    _routes["/promo-code-check/?auto=1"] = { data: { auto_promos: [LUNCH_10] } };
    await mountPickup({ wallet: "500.00" });

    wrapper.vm.promoCode = "SAVE5";
    wrapper.vm.promoApplied = { name: "Save 5", promo_type: "fixed", discount_value: "5.00", min_order_amount: "0.00" };
    await flushPromises();

    expect(wrapper.vm.promoDiscount).toBe(5); // the code's, not max(code, auto)
    expect(wrapper.findComponent(CartOrderSummary).props("promoLabel")).toBe("Save 5");
    expect(wrapper.vm.orderGrandTotal).toBe(105);
    expect(wrapper.text()).toContain('cartPage.promoReplacesAuto({"name":"Lunch 10%"})');
    expect(wrapper.vm.buildPayload().promo_code).toBe("SAVE5");
  });

  it("projects points with the tier multiplier and the first-order bonus (L6)", async () => {
    _routes["/customer/loyalty/config/"] = {
      data: {
        enabled: true, points_per_unit: 10, redeem_threshold: 100, points_value: "0.0100",
        tier_enabled: true, tier_silver_threshold: 500, tier_gold_threshold: 2000,
        tier_silver_multiplier: "1.50", tier_gold_multiplier: "2.00",
        first_order_bonus_points: 50, first_order_bonus_eligible: true,
      },
    };
    await mountPickup({ customer: { lifetime_loyalty_points: 600, loyalty_points: 0 } });

    // floor(100 × 10 × 1.5) + 50 — not the old floor(100 × 10).
    expect(wrapper.vm.loyaltyEarnProjection).toBe(1550);
    expect(wrapper.text()).toContain('cartPage.loyaltyEarnProjection({"points":1550})');
  });

  it("announces a replayed order as already placed, not as a new one (L14)", async () => {
    await mountPickup({ wallet: "500.00" });
    const toast = useToastStore();
    const show = vi.spyOn(toast, "show");
    api.post.mockImplementation((url) =>
      Promise.resolve(
        String(url).includes("/place-order/")
          ? { data: { order_number: "ORD-AAA111", total: "110.00", idempotent_replay: true } }
          : { data: {} },
      ),
    );

    await wrapper.vm.placeInAppOrder();
    await flushPromises();

    expect(show).toHaveBeenCalledWith("cartPage_order.orderAlreadyPlaced", "info");
    expect(show).not.toHaveBeenCalledWith("cartPage_order.placeOrderSuccess", "success");
    // Same cart as the key was minted for, so the replayed order IS this cart's — it's done.
    expect(useCartStore().items).toHaveLength(0);
  });

  it("lost response, then an edit: replays the EARLIER order, says the edits weren't added, keeps the cart (L14)", async () => {
    await mountPickup({ wallet: "500.00" });
    const cart = useCartStore();
    const show = vi.spyOn(useToastStore(), "show");
    const placeCalls = () => api.post.mock.calls.filter(([url]) => String(url).includes("/place-order/"));
    let attempt = 0;
    api.post.mockImplementation((url) => {
      if (!String(url).includes("/place-order/")) return Promise.resolve({ data: {} });
      attempt += 1;
      // 1st: the order IS placed server-side but the response is lost. 2nd: the server replays it.
      return attempt === 1
        ? Promise.reject(new Error("Network Error"))
        : Promise.resolve({ data: { order_number: "ORD-OLD111", total: "110.00", idempotent_replay: true } });
    });

    await wrapper.vm.placeInAppOrder();
    await flushPromises();
    cart.increment(cart.items[0].key); // the customer edits the cart before retrying
    await flushPromises();
    await wrapper.vm.placeInAppOrder();
    await flushPromises();

    // Same key → no second order / charge.
    expect(placeCalls()).toHaveLength(2);
    expect(placeCalls()[1][1].idempotency_key).toBe(placeCalls()[0][1].idempotency_key);
    expect(show).toHaveBeenCalledWith("cartPage_order.orderAlreadyPlacedEditsKept", "warning", 9000);
    expect(show).not.toHaveBeenCalledWith("cartPage_order.placeOrderSuccess", "success");
    // The edited cart is kept (not cleared, not recorded as that order).
    expect(cart.items).toHaveLength(1);
    expect(cart.items[0].qty).toBe(2);
  });
});
