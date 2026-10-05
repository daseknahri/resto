import { describe, it, expect } from "vitest";
import {
  CUSTOMER_ACTIVE_STATUSES,
  CUSTOMER_STATUS_I18N,
  customerStatusKey,
  formatScheduledDue,
} from "../orderStatusMeta";

// Customer-facing status helpers shared by CustomerAccount.vue and its Orders tab
// (CustomerAccountOrders.vue). Each page used to keep a private copy of the label map;
// both lacked `scheduled`, so a prepaid advance order was badged "Pending" and got no
// live-order banner (M6).
describe("customer order-status helpers", () => {
  it("labels a scheduled order 'Scheduled', not the 'Pending' fallback", () => {
    expect(customerStatusKey("scheduled")).toBe("orderStatus.statusScheduled");
  });

  it("covers every order status the backend can send", () => {
    for (const s of ["scheduled", "pending", "confirmed", "preparing", "ready", "out_for_delivery", "completed", "cancelled"]) {
      expect(CUSTOMER_STATUS_I18N[s]).toBeTruthy();
    }
  });

  it("still falls back to 'Pending' for an unknown status", () => {
    expect(customerStatusKey("mystery")).toBe("orderStatus.statusPending");
  });

  it("treats scheduled as live, and terminal statuses as not", () => {
    expect(CUSTOMER_ACTIVE_STATUSES.has("scheduled")).toBe(true);
    expect(CUSTOMER_ACTIVE_STATUSES.has("out_for_delivery")).toBe(true);
    expect(CUSTOMER_ACTIVE_STATUSES.has("completed")).toBe(false);
    expect(CUSTOMER_ACTIVE_STATUSES.has("cancelled")).toBe(false);
  });

  it("formats a due time with weekday, date and time in the given locale", () => {
    const iso = "2026-07-02T19:30:00Z";
    const expected = new Intl.DateTimeFormat("fr", {
      weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    }).format(new Date(iso));
    expect(formatScheduledDue("fr", iso)).toBe(expected);
  });

  it("returns '' for a missing or unparseable due time", () => {
    expect(formatScheduledDue("en", null)).toBe("");
    expect(formatScheduledDue("en", "not-a-date")).toBe("");
  });
});
