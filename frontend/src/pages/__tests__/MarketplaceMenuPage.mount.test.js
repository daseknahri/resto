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
import { describe, it, expect, vi, beforeEach } from "vitest";
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

vi.mock("../../lib/idempotency", () => ({
  newIdempotencyKey: () => "test-idem-key",
}));

// MarketplaceMenuPage reads route.params.slug at setup and uses the router.
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { slug: "demo" }, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import api from "../../lib/api";
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
