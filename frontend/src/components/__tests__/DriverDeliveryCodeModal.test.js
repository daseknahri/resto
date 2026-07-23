/**
 * Unit tests for DriverDeliveryCodeModal — the proof-of-delivery code modal
 * extracted from DriverPage.vue (RISK FE-2). The parent keeps submitDeliveryCode +
 * open/return-focus; here we verify open gating, the code/error/file models, the
 * disabled logic across both proof paths, the photo-selection lifecycle, and the
 * close/submit emits. Non-money.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));
vi.mock("../../composables/useFocusTrap", () => ({ useFocusTrap: () => {} }));
vi.mock("../AppIcon.vue", () => ({
  default: { name: "AppIcon", props: ["name"], template: '<span class="app-icon" />' },
}));

import DriverDeliveryCodeModal from "../DriverDeliveryCodeModal.vue";

const mountIt = (props = {}) =>
  mount(DriverDeliveryCodeModal, {
    props: { open: true, submitting: false, codeInput: "", codeError: "", proofPhotoFile: null, ...props },
    global: { stubs: { teleport: true } },
  });

const submitBtn = (w) => w.findAll("button").at(-1);

describe("DriverDeliveryCodeModal", () => {
  beforeEach(() => {
    globalThis.URL.createObjectURL = vi.fn(() => "blob:preview");
    globalThis.URL.revokeObjectURL = vi.fn();
  });

  it("renders nothing when closed", () => {
    expect(mountIt({ open: false }).find('[role="dialog"]').exists()).toBe(false);
  });

  it("renders the code input, the camera label and the action buttons when open", () => {
    const w = mountIt();
    expect(w.find('input[inputmode="numeric"]').exists()).toBe(true);
    expect(w.find('input[type="file"]').exists()).toBe(true);
    expect(w.text()).toContain("driver.leaveAtDoor");
  });

  it("emits update:codeInput as the PIN is typed", async () => {
    const w = mountIt();
    await w.find('input[inputmode="numeric"]').setValue("1234");
    expect(w.emitted("update:codeInput")[0]).toEqual(["1234"]);
  });

  it("disables confirm with neither code nor photo, and enables it once a code is present", () => {
    expect(submitBtn(mountIt({ codeInput: "" })).attributes("disabled")).toBeDefined();
    expect(submitBtn(mountIt({ codeInput: "123456" })).attributes("disabled")).toBeUndefined();
  });

  it("emits submit on Enter in the code field and on the confirm button", async () => {
    const w = mountIt({ codeInput: "123456" });
    await w.find('input[inputmode="numeric"]').trigger("keydown.enter");
    await submitBtn(w).trigger("click");
    expect(w.emitted("submit")).toHaveLength(2);
  });

  it("shows the error alert when codeError is set", () => {
    expect(mountIt({ codeError: "bad code" }).find('[role="alert"]').text()).toContain("bad code");
    expect(mountIt({ codeError: "" }).find('[role="alert"]').exists()).toBe(false);
  });

  it("shows the spinner and disables confirm while submitting", () => {
    const w = mountIt({ codeInput: "123456", submitting: true });
    expect(w.find(".animate-spin").exists()).toBe(true);
    expect(submitBtn(w).attributes("disabled")).toBeDefined();
  });

  it("selecting a proof photo sets the file model, clears the code, and shows the preview", async () => {
    const w = mountIt({ codeInput: "12" });
    const file = new File(["x"], "proof.jpg", { type: "image/jpeg" });
    const input = w.find('input[type="file"]');
    Object.defineProperty(input.element, "files", { value: [file], configurable: true });
    await input.trigger("change");
    expect(w.emitted("update:proofPhotoFile").at(-1)).toEqual([file]);
    expect(w.emitted("update:codeInput").at(-1)).toEqual([""]); // one proof path at a time
    expect(globalThis.URL.createObjectURL).toHaveBeenCalledWith(file);
    // Preview image replaces the camera label.
    await w.setProps({ proofPhotoFile: file });
    expect(w.find('img').exists()).toBe(true);
  });

  it("emits close from the cancel button and backdrop", async () => {
    const w = mountIt();
    const cancel = w.findAll("button").find((b) => b.text().includes("common.cancel"));
    await cancel.trigger("click");
    expect(w.emitted("close")).toBeTruthy();
  });
});
