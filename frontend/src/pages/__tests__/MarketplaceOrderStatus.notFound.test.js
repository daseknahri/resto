/**
 * MarketplaceOrderStatus.vue — 404 vs transient-error branching.
 *
 * A dead / expired / mistyped order link returns 404. Retrying a 404 loops forever,
 * so the page must show a distinct "order not found" card with a way back to the
 * marketplace, NOT the transient "Retry" error. A genuine transient failure (500 /
 * network) must still show the retryable error card.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { ref } from "vue";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatDateTime: (v) => String(v),
    formatCurrency: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

vi.mock("../../composables/useOrderRating", () => ({
  useOrderRating: () => ({
    score: ref(0),
    comment: ref(""),
    submitting: ref(false),
    submit: vi.fn(),
  }),
}));

vi.mock("../../lib/api", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

const mockPush = vi.fn();
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { slug: "demo", orderNumber: "X404" }, query: {} }),
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
}));

import api from "../../lib/api";
import MarketplaceOrderStatus from "../MarketplaceOrderStatus.vue";

const mountPage = () =>
  mount(MarketplaceOrderStatus, {
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
        "router-link": { template: "<a><slot /></a>" },
        DeliveryTracker: true,
        CustomerAuthModal: true,
        Transition: { template: "<slot />" },
      },
    },
  });

describe("MarketplaceOrderStatus — 404 vs transient error", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("shows the not-found card (no Retry) on a 404 and offers a way back to the marketplace", async () => {
    api.get.mockRejectedValue({ response: { status: 404 } });
    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.text()).toContain("mktOrderStatus.notFoundTitle");
    expect(wrapper.text()).toContain("mktOrderStatus.notFoundCta");
    // The transient error card / Retry must NOT show for a permanent 404.
    expect(wrapper.text()).not.toContain("mktOrderStatus.loadError");
    expect(wrapper.text()).not.toContain("common.retry");
  });

  it("shows the retryable error card on a transient (500) failure", async () => {
    api.get.mockRejectedValue({ response: { status: 500 } });
    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.text()).toContain("mktOrderStatus.loadError");
    expect(wrapper.text()).toContain("common.retry");
    expect(wrapper.text()).not.toContain("mktOrderStatus.notFoundTitle");
  });
});
