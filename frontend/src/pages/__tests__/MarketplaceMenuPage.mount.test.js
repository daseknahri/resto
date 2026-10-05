/**
 * Mount smoke test for MarketplaceMenuPage.vue.
 *
 * REGRESSION GUARD: this page had a temporal-dead-zone crash —
 * `watch(() => form.fulfillment_type, ...)` was registered BEFORE `const form`
 * was declared. watch() evaluates its source getter synchronously at
 * registration, so it hit `form` in the TDZ → "Cannot access 'form' before
 * initialization" → setup() threw → blank page. It shipped because NOTHING
 * mounted this page in the test suite (only its extracted child components were
 * tested). This test mounts the page so any setup()-time crash fails CI.
 *
 * shallowMount runs the page's own setup() (the thing under test) while
 * auto-stubbing the child components.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatCurrency: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

vi.mock("../../composables/useVocabulary", () => ({
  useVocabulary: () => ({ catalog: { value: "Menu" } }),
}));

vi.mock("../../lib/api", () => ({
  default: { get: vi.fn().mockResolvedValue({ data: {} }), post: vi.fn() },
}));

// A fresh key per mint, so a test can tell a reused key from a rotated one (L14).
vi.mock("../../lib/idempotency", () => {
  let n = 0;
  return { newIdempotencyKey: () => `test-idem-key-${++n}` };
});

// MarketplaceMenuPage reads route.params.slug at setup and uses the router.
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { slug: "demo" }, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import api from "../../lib/api";
import { useCustomerStore } from "../../stores/customer";
import { useToastStore } from "../../stores/toast";
import MarketplaceMenuPage from "../MarketplaceMenuPage.vue";

const mountPage = () =>
  shallowMount(MarketplaceMenuPage, {
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

describe("MarketplaceMenuPage — mount smoke", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("mounts without a setup() crash (TDZ regression: watch before const form)", async () => {
    let wrapper;
    // The TDZ bug threw synchronously inside setup(), so mount() itself would
    // throw. This assertion is the guard.
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
  });
});

describe("MarketplaceMenuPage — guest pickup payment payload", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  // Regression guard: a guest (unauthenticated) has no wallet to draw on, so the
  // marketplace order must NOT send use_wallet for a guest pickup order. Before the fix
  // the `else` branch set use_wallet=true unconditionally.
  it("does not send use_wallet for an unauthenticated guest pickup order", async () => {
    api.post.mockResolvedValueOnce({ data: { order_number: "A123" } });
    const wrapper = mountPage();
    await flushPromises();

    // Guest (no customer in the store) placing a pickup order.
    wrapper.vm.form.fulfillment_type = "pickup";
    wrapper.vm.form.customer_name = "Sara";
    wrapper.vm.form.customer_phone = "0612345678";
    wrapper.vm.cart.push({ slug: "burger", qty: 1 });
    await flushPromises();

    await wrapper.vm.placeOrder();
    await flushPromises();

    expect(api.post).toHaveBeenCalledWith("/marketplace/order/", expect.any(Object));
    const payload = api.post.mock.calls[0][1];
    expect(payload.use_wallet).toBeUndefined();
    expect(payload.payment_method).toBeUndefined();
    expect(payload.fulfillment_type).toBe("pickup");
  });
});

describe("MarketplaceMenuPage — menu fetch error states", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  const failMenuWith = (status) =>
    api.get.mockImplementation((url) =>
      String(url).includes("/marketplace/menu/")
        ? Promise.reject({ response: { status } })
        : Promise.resolve({ data: {} }),
    );

  // A 404 means this slug has no storefront — permanent. It must show the
  // "not found" state (Browse, no Retry), NOT the retryable error panel whose
  // Retry would only re-404.
  it("shows the not-found state (not the retryable error) on a 404", async () => {
    failMenuWith(404);
    const wrapper = mountPage();
    await flushPromises();
    expect(wrapper.vm.notFound).toBe(true);
    expect(wrapper.vm.fetchError).toBe(false);
  });

  // A transient/5xx failure IS retryable — it must show the error panel with
  // Retry, not the permanent not-found state.
  it("shows the retryable error (not not-found) on a 500", async () => {
    failMenuWith(500);
    const wrapper = mountPage();
    await flushPromises();
    expect(wrapper.vm.fetchError).toBe(true);
    expect(wrapper.vm.notFound).toBe(false);
  });
});

// ── Shared fixtures for the checkout-correctness suites below ────────────────
const dishFixture = (over = {}) => ({
  id: 1, slug: "burger", name: "Burger", price: "10.00", effective_price: "10.00",
  is_available: true, option_groups: [], tags: [], ...over,
});
const menuFixture = (...dishes) => ({
  slug: "demo", name: "Demo", currency: "MAD", is_open: true,
  super_categories: [{ id: 1, name: "Mains", categories: [{ id: 1, name: "Burgers", dishes }] }],
});
const serveMenu = (menu) =>
  api.get.mockImplementation((url) =>
    Promise.resolve({ data: String(url).includes("/marketplace/menu/") ? menu : {} }),
  );
const menuFetchCount = () =>
  api.get.mock.calls.filter(([url]) => String(url).includes("/marketplace/menu/")).length;
const resetMocks = () => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  localStorage.clear(); // the marketplace cart is persisted per-restaurant
  api.get.mockImplementation(() => Promise.resolve({ data: {} }));
  api.post.mockReset();
  vi.stubGlobal("IntersectionObserver", class { observe() {} unobserve() {} disconnect() {} });
};

// ── H3: a rejected cart line must be actionable ──────────────────────────────
// The server rejects unorderable lines as { code: "items_unavailable", slugs: [...] }.
// The page used to show one generic message: no line named, nothing to remove, menu stale.
describe("MarketplaceMenuPage — items_unavailable rejection (H3)", () => {
  beforeEach(resetMocks);
  afterEach(() => vi.unstubAllGlobals());

  const mountWithBurgerInCart = async () => {
    serveMenu(menuFixture(dishFixture()));
    const wrapper = mountPage();
    await flushPromises();
    wrapper.vm.form.fulfillment_type = "pickup";
    wrapper.vm.form.customer_name = "Sara";
    wrapper.vm.form.customer_phone = "0612345678";
    wrapper.vm.cart.push({ slug: "burger", name: "Burger", qty: 1, price: "10.00", unitPrice: 10 });
    wrapper.vm.checkoutOpen = true;
    await flushPromises();
    return wrapper;
  };

  const rejectWith = (slugs) =>
    api.post.mockRejectedValueOnce({ response: { status: 400, data: { code: "items_unavailable", slugs } } });

  it("flags + names the rejected line, offers Remove, and refetches the menu without a skeleton flash", async () => {
    const wrapper = await mountWithBurgerInCart();
    expect(wrapper.vm.unavailableSlugs.size).toBe(0);
    const fetchesBefore = menuFetchCount();

    rejectWith(["burger"]);
    await wrapper.vm.placeOrder();
    await flushPromises();

    expect(wrapper.vm.unavailableSlugs.has("burger")).toBe(true);
    expect(wrapper.vm.checkoutError).toBe('cartPage.itemsUnavailable({"items":"Burger"})');
    expect(wrapper.text()).toContain("cartPage.removeUnavailableItems");
    // Background refetch: the storefront catches up, and the menu never flipped to the skeleton.
    expect(menuFetchCount()).toBe(fetchesBefore + 1);
    expect(wrapper.vm.loading).toBe(false);
  });

  it("Remove drops the rejected line, clears the error and closes the emptied drawer", async () => {
    const wrapper = await mountWithBurgerInCart();
    rejectWith(["burger"]);
    await wrapper.vm.placeOrder();
    await flushPromises();

    const removeBtn = wrapper.findAll("button").find((b) => b.text().includes("cartPage.removeUnavailableItems"));
    expect(removeBtn).toBeTruthy();
    await removeBtn.trigger("click");
    await flushPromises();

    expect(wrapper.vm.cart).toHaveLength(0);
    expect(wrapper.vm.unavailableSlugs.size).toBe(0);
    expect(wrapper.vm.checkoutError).toBe("");
    expect(wrapper.vm.checkoutOpen).toBe(false);
  });

  it("only the rejected lines are removed — the rest of the cart survives", async () => {
    const wrapper = await mountWithBurgerInCart();
    wrapper.vm.cart.push({ slug: "fries", name: "Fries", qty: 1, price: "5.00", unitPrice: 5 });
    rejectWith(["burger"]);
    await wrapper.vm.placeOrder();
    await flushPromises();

    wrapper.vm.removeUnavailable();
    expect(wrapper.vm.cart.map((i) => i.slug)).toEqual(["fries"]);
    expect(wrapper.vm.checkoutOpen).toBe(true); // not emptied → drawer stays
  });

  it("lowering the quantity lapses a stale rejection (e.g. 'only 1 left') so the customer can retry", async () => {
    const wrapper = await mountWithBurgerInCart();
    wrapper.vm.cart[0].qty = 2;
    rejectWith(["burger"]);
    await wrapper.vm.placeOrder();
    await flushPromises();
    expect(wrapper.vm.unavailableSlugs.has("burger")).toBe(true);

    wrapper.vm.cart[0].qty = 1;
    await flushPromises();
    expect(wrapper.vm.unavailableSlugs.size).toBe(0);
  });

  it("the background refetch never overwrites what the customer chose/typed mid-checkout", async () => {
    serveMenu({ ...menuFixture(dishFixture()), delivery_enabled: true });
    localStorage.setItem("mkt:fulfillment:demo", "delivery"); // a remembered preference that a refetch would re-apply
    const wrapper = mountPage();
    await flushPromises();
    useCustomerStore().setCustomer({ id: 1, name: "Ali", phone: "0611", wallet_balance: "500.00" });
    wrapper.vm.form.fulfillment_type = "pickup";
    wrapper.vm.form.customer_name = "Alicia (typed)";
    wrapper.vm.form.customer_phone = "0699999999";
    wrapper.vm.cart.push({ slug: "burger", name: "Burger", qty: 1, price: "10.00", unitPrice: 10 });
    await flushPromises();

    rejectWith(["burger"]);
    await wrapper.vm.placeOrder();
    await flushPromises();

    expect(wrapper.vm.form.customer_name).toBe("Alicia (typed)");
    expect(wrapper.vm.form.customer_phone).toBe("0699999999");
    expect(wrapper.vm.form.fulfillment_type).toBe("pickup");
  });

  it("ignores rejected slugs that aren't in the cart and falls back to the generic message", async () => {
    const wrapper = await mountWithBurgerInCart();
    rejectWith(["something-else"]);
    await wrapper.vm.placeOrder();
    await flushPromises();
    expect(wrapper.vm.unavailableSlugs.size).toBe(0);
    expect(wrapper.vm.checkoutError).toBe("mktMenu.itemsUnavailable");
  });
});

// ── H3 (menu side): per-dish schedule / combo flags from the marketplace payload ──
describe("MarketplaceMenuPage — schedule / combo-unavailable dishes", () => {
  beforeEach(resetMocks);
  afterEach(() => vi.unstubAllGlobals());

  it("renders a dish outside its time window as 'not available now' and a broken combo as sold out", async () => {
    serveMenu(menuFixture(
      dishFixture({ id: 1, slug: "ok", name: "Okay Dish" }),
      dishFixture({ id: 2, slug: "late", name: "Late Dish", is_schedule_available: false }),
      dishFixture({ id: 3, slug: "combo", name: "Combo Dish", combo_unavailable: true }),
    ));
    const wrapper = mountPage();
    await flushPromises();

    const { isDishOrderable } = wrapper.vm;
    expect(isDishOrderable({ is_available: true })).toBe(true);
    expect(isDishOrderable({ is_available: true, is_schedule_available: null })).toBe(true); // no schedule
    expect(isDishOrderable({ is_available: true, is_schedule_available: false })).toBe(false);
    expect(isDishOrderable({ is_available: true, combo_unavailable: true })).toBe(false);
    expect(isDishOrderable({ is_available: false })).toBe(false);

    expect(wrapper.text()).toContain("mktMenu.notAvailableNow");
    expect(wrapper.text()).toContain("mktMenu.soldOut");
    // Only the orderable dish still gets an "Add" button.
    const addButtons = wrapper.findAll("button").filter((b) => b.text().includes("mktMenu.addToCart"));
    expect(addButtons).toHaveLength(1);
  });

  it("treats a cart line whose dish just went out of window / combo-unmakeable as unavailable", async () => {
    serveMenu(menuFixture(
      dishFixture({ id: 2, slug: "late", name: "Late Dish", is_schedule_available: false }),
      dishFixture({ id: 3, slug: "combo", name: "Combo Dish", combo_unavailable: true }),
      dishFixture({ id: 1, slug: "ok", name: "Okay Dish" }),
    ));
    const wrapper = mountPage();
    await flushPromises();
    for (const slug of ["late", "combo", "ok"]) {
      wrapper.vm.cart.push({ slug, name: slug, qty: 1, price: "10.00", unitPrice: 10 });
    }
    await flushPromises();
    expect([...wrapper.vm.unavailableSlugs].sort()).toEqual(["combo", "late"]);
  });
});

// ── M1: cash on handover vs "Schedule for later" ─────────────────────────────
describe("MarketplaceMenuPage — cash on handover vs scheduled order (M1)", () => {
  beforeEach(resetMocks);
  afterEach(() => vi.unstubAllGlobals());

  it("never reports (or sends) cash for a scheduled order — the wallet pays, and the UI says so", async () => {
    serveMenu({ ...menuFixture(dishFixture()), cod_eligible: true });
    api.post.mockResolvedValueOnce({ data: { order_number: "A1" } });
    const wrapper = mountPage();
    await flushPromises();
    useCustomerStore().setCustomer({ id: 1, name: "Ali", phone: "0611", wallet_balance: "500.00" });
    wrapper.vm.form.fulfillment_type = "pickup";
    wrapper.vm.form.customer_name = "Ali";
    wrapper.vm.form.customer_phone = "0611111111";
    wrapper.vm.cart.push({ slug: "burger", name: "Burger", qty: 1, price: "10.00", unitPrice: 10 });
    wrapper.vm.paymentMethod = "cash";
    await flushPromises();

    expect(wrapper.vm.codChosen).toBe(true); // immediate order: cash is honoured

    wrapper.vm.scheduleEnabled = true;
    await flushPromises();
    expect(wrapper.vm.scheduleBlocksCash).toBe(true);
    expect(wrapper.vm.codChosen).toBe(false);

    // Placing a (valid) scheduled order must not claim cash.
    const d = new Date(Date.now() + 2 * 60 * 60 * 1000);
    const pad = (n) => String(n).padStart(2, "0");
    wrapper.vm.scheduledFor = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    await wrapper.vm.placeOrder();
    await flushPromises();
    const payload = api.post.mock.calls[0][1];
    expect(payload.payment_method).toBeUndefined();
    expect(payload.use_wallet).toBe(true);
    expect(payload.scheduled_for).toBeTruthy();
  });
});

// ── M2: guests can't order pickup/delivery — prompt sign-in instead of "pay in person" ──
describe("MarketplaceMenuPage — guest pickup checkout (M2)", () => {
  beforeEach(resetMocks);
  afterEach(() => vi.unstubAllGlobals());

  it("shows a sign-in prompt (not a 'pay in person' promise) and opens the auth modal from it", async () => {
    serveMenu(menuFixture(dishFixture()));
    const wrapper = mountPage();
    await flushPromises();
    wrapper.vm.form.fulfillment_type = "pickup";
    wrapper.vm.cart.push({ slug: "burger", name: "Burger", qty: 1, price: "10.00", unitPrice: 10 });
    wrapper.vm.checkoutOpen = true;
    await flushPromises();

    expect(wrapper.text()).not.toContain("mktMenu.guestPickupPayNote");
    expect(wrapper.text()).toContain("mktMenu.guestSignInToOrder");

    expect(wrapper.vm.showAuthModal).toBe(false);
    const signIn = wrapper.findAll("button").find((b) => b.text().includes("mktMenu.authRequiredSignIn"));
    expect(signIn).toBeTruthy();
    await signIn.trigger("click");
    expect(wrapper.vm.showAuthModal).toBe(true);
  });

  it("a signed-in customer doesn't see the guest prompt", async () => {
    serveMenu(menuFixture(dishFixture()));
    const wrapper = mountPage();
    await flushPromises();
    useCustomerStore().setCustomer({ id: 1, name: "Ali", phone: "0611", wallet_balance: "500.00" });
    wrapper.vm.form.fulfillment_type = "pickup";
    wrapper.vm.cart.push({ slug: "burger", name: "Burger", qty: 1, price: "10.00", unitPrice: 10 });
    wrapper.vm.checkoutOpen = true;
    await flushPromises();
    expect(wrapper.text()).not.toContain("mktMenu.guestSignInToOrder");
  });
});

// ── M5: wallet balance must not go stale after an order / a 402 ──────────────
describe("MarketplaceMenuPage — customer refresh after money events (M5)", () => {
  beforeEach(resetMocks);
  afterEach(() => vi.unstubAllGlobals());

  const mountSignedIn = async () => {
    serveMenu(menuFixture(dishFixture()));
    const wrapper = mountPage();
    await flushPromises();
    const customerStore = useCustomerStore();
    customerStore.setCustomer({ id: 1, name: "Ali", phone: "0611", wallet_balance: "500.00" });
    const spy = vi.spyOn(customerStore, "fetchCustomer");
    wrapper.vm.form.fulfillment_type = "pickup";
    wrapper.vm.form.customer_name = "Ali";
    wrapper.vm.form.customer_phone = "0611111111";
    wrapper.vm.cart.push({ slug: "burger", name: "Burger", qty: 1, price: "10.00", unitPrice: 10 });
    await flushPromises();
    return { wrapper, spy };
  };

  it("force-refreshes the customer after a successful order", async () => {
    const { wrapper, spy } = await mountSignedIn();
    api.post.mockResolvedValueOnce({ data: { order_number: "A1" } });
    await wrapper.vm.placeOrder();
    await flushPromises();
    expect(spy).toHaveBeenCalledWith(true);
  });

  it("re-syncs the balance on a 402 wallet_insufficient", async () => {
    const { wrapper, spy } = await mountSignedIn();
    api.post.mockRejectedValueOnce({ response: { status: 402, data: { code: "wallet_insufficient" } } });
    await wrapper.vm.placeOrder();
    await flushPromises();
    expect(spy).toHaveBeenCalledWith(true);
    expect(wrapper.vm.checkoutError).toBe("mktMenu.walletInsufficientError");
  });

  it("does not hit the session endpoint for a guest order", async () => {
    serveMenu(menuFixture(dishFixture()));
    api.post.mockResolvedValueOnce({ data: { order_number: "A1" } });
    const wrapper = mountPage();
    await flushPromises();
    const spy = vi.spyOn(useCustomerStore(), "fetchCustomer");
    wrapper.vm.form.fulfillment_type = "pickup";
    wrapper.vm.form.customer_name = "Sara";
    wrapper.vm.form.customer_phone = "0612345678";
    wrapper.vm.cart.push({ slug: "burger", name: "Burger", qty: 1, price: "10.00", unitPrice: 10 });
    await wrapper.vm.placeOrder();
    await flushPromises();
    expect(spy).not.toHaveBeenCalledWith(true);
  });
});

// ── L6: the points projection must equal what MarketplacePlaceOrderView credits ──
describe("MarketplaceMenuPage — loyalty earn projection (L6)", () => {
  beforeEach(resetMocks);
  afterEach(() => vi.unstubAllGlobals());

  const LOYALTY = {
    enabled: true, points_per_unit: 10, points_value: "0.0100", redeem_threshold: 100,
    tier_enabled: true, tier_silver_threshold: 500, tier_gold_threshold: 2000,
    tier_silver_multiplier: "1.50", tier_gold_multiplier: "2.00",
    first_order_bonus_points: 50, first_order_bonus_eligible: true,
  };

  it("earns on the FOOD subtotal (not the delivery fee) × tier, + the first-order bonus; nothing for a guest", async () => {
    serveMenu({ ...menuFixture(dishFixture()), delivery_enabled: true, delivery_fee: "20.00", loyalty: LOYALTY });
    const wrapper = mountPage();
    await flushPromises();
    wrapper.vm.form.fulfillment_type = "delivery";
    wrapper.vm.cart.push({ slug: "burger", name: "Burger", qty: 1, price: "10.00", unitPrice: 10 });
    await flushPromises();
    expect(wrapper.vm.deliveryFee).toBe(20); // sanity: a fee the old projection counted

    // A guest never earns (the server only credits a signed-in customer).
    expect(wrapper.vm.loyaltyEarnProjection).toBe(0);

    useCustomerStore().setCustomer({ id: 1, name: "Ali", phone: "0611", wallet_balance: "500.00", lifetime_loyalty_points: 600 });
    await flushPromises();
    // floor(10 × 10 × 1.5) + 50 — the old floor((10 + 20) × 10) was 300.
    expect(wrapper.vm.loyaltyEarnProjection).toBe(200);
  });
});

// ── L14: the idempotency key identifies ONE cart snapshot ────────────────────
describe("MarketplaceMenuPage — checkout retry idempotency (L14)", () => {
  beforeEach(resetMocks);
  afterEach(() => vi.unstubAllGlobals());

  const mountSignedInPickup = async () => {
    serveMenu(menuFixture(dishFixture()));
    const wrapper = mountPage();
    await flushPromises();
    useCustomerStore().setCustomer({ id: 1, name: "Ali", phone: "0611", wallet_balance: "500.00" });
    wrapper.vm.form.fulfillment_type = "pickup";
    wrapper.vm.form.customer_name = "Ali";
    wrapper.vm.form.customer_phone = "0611111111";
    wrapper.vm.cart.push({ slug: "burger", name: "Burger", qty: 1, price: "10.00", unitPrice: 10 });
    await flushPromises();
    return wrapper;
  };
  const sentKey = (call) => api.post.mock.calls[call][1].idempotency_key;
  const lostResponse = () => api.post.mockRejectedValueOnce(new Error("Network Error"));

  it("after a lost response, even an EDITED cart keeps the key — the lost attempt may have charged", async () => {
    const wrapper = await mountSignedInPickup();
    const show = vi.spyOn(useToastStore(), "show");
    lostResponse();
    await wrapper.vm.placeOrder();
    lostResponse();
    await wrapper.vm.placeOrder(); // unchanged cart → same key (server would replay)
    wrapper.vm.cart[0].qty = 2;
    await flushPromises();
    // The lost attempt had placed the 1-burger order: the server replays it.
    api.post.mockResolvedValueOnce({ data: { order_number: "A1", idempotent_replay: true } });
    await wrapper.vm.placeOrder();
    await flushPromises();

    expect(sentKey(1)).toBe(sentKey(0));
    expect(sentKey(2)).toBe(sentKey(0)); // no second order / charge
    // Honest: that order lacks the edit — say so, and keep the edited cart.
    expect(show).toHaveBeenCalledWith("cartPage_order.orderAlreadyPlacedEditsKept", "warning", 9000);
    expect(show).not.toHaveBeenCalledWith("cartPage_order.orderAlreadyPlaced", "info");
    expect(wrapper.vm.cart).toHaveLength(1);
    expect(wrapper.vm.cart[0].qty).toBe(2);
  });

  it("after a definitive 4xx rejection, an edited cart gets a new key", async () => {
    const wrapper = await mountSignedInPickup();
    api.post.mockRejectedValueOnce({ response: { status: 400, data: { code: "stale_options" } } });
    await wrapper.vm.placeOrder();
    wrapper.vm.cart[0].qty = 2;
    await flushPromises();
    api.post.mockResolvedValueOnce({ data: { order_number: "A2" } });
    await wrapper.vm.placeOrder();
    await flushPromises();

    expect(sentKey(1)).not.toBe(sentKey(0));
  });

  it("says a replayed order had already gone through", async () => {
    const wrapper = await mountSignedInPickup();
    const show = vi.spyOn(useToastStore(), "show");
    api.post.mockResolvedValue({ data: { order_number: "A1", idempotent_replay: true } });
    await wrapper.vm.placeOrder();
    await flushPromises();
    expect(wrapper.vm.checkoutError).toBe("");
    expect(api.post).toHaveBeenCalledWith("/marketplace/order/", expect.any(Object));
    expect(show).toHaveBeenCalledWith("cartPage_order.orderAlreadyPlaced", "info");
  });
});
