/**
 * Unit tests for OwnerReservationsCalendarDetail — the "selected calendar
 * reservation detail" quick panel of OwnerReservations.vue, extracted into a
 * standalone presentational component (RISK FE-2). The `selectedCalendarRes`
 * state and the calendar view gate stay in the parent; this component only
 * renders the reservation it's given and asks the parent to close via the
 * `close` emit. It makes no API calls and mutates nothing.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import OwnerReservationsCalendarDetail from "../OwnerReservationsCalendarDetail.vue";

const formatDateTime = (iso) => (iso ? `fmt:${iso}` : "");

const reservation = (overrides = {}) => ({
  id: 7,
  name: "Nadia Guest",
  phone: "0600000000",
  email: "nadia@example.com",
  booked_for: "2026-08-01T19:00:00Z",
  party_size: 4,
  notes: "Anniversary — window table",
  ...overrides,
});

const mountComp = (props = {}) =>
  mount(OwnerReservationsCalendarDetail, {
    props: {
      reservation: reservation(),
      formatDateTime,
      ...props,
    },
  });

describe("OwnerReservationsCalendarDetail", () => {
  it("renders the reservation name, phone and email", () => {
    const w = mountComp();
    expect(w.text()).toContain("Nadia Guest");
    expect(w.text()).toContain("0600000000");
    expect(w.text()).toContain("nadia@example.com");
  });

  it("renders the booked-for date via the parent formatDateTime plus party size", () => {
    const w = mountComp();
    expect(w.text()).toContain("ownerReservations.bookedFor");
    expect(w.text()).toContain("fmt:2026-08-01T19:00:00Z");
    expect(w.text()).toContain("ownerReservations.guests");
    expect(w.text()).toContain("4");
  });

  it("hides the booked-for line when the reservation has no booked_for", () => {
    const w = mountComp({ reservation: reservation({ booked_for: null }) });
    expect(w.text()).not.toContain("ownerReservations.bookedFor");
  });

  it("hides the party-size suffix when the reservation has no party_size", () => {
    const w = mountComp({ reservation: reservation({ party_size: null }) });
    expect(w.text()).toContain("ownerReservations.bookedFor");
    expect(w.text()).not.toContain("ownerReservations.guests");
  });

  it("renders the notes block when notes are present", () => {
    const w = mountComp();
    expect(w.text()).toContain("Anniversary — window table");
  });

  it("hides the notes block when there are no notes", () => {
    const w = mountComp({ reservation: reservation({ notes: "" }) });
    expect(w.text()).not.toContain("Anniversary");
  });

  it("emits close when the close button is clicked", async () => {
    const w = mountComp();
    await w.find("button").trigger("click");
    expect(w.emitted("close")).toBeTruthy();
    expect(w.emitted("close")).toHaveLength(1);
  });
});
