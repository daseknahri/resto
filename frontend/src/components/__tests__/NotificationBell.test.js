/**
 * Unit tests for NotificationBell — header bell + unread badge for the inbox.
 *
 * Locks in: hidden for guests; polls the count-only endpoint while signed in; shows a
 * badge with the unread count (capped at 99+); toggles the inbox dropdown open/closed.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));

const getMock = vi.fn();
vi.mock("../../lib/api", () => ({
  default: {
    get: (...a) => getMock(...a),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// Stub the heavy inbox child so the bell test stays focused.
vi.mock("../NotificationInbox.vue", () => ({
  default: { name: "NotificationInbox", template: '<div class="inbox-stub" />' },
}));

import NotificationBell from "../NotificationBell.vue";
import { useCustomerStore } from "../../stores/customer";

function mountBell() {
  return mount(NotificationBell, {
    global: { stubs: { AppIcon: { template: "<i />" } } },
  });
}

describe("NotificationBell", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    getMock.mockReset();
    getMock.mockResolvedValue({ data: { unread_count: 0 } });
  });

  it("renders nothing for guests", () => {
    const store = useCustomerStore();
    store.setCustomer(null);
    const w = mountBell();
    expect(w.find("button").exists()).toBe(false);
  });

  it("polls unread count and shows a badge when signed in", async () => {
    getMock.mockResolvedValue({ data: { unread_count: 3 } });
    const store = useCustomerStore();
    store.setCustomer({ id: 1 });
    const w = mountBell();
    await flushPromises();
    expect(getMock).toHaveBeenCalledWith(
      "/customer/notifications/",
      expect.objectContaining({ params: { count_only: 1 } })
    );
    expect(w.text()).toContain("3");
  });

  it("caps the badge at 99+", async () => {
    getMock.mockResolvedValue({ data: { unread_count: 250 } });
    const store = useCustomerStore();
    store.setCustomer({ id: 1 });
    const w = mountBell();
    await flushPromises();
    expect(w.text()).toContain("99+");
  });

  it("toggles the inbox dropdown on click", async () => {
    const store = useCustomerStore();
    store.setCustomer({ id: 1 });
    const w = mountBell();
    await flushPromises();
    expect(w.find(".inbox-stub").exists()).toBe(false);
    await w.find("button").trigger("click");
    expect(w.find(".inbox-stub").exists()).toBe(true);
    await w.find("button").trigger("click");
    expect(w.find(".inbox-stub").exists()).toBe(false);
  });
});
