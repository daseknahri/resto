/**
 * Unit tests for AdminConsoleLiveOrdersModal — the read-only "live orders
 * support" modal of AdminConsole.vue, extracted into a standalone presentational
 * component (RISK FE-2). All data-fetching (the /admin/tenants/{id}/live-orders/
 * call), the open/close state and the orders/count refs stay owned by the
 * parent; this component only renders the mobile-card + desktop-table views it's
 * given and asks the parent to close/refresh via emits (`close`, `refresh`). The
 * dialog's focus trap moved in with the markup, so it is covered here too.
 */
import { describe, it, expect, vi } from "vitest";
import { nextTick } from "vue";
import { mount, flushPromises } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import AdminConsoleLiveOrdersModal from "../AdminConsoleLiveOrdersModal.vue";

const order = (overrides = {}) => ({
  order_number: "1042",
  status: "preparing",
  order_type: "delivery",
  total: "125.00",
  created_at: "2026-07-19T10:00:00Z",
  customer_phone: "+212600000000",
  ...overrides,
});

// Stub teleport so the modal renders inline (queryable in the wrapper), same
// pattern used by AdminConsoleDryRunImportModal.test.js for teleport modals.
const mountModal = (props = {}) =>
  mount(AdminConsoleLiveOrdersModal, {
    props: {
      open: true,
      tenant: { id: 7, name: "Acme Diner" },
      loading: false,
      error: null,
      orders: [order()],
      count: 1,
      ...props,
    },
    global: { stubs: { teleport: true } },
  });

describe("AdminConsoleLiveOrdersModal", () => {
  it("renders nothing when closed", () => {
    const w = mountModal({ open: false });
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("renders the dialog with the tenant name and header text when open", () => {
    const w = mountModal();
    expect(w.find('[role="dialog"]').exists()).toBe(true);
    expect(w.text()).toContain("Acme Diner");
    expect(w.text()).toContain("adminConsole.liveOrders.title");
    expect(w.text()).toContain("adminConsole.liveOrders.subtitle");
    expect(w.text()).toContain("adminConsole.liveOrders.readOnlyBadge");
  });

  it("shows the skeleton (and no orders) while loading", () => {
    const w = mountModal({ loading: true });
    expect(w.findAll(".ui-skeleton").length).toBeGreaterThan(0);
    expect(w.find("table").exists()).toBe(false);
    expect(w.find(".ui-empty-state").exists()).toBe(false);
  });

  it("shows an alert with the error message when the fetch failed", () => {
    const w = mountModal({ error: "Boom", orders: [], count: 0 });
    const alert = w.find('[role="alert"]');
    expect(alert.exists()).toBe(true);
    expect(alert.text()).toContain("Boom");
    expect(w.find("table").exists()).toBe(false);
  });

  it("shows the empty state when there are no orders", () => {
    const w = mountModal({ orders: [], count: 0 });
    expect(w.find(".ui-empty-state").exists()).toBe(true);
    expect(w.text()).toContain("adminConsole.liveOrders.empty");
    expect(w.text()).toContain("adminConsole.liveOrders.emptyHint");
    expect(w.find("table").exists()).toBe(false);
  });

  it("renders the active count line with the count param", () => {
    const w = mountModal({ count: 4 });
    expect(w.text()).toContain('adminConsole.liveOrders.activeCount:{"count":4}');
  });

  it("renders the mobile-card branch for each order", () => {
    const w = mountModal({ orders: [order({ order_number: "A1" }), order({ order_number: "B2" })] });
    const cards = w.findAll(".ui-admin-card");
    expect(cards.length).toBe(2);
    expect(cards[0].text()).toContain("#A1");
    expect(cards[1].text()).toContain("#B2");
  });

  it("renders the desktop-table branch with a row per order", () => {
    const w = mountModal({ orders: [order({ order_number: "A1" }), order({ order_number: "B2" })] });
    const table = w.find("table");
    expect(table.exists()).toBe(true);
    // header + 2 data rows
    expect(table.findAll("tbody tr").length).toBe(2);
    expect(table.text()).toContain("#A1");
    expect(table.text()).toContain("#B2");
  });

  it("maps the order status to a pill class (status helper moved into the child)", () => {
    const w = mountModal({ orders: [order({ status: "ready" })] });
    expect(w.find(".ui-status-pill").classes()).toContain("bg-emerald-500/20");
  });

  it("renders a dash for a missing/invalid created_at (age helper moved into the child)", () => {
    const w = mountModal({ orders: [order({ created_at: null })] });
    // The age line falls back to "-"; assert the mobile card shows the age label.
    expect(w.text()).toContain("adminConsole.liveOrders.age");
  });

  it("emits refresh from the refresh button", async () => {
    const w = mountModal();
    const refreshBtn = w.findAll("button").find((b) => b.text() === "common.refresh");
    await refreshBtn.trigger("click");
    expect(w.emitted("refresh")).toBeTruthy();
  });

  it("disables the refresh button while loading", () => {
    const w = mountModal({ loading: true });
    const refreshBtn = w.findAll("button").find((b) => b.text() === "common.refresh");
    expect(refreshBtn.attributes("disabled")).not.toBeUndefined();
  });

  it("emits close from the header and footer close buttons", async () => {
    const w = mountModal();
    const closeButtons = w.findAll("button").filter((b) => b.text() === "adminConsole.liveOrders.close");
    expect(closeButtons.length).toBe(2);
    await closeButtons[0].trigger("click");
    await closeButtons[1].trigger("click");
    expect(w.emitted("close")).toBeTruthy();
    expect(w.emitted("close").length).toBe(2);
  });

  it("emits close when the backdrop is clicked", async () => {
    const w = mountModal();
    const backdrop = w.findAll("div").find((d) => d.classes().includes("bg-slate-950/80"));
    expect(backdrop).toBeTruthy();
    await backdrop.trigger("click");
    expect(w.emitted("close")).toBeTruthy();
  });

  it("emits close on Escape", async () => {
    const w = mountModal();
    const backdrop = w.findAll("div").find((d) => d.classes().includes("bg-slate-950/80"));
    await backdrop.trigger("keydown.esc");
    expect(w.emitted("close")).toBeTruthy();
  });

  it("registers a keydown focus trap when it opens and removes it when it closes", async () => {
    const addSpy = vi.spyOn(document, "addEventListener");
    const removeSpy = vi.spyOn(document, "removeEventListener");

    // Start closed so the (non-immediate) watcher fires on the false -> true transition.
    const w = mountModal({ open: false });
    expect(addSpy).not.toHaveBeenCalledWith("keydown", expect.any(Function));

    await w.setProps({ open: true });
    await flushPromises();
    await nextTick();
    expect(addSpy).toHaveBeenCalledWith("keydown", expect.any(Function));

    await w.setProps({ open: false });
    await nextTick();
    expect(removeSpy).toHaveBeenCalledWith("keydown", expect.any(Function));

    addSpy.mockRestore();
    removeSpy.mockRestore();
  });

  it("removes the keydown focus trap on unmount", () => {
    const removeSpy = vi.spyOn(document, "removeEventListener");
    const w = mountModal();
    w.unmount();
    expect(removeSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
    removeSpy.mockRestore();
  });
});
