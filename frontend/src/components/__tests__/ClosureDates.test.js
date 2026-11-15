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
// ── Run 8 G4b-K2 (A3-37) — appended 2026-11-15 ────────────────────────────
// The 2 base double-tap tests above are untouched; everything below this line
// is new. 5 tests: mount smoke (empty list) (1), load-failure inline + retry
// (1), delete confirm cancel / proceed (2), add failure translated (1).
//
// Mock note — the hoisted useConfirmModal mock below applies file-wide: the
// base tests never mocked it, and the real composable's confirm() returns a
// promise that only settles via the modal UI, so without this mock every base
// remove-click test would hang at the new confirm step. The mock resolves true
// by default, preserving both base tests; the cancel path flips it per test.
const closureConfirmMock = vi.hoisted(() => vi.fn(() => Promise.resolve(true)));
vi.mock("../../composables/useConfirmModal", () => ({
  useConfirmModal: () => ({ confirm: closureConfirmMock }),
}));

import api from "../../lib/api";

describe("ClosureDates — G4b-K2 A3-37 (load error, delete confirm, add error)", () => {
  beforeEach(() => {
    // The top-level beforeEach resets getMock/deleteMock but not the hoisted
    // confirm mock — without this, confirm calls from the base double-tap
    // tests accumulate and the per-test toHaveBeenCalledTimes(1) fails.
    closureConfirmMock.mockReset();
    api.post = vi.fn().mockResolvedValue({ data: { id: 11, date: "2099-03-03", label: "" } });
  });

  const removeButton = (w) => w.get('button[aria-label^="common.remove"]');
  const addButton = (w) =>
    w.findAll("button").find((b) => b.text().trim() === "closureDates.add");

  it("mounts with an empty list (empty state, no crash)", async () => {
    getMock.mockResolvedValue({ data: [] });
    const w = mount(ClosureDates);
    await flushPromises();
    expect(w.exists()).toBe(true);
    expect(w.text()).toContain("closureDates.emptyTitle");
  });

  it("load failure shows an inline message with Retry instead of a silently empty list", async () => {
    getMock.mockRejectedValueOnce(new Error("offline"));
    const w = mount(ClosureDates);
    await flushPromises();

    expect(w.text()).toContain("closureDates.loadFailed");
    const retryBtn = w.findAll("button").find((b) => b.text().includes("common.retry"));
    expect(retryBtn.exists()).toBe(true);

    getMock.mockResolvedValue({ data: [{ id: 7, date: "2099-01-01", label: "NYE" }] });
    await retryBtn.trigger("click");
    await flushPromises();
    expect(w.text()).toContain("NYE");
    expect(w.text()).not.toContain("closureDates.loadFailed");
  });

  it("asks for confirmation before deleting, naming the date", async () => {
    getMock.mockResolvedValue({ data: [{ id: 7, date: "2099-01-01", label: "NYE" }] });
    const w = mount(ClosureDates);
    await flushPromises();

    await removeButton(w).trigger("click");
    await flushPromises();

    expect(closureConfirmMock).toHaveBeenCalledTimes(1);
    expect(closureConfirmMock).toHaveBeenCalledWith(
      expect.objectContaining({ title: "closureDates.removeConfirmTitle" }),
    );
    expect(deleteMock).toHaveBeenCalledTimes(1);
    expect(deleteMock).toHaveBeenCalledWith("/owner/closure-dates/7/");
  });

  it("does not DELETE when the delete confirm is declined", async () => {
    closureConfirmMock.mockResolvedValueOnce(false);
    getMock.mockResolvedValue({ data: [{ id: 7, date: "2099-01-01", label: "NYE" }] });
    const w = mount(ClosureDates);
    await flushPromises();

    await removeButton(w).trigger("click");
    await flushPromises();

    expect(deleteMock).not.toHaveBeenCalled();
    expect(w.text()).toContain("NYE");
  });

  it("add failure shows the translated generic message, never the raw backend detail", async () => {
    getMock.mockResolvedValue({ data: [] });
    api.post.mockRejectedValueOnce({ response: { data: { detail: "Date already closed" } } });
    const w = mount(ClosureDates);
    await flushPromises();

    // setValue on the input (awaits a tick) so the :disabled-bound Add button enables.
    await w.find("#closure-date").setValue("2099-03-03");
    await addButton(w).trigger("click");
    await flushPromises();

    expect(w.text()).toContain("closureDates.addFailed");
    expect(w.text()).not.toContain("Date already closed");
  });
});
