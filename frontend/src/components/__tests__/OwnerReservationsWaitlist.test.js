/**
 * Unit tests for OwnerReservationsWaitlist — the waitlist section of
 * OwnerReservations.vue, extracted into a standalone presentational
 * component (RISK FE-2). Fetch/date-filter state and the fetchWaitlist API
 * call stay in the parent; this component only renders whatever the parent
 * has loaded and asks the parent to update the date / re-fetch via the
 * `update:date` / `refresh` emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import OwnerReservationsWaitlist from "../OwnerReservationsWaitlist.vue";

const formatDate = (iso) => (iso ? `fmt:${iso}` : "-");

const entry = (overrides = {}) => ({
  id: 1,
  name: "Sam Guest",
  phone: "0600000000",
  email: "sam@example.com",
  booked_for: "2026-08-01T19:00:00Z",
  party_size: 4,
  status: "waiting",
  notes: "Window seat please",
  ...overrides,
});

const mountComp = (props = {}) =>
  mount(OwnerReservationsWaitlist, {
    props: {
      date: "",
      loading: false,
      error: false,
      entries: [],
      formatDate,
      ...props,
    },
  });

describe("OwnerReservationsWaitlist", () => {
  it("renders the loading skeleton", () => {
    const w = mountComp({ loading: true });
    expect(w.findAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders the error state and emits refresh when the retry button is clicked", async () => {
    const w = mountComp({ error: true });
    expect(w.text()).toContain("ownerReservations.waitlistLoadError");
    await w.find("button").trigger("click");
    expect(w.emitted("refresh")).toBeTruthy();
  });

  it("shows the all-dates empty copy when no date filter is set", () => {
    const w = mountComp({ date: "" });
    expect(w.text()).toContain("ownerReservations.waitlistEmptyAll");
  });

  it("shows the date-specific empty copy when a date filter is set", () => {
    const w = mountComp({ date: "2026-08-01" });
    expect(w.text()).toContain("ownerReservations.waitlistEmpty");
    expect(w.text()).not.toContain("ownerReservations.waitlistEmptyAll");
  });

  it("renders entries using the parent-supplied formatDate and local status label/class", () => {
    const w = mountComp({ entries: [entry()] });
    expect(w.text()).toContain("Sam Guest");
    expect(w.text()).toContain("fmt:2026-08-01T19:00:00Z");
    expect(w.text()).toContain("ownerReservations.waitlistStatusWaiting");
    expect(w.find(".ui-table-wrap").exists()).toBe(true);
  });

  it("emits update:date on input and refresh only on change (matching the original v-model + @change split)", async () => {
    const w = mountComp();
    const input = w.find('input[type="date"]');

    // Vue Test Utils' setValue() always fires both input+change (for
    // v-model.lazy support), so trigger 'input' directly to isolate the
    // per-keystroke behavior from the on-commit 'change' behavior.
    input.element.value = "2026-08-05";
    await input.trigger("input");
    expect(w.emitted("update:date")[0]).toEqual(["2026-08-05"]);
    expect(w.emitted("refresh")).toBeFalsy();

    await input.trigger("change");
    expect(w.emitted("refresh")).toBeTruthy();
  });
});
