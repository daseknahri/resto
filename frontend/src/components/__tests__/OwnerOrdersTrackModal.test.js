/**
 * Unit tests for OwnerOrdersTrackModal — the live delivery-tracking modal
 * extracted from OwnerOrders.vue (RISK FE-2). Display only: it renders the order
 * number, the polled delivery (via DeliveryTracker), an error, or a loading
 * skeleton, and asks the parent to close via the close emit. The trackModal state
 * and the 10s poll stay in the parent.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) => k,
  }),
}));

import OwnerOrdersTrackModal from "../OwnerOrdersTrackModal.vue";

const mountModal = (props = {}) =>
  mount(OwnerOrdersTrackModal, {
    props: { open: true, orderNumber: "1042", delivery: null, error: "", ...props },
    global: { stubs: { DeliveryTracker: true } },
  });

describe("OwnerOrdersTrackModal", () => {
  it("renders nothing when open is false", () => {
    const w = mountModal({ open: false });
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("renders the heading with the order number when open", () => {
    const w = mountModal();
    expect(w.find('[role="dialog"]').exists()).toBe(true);
    expect(w.text()).toContain("ownerOrders.trackTitle");
    expect(w.text()).toContain("#1042");
  });

  it("shows the error message when an error is present (and no tracker/skeleton)", () => {
    const w = mountModal({ error: "ownerOrders.trackUnavailable", delivery: { id: 1 } });
    expect(w.text()).toContain("ownerOrders.trackUnavailable");
    expect(w.findComponent({ name: "DeliveryTracker" }).exists()).toBe(false);
  });

  it("renders DeliveryTracker with the delivery when present and no error", () => {
    const w = mountModal({ delivery: { id: 7, status: "en_route" }, error: "" });
    expect(w.findComponent({ name: "DeliveryTracker" }).exists()).toBe(true);
  });

  it("shows the loading skeleton when there is no delivery and no error", () => {
    const w = mountModal({ delivery: null, error: "" });
    expect(w.find(".ui-skeleton").exists()).toBe(true);
    expect(w.find('[aria-busy="true"]').exists()).toBe(true);
  });

  it("emits close from the close button, the backdrop and Escape", async () => {
    const w = mountModal();
    const closeBtn = w.findAll("button").find((b) => b.text() === "common.close");
    await closeBtn.trigger("click");
    const backdrop = w.find(".fixed.inset-0");
    await backdrop.trigger("click");
    await backdrop.trigger("keydown.esc");
    expect(w.emitted("close").length).toBe(3);
  });
});
