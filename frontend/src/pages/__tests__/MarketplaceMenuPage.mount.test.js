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

import MarketplaceMenuPage from "../MarketplaceMenuPage.vue";

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
      wrapper = shallowMount(MarketplaceMenuPage, {
        global: {
          stubs: {
            RouterLink: { template: "<a><slot /></a>" },
            Transition: { template: "<slot />" },
            Teleport: { template: "<slot />" },
          },
        },
      });
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
  });
});
