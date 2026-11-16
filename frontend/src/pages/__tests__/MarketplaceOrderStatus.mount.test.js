/**
 * MarketplaceOrderStatus.vue — mount tests for the S2-A fixes (C-01, C-04, C-05).
 *
 * Pattern-faithful to MarketplaceOrderStatus.notFound.test.js (same mocks for
 * useI18n / useOrderRating / lib/api / vue-router, full `mount` so the real
 * stepper + rating template renders). PushPrimingSheet is stubbed with an
 * exposed `maybeShow` spy so C-04 can assert the soft-ask — and only the
 * soft-ask — fires on mount.
 *
 * C-01: a scheduled order gets a leading "scheduled" step and progress > 0%
 *   (was: no step matched, currentStatusIdx -1, progress 0%).
 * C-04: no raw Notification.requestPermission() on mount; the priming sheet's
 *   maybeShow is called at the just-placed moment and never otherwise.
 * C-05: star buttons carry a translated "N out of 5" label and roving tabindex
 *   with Arrow/Home/End keyboard support (mirrors OrderStatus.vue).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { ref, nextTick } from "vue";

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
  useRoute: () => ({ params: { slug: "demo", orderNumber: "X1" }, query: {} }),
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
}));

import api from "../../lib/api";
import MarketplaceOrderStatus from "../MarketplaceOrderStatus.vue";

// The priming sheet, stubbed with its real contract: the page calls
// pushPrimingSheet.value?.maybeShow?.() at the just-placed moment.
const maybeShowSpy = vi.fn();
const PushPrimingSheetStub = {
  name: "PushPrimingSheet",
  setup(_, { expose }) {
    expose({ maybeShow: maybeShowSpy });
    return () => null;
  },
};

const mountPage = () =>
  mount(MarketplaceOrderStatus, {
    // attachTo: the C-05 roving-tabindex tests assert document.activeElement
    // after onStarKey focuses the next star — .focus() is a no-op on a
    // detached tree, so the wrapper must live in the document.
    attachTo: document.body,
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
        "router-link": { template: "<a><slot /></a>" },
        DeliveryTracker: true,
        CustomerAuthModal: true,
        PushPrimingSheet: PushPrimingSheetStub,
        Transition: { template: "<slot />" },
      },
    },
  });

let _order = null;
let requestPermissionSpy;

const baseOrder = (overrides = {}) => ({
  restaurant_name: "Demo",
  order_number: "X1",
  status: "pending",
  fulfillment_type: "pickup",
  currency: "MAD",
  total: "50.00",
  delivery_fee: "0",
  tip_amount: "0",
  promotion_discount: "0",
  loyalty_discount: "0",
  wallet_amount_paid: "0",
  points_earned: 0,
  items: [{ dish_name: "Pizza", qty: 1, subtotal: "50.00", options: [] }],
  ...overrides,
});

describe("MarketplaceOrderStatus — scheduled stepper (C-01)", () => {
  let wrapper;
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    requestPermissionSpy = vi.fn(() => Promise.resolve("granted"));
    globalThis.Notification = { permission: "default", requestPermission: requestPermissionSpy };
    api.get.mockImplementation((url) => {
      if (String(url).includes("/marketplace/track/")) return Promise.resolve({ data: null });
      return Promise.resolve({ data: _order });
    });
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    delete globalThis.Notification;
  });

  it("a scheduled pickup order shows a current 'scheduled' step and 1/6 = 17% progress (was 0%)", async () => {
    _order = baseOrder({ status: "scheduled", scheduled_for: "2026-11-17T12:00:00Z" });
    wrapper = mountPage();
    await flushPromises();

    expect(wrapper.find('[role="progressbar"]').attributes("aria-valuenow")).toBe("17");
    const current = wrapper.find('[aria-current="step"]');
    expect(current.exists()).toBe(true);
    expect(current.attributes("aria-label")).toContain("mktOrderStatus.scheduled");
    expect(wrapper.text()).toContain("mktOrderStatus.scheduledFor");
  });

  it("a scheduled delivery order shows 1/7 = 14% progress", async () => {
    _order = baseOrder({
      status: "scheduled",
      fulfillment_type: "delivery",
      scheduled_for: "2026-11-17T12:00:00Z",
    });
    wrapper = mountPage();
    await flushPromises();

    expect(wrapper.find('[role="progressbar"]').attributes("aria-valuenow")).toBe("14");
    expect(wrapper.find('[aria-current="step"]').attributes("aria-label")).toContain("mktOrderStatus.scheduled");
  });

  it("a non-scheduled order has no 'scheduled' step and keeps its old progress", async () => {
    _order = baseOrder({ status: "pending" });
    wrapper = mountPage();
    await flushPromises();

    expect(wrapper.find('[role="progressbar"]').attributes("aria-valuenow")).toBe("20");
    expect(wrapper.find('[aria-current="step"]').attributes("aria-label")).toContain("mktOrderStatus.pending");
    expect(wrapper.find('[aria-current="step"]').attributes("aria-label")).not.toContain("mktOrderStatus.scheduled");
  });
});

describe("MarketplaceOrderStatus — notification permission (C-04)", () => {
  let wrapper;
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    requestPermissionSpy = vi.fn(() => Promise.resolve("granted"));
    globalThis.Notification = { permission: "default", requestPermission: requestPermissionSpy };
    api.get.mockImplementation((url) => {
      if (String(url).includes("/marketplace/track/")) return Promise.resolve({ data: null });
      return Promise.resolve({ data: _order });
    });
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    delete globalThis.Notification;
  });

  it("on a just-placed order the priming sheet's maybeShow fires and no raw OS prompt is requested", async () => {
    _order = baseOrder({ status: "pending" });
    localStorage.setItem("mktLastOrderNumber", "X1");
    localStorage.setItem("mktLastOrderAt", String(Date.now()));
    wrapper = mountPage();
    await flushPromises();

    expect(maybeShowSpy).toHaveBeenCalledTimes(1);
    expect(requestPermissionSpy).not.toHaveBeenCalled();
  });

  it("on a plain visit neither the sheet nor a raw OS prompt fires", async () => {
    _order = baseOrder({ status: "pending" });
    wrapper = mountPage();
    await flushPromises();

    expect(maybeShowSpy).not.toHaveBeenCalled();
    expect(requestPermissionSpy).not.toHaveBeenCalled();
  });
});

describe("MarketplaceOrderStatus — rating widget a11y (C-05)", () => {
  let wrapper;
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    requestPermissionSpy = vi.fn(() => Promise.resolve("granted"));
    globalThis.Notification = { permission: "default", requestPermission: requestPermissionSpy };
    api.get.mockImplementation((url) => {
      if (String(url).includes("/marketplace/track/")) return Promise.resolve({ data: null });
      return Promise.resolve({ data: _order });
    });
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    delete globalThis.Notification;
  });

  const loadRated = async () => {
    _order = baseOrder({ status: "completed", has_rating: false });
    wrapper = mountPage();
    await flushPromises();
    return wrapper.findAll('[role="radio"]');
  };

  it("each star carries a translated label, not a bare number", async () => {
    const radios = await loadRated();
    expect(radios).toHaveLength(5);
    expect(radios[0].attributes("aria-label")).toBe('mktOrderStatus.ratingLabel({"score":1})');
    expect(radios[2].attributes("aria-label")).toBe('mktOrderStatus.ratingLabel({"score":3})');
    expect(radios[4].attributes("aria-label")).toBe('mktOrderStatus.ratingLabel({"score":5})');
  });

  it("only the first star is tabbable until one is chosen (roving tabindex)", async () => {
    const radios = await loadRated();
    expect(radios[0].attributes("tabindex")).toBe("0");
    for (const r of radios.slice(1)) expect(r.attributes("tabindex")).toBe("-1");

    // Choosing star 3 moves the single tab stop to it.
    await radios[2].trigger("click");
    await nextTick();
    const after = wrapper.findAll('[role="radio"]');
    expect(after[2].attributes("tabindex")).toBe("0");
    expect(after[0].attributes("tabindex")).toBe("-1");
    expect(after[2].attributes("aria-checked")).toBe("true");
  });

  it("ArrowRight / ArrowLeft move selection and focus across the stars", async () => {
    await loadRated();
    let radios = wrapper.findAll('[role="radio"]');
    await radios[2].trigger("click");
    await nextTick();

    radios = wrapper.findAll('[role="radio"]');
    await radios[2].trigger("keydown", { key: "ArrowRight" });
    await nextTick();
    radios = wrapper.findAll('[role="radio"]');
    expect(radios[3].attributes("aria-checked")).toBe("true");
    expect(radios[3].attributes("tabindex")).toBe("0");
    expect(document.activeElement).toBe(radios[3].element);

    await radios[3].trigger("keydown", { key: "ArrowLeft" });
    await nextTick();
    radios = wrapper.findAll('[role="radio"]');
    expect(radios[2].attributes("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(radios[2].element);
  });

  it("End jumps to 5 stars and Home back to 1", async () => {
    await loadRated();
    let radios = wrapper.findAll('[role="radio"]');
    await radios[1].trigger("keydown", { key: "End" });
    await nextTick();
    radios = wrapper.findAll('[role="radio"]');
    expect(radios[4].attributes("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(radios[4].element);

    await radios[4].trigger("keydown", { key: "Home" });
    await nextTick();
    radios = wrapper.findAll('[role="radio"]');
    expect(radios[0].attributes("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(radios[0].element);
  });
});
