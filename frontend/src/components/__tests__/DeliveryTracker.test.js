/**
 * DeliveryTracker.vue — the no-driver body must agree with the status pill.
 *
 * L2: a job that ENDED before any driver took it (order cancelled → job cancelled, or a
 * failed job with no driver) used to keep the "Finding a driver nearby…" line + amber
 * live dot under a "Cancelled" / "Delivery failed" pill — a direct contradiction. Only a
 * job that is actually `searching` may say it's searching.
 *
 * No driver position in any case below, so the lazy Leaflet map never initialises.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k) }),
}));
vi.mock("../../stores/toast", () => ({ useToastStore: () => ({ show: vi.fn() }) }));
vi.mock("../../lib/api", () => ({ default: { post: vi.fn(() => Promise.resolve({ data: {} })) } }));
vi.mock("../../lib/mapTiles", () => ({ addTileLayer: vi.fn() }));

import DeliveryTracker from "../DeliveryTracker.vue";

const mountTracker = (delivery) =>
  mount(DeliveryTracker, {
    props: { delivery },
    global: { stubs: { AppIcon: { template: "<i />" } } },
  });

const job = (overrides = {}) => ({
  order_number: "D1",
  status: "searching",
  driver: null,
  business_type: "restaurant",
  pickup_address: "",
  delivery_address: "",
  ...overrides,
});

describe("DeliveryTracker — no-driver body matches the job state (L2)", () => {
  it("a cancelled job with no driver says so — no 'Finding a driver' line or live dot", () => {
    const wrapper = mountTracker(job({ status: "cancelled" }));
    const text = wrapper.text();
    expect(text).toContain("deliveryTracker.status_cancelled");
    expect(text).toContain("deliveryTracker.endedCancelled");
    expect(text).not.toContain("deliveryTracker.searching");
    expect(wrapper.find(".ui-live-dot").exists()).toBe(false);
    wrapper.unmount();
  });

  it("a failed job with no driver reads as ended, not searching", () => {
    const wrapper = mountTracker(job({ status: "failed" }));
    const text = wrapper.text();
    expect(text).toContain("deliveryTracker.endedFailed");
    expect(text).not.toContain("deliveryTracker.searching");
    expect(wrapper.find(".ui-live-dot").exists()).toBe(false);
    wrapper.unmount();
  });

  it("a searching job still shows the live 'Finding a driver' line", () => {
    const wrapper = mountTracker(job({ status: "searching" }));
    expect(wrapper.text()).toContain("deliveryTracker.searching");
    expect(wrapper.find("[data-test='ended-without-driver']").exists()).toBe(false);
    expect(wrapper.find(".ui-live-dot").exists()).toBe(true);
    wrapper.unmount();
  });

  it("an assigned job shows the driver card, not the searching line", () => {
    const wrapper = mountTracker(job({ status: "assigned", driver: { name: "Ali", phone: "0600" } }));
    const text = wrapper.text();
    expect(text).toContain("Ali");
    expect(text).not.toContain("deliveryTracker.searching");
    expect(text).not.toContain("deliveryTracker.endedCancelled");
    wrapper.unmount();
  });
});
