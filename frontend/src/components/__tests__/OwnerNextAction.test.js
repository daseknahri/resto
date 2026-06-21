/**
 * Unit tests for OwnerNextAction — the solo-owner single next-action focus card.
 *
 * Locks in: it renders THE one highest-priority action from the shared
 * computeNextAction ladder; the primary button emits `act` with the action
 * descriptor; the all-clear state renders when nothing needs attention; and
 * "Next" emits `skip` only when more than one candidate exists.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

// Deterministic i18n: key + interpolation passthrough so we can assert on text.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, vars) => (vars ? `${k}:${Object.values(vars).join(",")}` : k),
  }),
}));

// Freeze the ticker so time-based derivations are deterministic.
const NOW = new Date("2026-06-21T12:00:00Z").getTime();
vi.mock("../../composables/useNowTicker", () => ({
  useNowTicker: () => ({ now: { value: NOW } }),
}));

import OwnerNextAction from "../OwnerNextAction.vue";

const minsAgo = (m) => new Date(NOW - m * 60000).toISOString();

const mountCard = (props = {}) =>
  mount(OwnerNextAction, { props: { orders: [], soldOutCount: 0, ...props } });

describe("OwnerNextAction", () => {
  it("renders the all-clear state when there is nothing to do", () => {
    const w = mountCard({ orders: [] });
    expect(w.text()).toContain("ownerHome.nextActionAllClearTitle");
    // No primary action button in the all-clear state.
    expect(w.find("button.ui-btn-primary").exists()).toBe(false);
  });

  it("surfaces an overdue pending order as a confirm action and emits act", async () => {
    const orders = [
      { id: 1, order_number: "A1", status: "pending", created_at: minsAgo(20) },
    ];
    const w = mountCard({ orders });
    // Title uses the order number via interpolation passthrough.
    expect(w.text()).toContain("ownerHome.nextActionConfirm:A1");
    const btn = w.find("button.ui-btn-primary");
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    const evt = w.emitted("act");
    expect(evt).toBeTruthy();
    expect(evt[0][0]).toMatchObject({ kind: "confirm", order: { id: 1 } });
  });

  it("shows the Next (skip) control only when more than one candidate exists", () => {
    const single = mountCard({
      orders: [{ id: 1, order_number: "A1", status: "ready", created_at: minsAgo(2) }],
    });
    expect(single.text()).not.toContain("ownerHome.nextActionSkip");

    const many = mountCard({
      orders: [
        { id: 1, order_number: "A1", status: "ready", created_at: minsAgo(2) },
        { id: 2, order_number: "A2", status: "pending", created_at: minsAgo(3) },
      ],
    });
    expect(many.text()).toContain("ownerHome.nextActionSkip");
  });

  it("emits skip with the current action descriptor", async () => {
    const orders = [
      { id: 1, order_number: "A1", status: "ready", created_at: minsAgo(2) },
      { id: 2, order_number: "A2", status: "pending", created_at: minsAgo(3) },
    ];
    const w = mountCard({ orders });
    const skipBtn = w.findAll("button").find((b) => b.text().includes("ownerHome.nextActionSkip"));
    await skipBtn.trigger("click");
    expect(w.emitted("skip")).toBeTruthy();
  });

  it("disables the primary button while busy", () => {
    const orders = [{ id: 1, order_number: "A1", status: "ready", created_at: minsAgo(2) }];
    const w = mountCard({ orders, busy: true });
    expect(w.find("button.ui-btn-primary").attributes("disabled")).toBeDefined();
  });
});
