/**
 * Unit tests for WaiterOfflineIndicator — the offline / queue-sync banner
 * extracted from WaiterPage.vue (RISK FE-2). Display only: it shows an "offline"
 * banner when disconnected, a "syncing N" banner when there are queued actions,
 * and nothing when online with an empty queue.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import WaiterOfflineIndicator from "../WaiterOfflineIndicator.vue";

const mountIt = (props = {}) =>
  mount(WaiterOfflineIndicator, {
    props: { online: true, queueLength: 0, ...props },
    global: { stubs: { transition: false } },
  });

describe("WaiterOfflineIndicator", () => {
  it("renders nothing when online with an empty queue", () => {
    expect(mountIt({ online: true, queueLength: 0 }).find('[role="status"]').exists()).toBe(false);
  });

  it("shows the offline banner when offline", () => {
    const w = mountIt({ online: false, queueLength: 0 });
    expect(w.find('[role="status"]').exists()).toBe(true);
    expect(w.text()).toContain("waiterPage.offline");
    expect(w.text()).not.toContain("waiterPage.syncingQueue");
  });

  it("shows the syncing-queue banner with the count when online but queued", () => {
    const w = mountIt({ online: true, queueLength: 3 });
    expect(w.text()).toContain('waiterPage.syncingQueue:{"n":3}');
    expect(w.text()).not.toContain("waiterPage.offline");
  });

  it("prefers the offline message when both offline and queued", () => {
    const w = mountIt({ online: false, queueLength: 2 });
    expect(w.text()).toContain("waiterPage.offline");
    expect(w.text()).not.toContain("waiterPage.syncingQueue");
  });
});
