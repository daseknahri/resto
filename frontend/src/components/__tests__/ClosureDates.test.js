/**
 * Unit tests for ClosureDates — the owner closure-date manager.
 *
 * Regression guard for the double-tap DELETE bug: removeDate had no in-flight
 * guard, so a rapid double-tap fired two DELETE /owner/closure-dates/:id/ calls;
 * the second raced against the optimistic list removal, 404'd, and surfaced a
 * spurious closureDates.removeFailed toast after a delete that actually succeeded.
 * The fix adds a `deletingId` guard (+ a :disabled binding on the button).
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Deterministic i18n. currentLocale is consumed by formatDate → must be a ref-like.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) => k,
    currentLocale: { value: "en" },
  }),
}));

const getMock = vi.fn();
const deleteMock = vi.fn();
vi.mock("../../lib/api", () => ({
  default: {
    get: (...a) => getMock(...a),
    delete: (...a) => deleteMock(...a),
  },
}));

import ClosureDates from "../ClosureDates.vue";

beforeEach(() => {
  setActivePinia(createPinia());
  getMock.mockReset();
  deleteMock.mockReset();
});

describe("ClosureDates — delete in-flight guard", () => {
  it("a rapid double-tap on remove fires only one DELETE", async () => {
    getMock.mockResolvedValue({ data: [{ id: 7, date: "2099-01-01", label: "NYE" }] });
    // Keep the DELETE in-flight so the second tap lands while the first is pending.
    let resolveDelete;
    deleteMock.mockImplementation(() => new Promise((res) => { resolveDelete = res; }));

    const w = mount(ClosureDates);
    await flushPromises(); // let onMounted fetchDates resolve → the row + remove button render

    const btn = w.get('button[aria-label^="common.remove"]');
    // Two synchronous taps before the first DELETE settles (no await between them).
    btn.trigger("click");
    btn.trigger("click");
    await flushPromises();

    expect(deleteMock).toHaveBeenCalledTimes(1);

    resolveDelete({ data: {} }); // settle the in-flight delete so nothing dangles
    await flushPromises();
  });

  it("disables the remove button while its DELETE is in flight", async () => {
    getMock.mockResolvedValue({ data: [{ id: 9, date: "2099-02-02", label: "" }] });
    let resolveDelete;
    deleteMock.mockImplementation(() => new Promise((res) => { resolveDelete = res; }));

    const w = mount(ClosureDates);
    await flushPromises();

    const btn = w.get('button[aria-label^="common.remove"]');
    await btn.trigger("click"); // start the delete; button should reflect the busy state
    expect(btn.attributes("disabled")).toBeDefined();

    resolveDelete({ data: {} });
    await flushPromises();
  });
});
