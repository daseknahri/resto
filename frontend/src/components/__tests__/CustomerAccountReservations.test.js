/**
 * Unit tests for CustomerAccountReservations — the reservations tab of
 * CustomerAccount.vue, extracted into a standalone presentational component
 * (RISK FE-2). Fetch/state stays in the parent; this component only renders
 * whatever it's given and asks the parent to retry via the `retry` emit.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
    currentLocale: { value: "en" },
  }),
}));

import CustomerAccountReservations from "../CustomerAccountReservations.vue";

const RouterLinkStub = {
  name: "RouterLink",
  props: ["to"],
  template: '<a class="rl"><slot /></a>',
};

const mountComp = (props = {}) =>
  mount(CustomerAccountReservations, {
    props: { reservations: [], loading: false, error: false, ...props },
    global: { stubs: { RouterLink: RouterLinkStub } },
  });

const reservation = (overrides = {}) => ({
  id: 1,
  restaurant_name: "Le Bistro",
  restaurant_slug: "le-bistro",
  booked_for: "2026-08-01T19:00:00Z",
  party_size: 2,
  status: "new",
  cancel_token: "tok-1",
  notes: "",
  ...overrides,
});

describe("CustomerAccountReservations", () => {
  it("renders the loading skeleton", () => {
    const w = mountComp({ loading: true });
    expect(w.findAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders the empty state when there are no reservations", () => {
    const w = mountComp();
    expect(w.text()).toContain("customerAccount.reservationsEmpty");
    expect(w.text()).toContain("customerAccount.reservationsEmptyHint");
  });

  it("renders the error state and emits retry when the retry button is clicked", async () => {
    const w = mountComp({ error: true });
    expect(w.text()).toContain("customerAccount.fetchError");
    await w.find("button").trigger("click");
    expect(w.emitted("retry")).toBeTruthy();
  });

  it("renders the reservation list with restaurant name, status and a manage link", () => {
    const w = mountComp({ reservations: [reservation()] });
    expect(w.text()).toContain("Le Bistro");
    expect(w.text()).toContain("customerAccount.reservationStatusNew");
    expect(w.find("a.rl").exists()).toBe(true);
  });

  it("shows the reservation count badge", () => {
    const w = mountComp({
      reservations: [reservation({ id: 1 }), reservation({ id: 2 })],
    });
    expect(w.text()).toContain("2");
  });

  it("does not render a manage link when there is no cancel token", () => {
    const w = mountComp({ reservations: [reservation({ cancel_token: null })] });
    expect(w.find("a.rl").exists()).toBe(false);
  });
});
