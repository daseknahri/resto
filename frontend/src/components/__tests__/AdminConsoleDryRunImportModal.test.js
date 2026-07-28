/**
 * Unit tests for AdminConsoleDryRunImportModal — the dry-run import review modal
 * of AdminConsole.vue, extracted into a standalone presentational component
 * (RISK FE-2). The import dry-run/apply flow (building the review object, the
 * cancel toast, the settings-import apply API call) stays owned by the parent;
 * this component only renders the summary it's given and asks the parent to
 * cancel/apply via emits (`cancel`, `apply`). The dialog's focus trap moved in
 * with the markup, so it is covered here too.
 */
import { describe, it, expect, vi } from "vitest";
import { nextTick } from "vue";
import { mount, flushPromises } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import AdminConsoleDryRunImportModal from "../AdminConsoleDryRunImportModal.vue";

const review = (summaryOverrides = {}) => ({
  tenant: { id: 7, slug: "acme" },
  replaceBody: { mode: "replace", payload: {} },
  summary: {
    categories: 3,
    dishes: 12,
    options: 5,
    table_links: 2,
    profile_updated: true,
    ...summaryOverrides,
  },
});

// Stub teleport so the modal renders inline (queryable in the wrapper), same
// pattern used by OwnerOrdersCashierModal.test.js for teleport-based modals.
const mountModal = (props = {}) =>
  mount(AdminConsoleDryRunImportModal, {
    props: {
      review: review(),
      applying: false,
      ...props,
    },
    global: { stubs: { teleport: true } },
  });

describe("AdminConsoleDryRunImportModal", () => {
  it("renders nothing when review is null", () => {
    const w = mountModal({ review: null });
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("renders the dialog with the dry-run summary counts when open", () => {
    const w = mountModal();
    expect(w.find('[role="dialog"]').exists()).toBe(true);
    expect(w.text()).toContain("adminConsole.dryRunSuccessful");
    expect(w.text()).toContain("adminConsole.applyImportNow");
    // categories / dishes / options / table_links values
    expect(w.text()).toContain("3");
    expect(w.text()).toContain("12");
    expect(w.text()).toContain("5");
    expect(w.text()).toContain("2");
  });

  it("falls back to 0 for missing summary counts", () => {
    const w = mountModal({ review: review({ categories: undefined, dishes: 0 }) });
    // "0" appears for the missing/zero counts
    expect(w.text()).toContain("0");
  });

  it("shows the 'yes' profile label when profile_updated is true", () => {
    const w = mountModal({ review: review({ profile_updated: true }) });
    expect(w.text()).toContain("adminConsole.yes");
    expect(w.text()).not.toContain("adminConsole.no");
  });

  it("shows the 'no' profile label when profile_updated is false", () => {
    const w = mountModal({ review: review({ profile_updated: false }) });
    expect(w.text()).toContain("adminConsole.no");
    expect(w.text()).not.toContain("adminConsole.yes");
  });

  it("emits cancel from the cancel button", async () => {
    const w = mountModal();
    const cancelBtn = w.findAll("button").find((b) => b.text() === "common.cancel");
    await cancelBtn.trigger("click");
    expect(w.emitted("cancel")).toBeTruthy();
  });

  it("emits cancel when the backdrop is clicked", async () => {
    const w = mountModal();
    const backdrop = w.findAll("div").find((d) => d.classes().includes("bg-black/70"));
    expect(backdrop).toBeTruthy();
    await backdrop.trigger("click");
    expect(w.emitted("cancel")).toBeTruthy();
  });

  it("emits cancel on Escape", async () => {
    const w = mountModal();
    const backdrop = w.findAll("div").find((d) => d.classes().includes("bg-black/70"));
    await backdrop.trigger("keydown.esc");
    expect(w.emitted("cancel")).toBeTruthy();
  });

  it("emits apply from the apply button", async () => {
    const w = mountModal();
    const applyBtn = w.findAll("button").find((b) => b.text().includes("adminConsole.applyImport"));
    await applyBtn.trigger("click");
    expect(w.emitted("apply")).toBeTruthy();
  });

  it("disables both buttons and shows a spinner while applying", () => {
    const w = mountModal({ applying: true });
    const buttons = w.findAll("button");
    expect(buttons.every((b) => b.attributes("disabled") !== undefined)).toBe(true);
    const applyBtn = buttons.find((b) => b.text().includes("common.loading"));
    expect(applyBtn).toBeTruthy();
    expect(applyBtn.attributes("aria-busy")).toBe("true");
    expect(applyBtn.find(".animate-spin").exists()).toBe(true);
  });

  it("does not disable the buttons when not applying", () => {
    const w = mountModal({ applying: false });
    const applyBtn = w.findAll("button").find((b) => b.text().includes("adminConsole.applyImport"));
    expect(applyBtn.attributes("disabled")).toBeUndefined();
    expect(applyBtn.find(".animate-spin").exists()).toBe(false);
  });

  it("registers a keydown focus trap when a review opens and removes it when it closes", async () => {
    const addSpy = vi.spyOn(document, "addEventListener");
    const removeSpy = vi.spyOn(document, "removeEventListener");

    // Start closed so the watcher (not immediate) fires on the null -> review transition.
    const w = mountModal({ review: null });
    expect(addSpy).not.toHaveBeenCalledWith("keydown", expect.any(Function));

    await w.setProps({ review: review() });
    await flushPromises();
    await nextTick();
    expect(addSpy).toHaveBeenCalledWith("keydown", expect.any(Function));

    await w.setProps({ review: null });
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
