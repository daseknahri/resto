/**
 * CustomerAccount.vue — order-list behaviour owned by the page (the Orders tab child,
 * CustomerAccountOrders, only renders + emits; every fetch / cancel lives here).
 *
 *  - M6: a `scheduled` (prepaid advance) order is live — it gets the always-visible
 *    live-order banner with a "Scheduled" label and its due time.
 *  - L1: a too-late self-cancel is refused by the server with 409 `not_cancellable`
 *    (tenant cancel view) or `cancel_too_late` (marketplace cancel view). The page used
 *    to look for a `cannot_cancel` code that is never sent, so the customer got a generic
 *    "try again" and the Cancel button stayed. It must show the "too late" copy and
 *    refetch that order so its status catches up and can_cancel flips to false.
 *
 * Mock style follows CustomerAccount.mount.test.js (URL-routed api, key-echo t, hoisted
 * stubs, localStorage cleared first). confirm() and the toast store are mocked so the
 * cancel flow runs headless and the toast copy can be asserted.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

const RouterLinkStub = vi.hoisted(() => ({
  name: "RouterLink",
  props: ["to"],
  template: "<a><slot /></a>",
}));
const routes = vi.hoisted(() => ({ current: {} }));
const toastShow = vi.hoisted(() => vi.fn());

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatPrice: (v) => String(v),
    formatCurrency: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

vi.mock("../../lib/api", () => {
  const respond = (url = "") => {
    const table = routes.current || {};
    for (const key of Object.keys(table)) {
      if (url.includes(key)) return Promise.resolve(table[key]);
    }
    return Promise.resolve({ data: {} });
  };
  return {
    default: {
      get: vi.fn((url) => respond(url)),
      post: vi.fn(() => Promise.resolve({ data: {} })),
      patch: vi.fn(() => Promise.resolve({ data: {} })),
      delete: vi.fn(() => Promise.resolve({ data: {} })),
      put: vi.fn(() => Promise.resolve({ data: {} })),
    },
  };
});

// ?tab=orders deep-link → the Orders tab (and its CustomerAccountOrders child) renders.
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
  useRoute: () => ({ query: { tab: "orders" }, params: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("../../composables/useConfirmModal", () => ({
  useConfirmModal: () => ({ confirm: vi.fn(() => Promise.resolve(true)) }),
}));

vi.mock("../../stores/toast", () => ({
  useToastStore: () => ({ show: toastShow }),
}));

import api from "../../lib/api";
import CustomerAccountOrders from "../../components/CustomerAccountOrders.vue";
import CustomerAccount from "../CustomerAccount.vue";

const SESSION = {
  data: {
    customer: { id: 7, name: "Sara", phone: "0612345678", phone_verified: true, wallet_balance: "10.00", loyalty_points: 0 },
    platform: { enabled_verticals: ["food"], psp_topup_enabled: false },
  },
};

const mountPage = () =>
  shallowMount(CustomerAccount, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

const settle = async () => {
  await flushPromises();
  await flushPromises();
};

describe("CustomerAccount — order list behaviour", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    routes.current = {};
    vi.clearAllMocks();
  });

  it("M6: a scheduled order gets the live-order banner with its label and due time", async () => {
    const due = "2026-07-02T19:30:00Z";
    routes.current = {
      "/customer/session/": SESSION,
      "/customer/orders/?page=": {
        data: {
          orders: [{ order_number: "S1", status: "scheduled", scheduled_for: due, total: "40.00", currency: "MAD", items: [] }],
          has_more: false,
        },
      },
    };
    const wrapper = mountPage();
    await settle();

    const time = new Intl.DateTimeFormat("en", {
      weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    }).format(new Date(due));
    const text = wrapper.text();
    expect(text).toContain("customerAccount.trackOrder");
    expect(text).toContain("orderStatus.statusScheduled");
    expect(text).toContain(`customerAccount.scheduledDue(${JSON.stringify({ time })})`);
    // The same set drives the Orders tab's active styling.
    expect(wrapper.findComponent(CustomerAccountOrders).props("activeStatuses").has("scheduled")).toBe(true);
    wrapper.unmount();
  });

  it("L1: a 409 not_cancellable shows the too-late copy and refetches that order", async () => {
    routes.current = {
      "/customer/session/": SESSION,
      "/customer/orders/?page=": {
        data: {
          orders: [{ order_number: "A1", status: "confirmed", can_cancel: true, total: "40.00", currency: "MAD", items: [] }],
          has_more: false,
        },
      },
      // The refetch: the kitchen has started it.
      "/order-status/A1/": { data: { order_number: "A1", status: "preparing", can_cancel: false } },
    };
    api.post.mockImplementationOnce(() =>
      Promise.reject({ response: { status: 409, data: { code: "not_cancellable" } } }),
    );
    const wrapper = mountPage();
    await settle();

    const child = wrapper.findComponent(CustomerAccountOrders);
    child.vm.$emit("cancel-order", child.props("apiOrders")[0]);
    await settle();

    expect(api.post).toHaveBeenCalledWith("/order-status/A1/cancel/");
    expect(toastShow).toHaveBeenCalledWith("customerAccount.orderCannotCancel", "error");
    expect(toastShow).not.toHaveBeenCalledWith("customerAccount.orderCancelFailed", "error");
    expect(api.get).toHaveBeenCalledWith("/order-status/A1/", undefined);
    const row = wrapper.findComponent(CustomerAccountOrders).props("apiOrders")[0];
    expect(row.status).toBe("preparing");
    expect(row.can_cancel).toBe(false);
    wrapper.unmount();
  });

  it("L1: a marketplace 409 cancel_too_late shows the too-late copy and refetches that order", async () => {
    routes.current = {
      "/customer/session/": SESSION,
      "/customer/orders/all/": {
        data: {
          orders: [{ order_number: "M1", restaurant_slug: "demo", restaurant_name: "Demo", status: "pending", can_cancel: true, total: "30.00", currency: "MAD" }],
          has_more: false,
        },
      },
      "/marketplace/order/M1/": { data: { order_number: "M1", status: "confirmed", can_cancel: true } },
    };
    api.post.mockImplementationOnce(() =>
      Promise.reject({ response: { status: 409, data: { code: "cancel_too_late" } } }),
    );
    const wrapper = mountPage();
    await settle();

    const child = wrapper.findComponent(CustomerAccountOrders);
    child.vm.$emit("cancel-marketplace-order", child.props("marketplaceOrders")[0]);
    await settle();

    expect(toastShow).toHaveBeenCalledWith("customerAccount.orderCannotCancel", "error");
    expect(api.get).toHaveBeenCalledWith("/marketplace/order/M1/", { params: { restaurant: "demo" } });
    const row = wrapper.findComponent(CustomerAccountOrders).props("marketplaceOrders")[0];
    // The server's fresh state wins over the optimistic hide.
    expect(row.status).toBe("confirmed");
    expect(row.can_cancel).toBe(true);
    wrapper.unmount();
  });

  it("L1: any other failure keeps the generic retry copy (no refetch)", async () => {
    routes.current = {
      "/customer/session/": SESSION,
      "/customer/orders/?page=": {
        data: {
          orders: [{ order_number: "A2", status: "confirmed", can_cancel: true, total: "40.00", currency: "MAD", items: [] }],
          has_more: false,
        },
      },
    };
    api.post.mockImplementationOnce(() => Promise.reject({ response: { status: 500, data: {} } }));
    const wrapper = mountPage();
    await settle();

    const child = wrapper.findComponent(CustomerAccountOrders);
    child.vm.$emit("cancel-order", child.props("apiOrders")[0]);
    await settle();

    expect(toastShow).toHaveBeenCalledWith("customerAccount.orderCancelFailed", "error");
    expect(api.get).not.toHaveBeenCalledWith("/order-status/A2/", undefined);
    wrapper.unmount();
  });
});
