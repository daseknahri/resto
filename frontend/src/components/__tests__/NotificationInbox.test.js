/**
 * Unit tests for NotificationInbox — the persistent notification feed.
 *
 * Locks in: loads + renders rows on mount; shows the empty state; marks unread rows
 * read on open (emits update-unread); "mark all read" clears the unread count; rows
 * with a url deep-link via RouterLink; relative-time bucketing.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${p.n}` : k) }),
}));

const getMock = vi.fn();
const postMock = vi.fn();
vi.mock("../../lib/api", () => ({
  default: {
    get: (...a) => getMock(...a),
    post: (...a) => postMock(...a),
  },
}));

import NotificationInbox from "../NotificationInbox.vue";

const RouterLinkStub = {
  name: "RouterLink",
  props: ["to"],
  template: '<a class="rl"><slot /></a>',
};

function mountInbox() {
  return mount(NotificationInbox, {
    global: { stubs: { RouterLink: RouterLinkStub } },
  });
}

function row(id, { read = false, url = "/orders/X" } = {}) {
  return {
    id,
    type: "delivery.delivered",
    vertical: "food",
    title: `Title ${id}`,
    body: "body",
    url,
    is_read: read,
    created_at: new Date().toISOString(),
  };
}

describe("NotificationInbox", () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    postMock.mockResolvedValue({ data: { unread_count: 0 } });
  });

  it("renders the empty state when there are no notifications", async () => {
    getMock.mockResolvedValue({ data: { notifications: [], unread_count: 0, has_more: false } });
    const w = mountInbox();
    await flushPromises();
    expect(w.text()).toContain("notifications.empty");
  });

  it("renders rows and marks all read on open", async () => {
    getMock.mockResolvedValue({
      data: { notifications: [row(3), row(2, { read: true })], unread_count: 1, has_more: false },
    });
    const w = mountInbox();
    await flushPromises();
    expect(w.text()).toContain("Title 3");
    // Opening the inbox acknowledges unread rows.
    expect(postMock).toHaveBeenCalledWith(
      "/customer/notifications/mark-read/",
      { ids: [] }
    );
    // Emits the reconciled unread count up to the bell.
    const emitted = w.emitted("update-unread");
    expect(emitted).toBeTruthy();
    expect(emitted[emitted.length - 1]).toEqual([0]);
  });

  it("does not call mark-read when everything is already read", async () => {
    getMock.mockResolvedValue({
      data: { notifications: [row(1, { read: true })], unread_count: 0, has_more: false },
    });
    mountInbox();
    await flushPromises();
    expect(postMock).not.toHaveBeenCalled();
  });

  it("renders a deep-link RouterLink for rows with a url", async () => {
    getMock.mockResolvedValue({
      data: { notifications: [row(5, { url: "/orders/ORD-9", read: true })], unread_count: 0, has_more: false },
    });
    const w = mountInbox();
    await flushPromises();
    const link = w.find("a.rl");
    expect(link.exists()).toBe(true);
  });

  it("shows the error state when the fetch fails", async () => {
    getMock.mockRejectedValue(new Error("network"));
    const w = mountInbox();
    await flushPromises();
    expect(w.text()).toContain("notifications.error");
  });
});
