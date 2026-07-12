/**
 * Unit tests for WaiterTableQRModal — the table QR-code modal of
 * WaiterPage.vue, extracted into a standalone presentational component
 * (RISK FE-2). QR generation and the `qrDataUrl`/`qrTableLabel` state stay
 * owned by the parent; this component only renders the given data URL +
 * label and asks the parent to clear them via the `close` emit.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import WaiterTableQRModal from "../WaiterTableQRModal.vue";

const mountModal = (props = {}) =>
  mount(WaiterTableQRModal, {
    props: { qrDataUrl: "", qrTableLabel: "", ...props },
    global: { stubs: { teleport: true } },
  });

describe("WaiterTableQRModal", () => {
  it("renders nothing when qrDataUrl is empty", () => {
    const w = mountModal();
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("renders the dialog with the QR image and table label when qrDataUrl is set", () => {
    const w = mountModal({ qrDataUrl: "data:image/png;base64,abc123", qrTableLabel: "Table 5" });
    expect(w.find('[role="dialog"]').exists()).toBe(true);
    expect(w.text()).toContain("Table 5");
    const img = w.find("img");
    expect(img.exists()).toBe(true);
    expect(img.attributes("src")).toBe("data:image/png;base64,abc123");
    expect(img.attributes("alt")).toContain("Table 5");
  });

  it("emits close when the close button is clicked", async () => {
    const w = mountModal({ qrDataUrl: "data:image/png;base64,abc123", qrTableLabel: "Table 5" });
    await w.find("button").trigger("click");
    expect(w.emitted("close")).toBeTruthy();
  });

  it("emits close when the backdrop is clicked", async () => {
    const w = mountModal({ qrDataUrl: "data:image/png;base64,abc123", qrTableLabel: "Table 5" });
    const backdrop = w.findAll("div").find((d) => d.classes().includes("backdrop-blur-sm"));
    expect(backdrop).toBeTruthy();
    await backdrop.trigger("click");
    expect(w.emitted("close")).toBeTruthy();
  });

  it("emits close on Escape keydown", async () => {
    const w = mountModal({ qrDataUrl: "data:image/png;base64,abc123", qrTableLabel: "Table 5" });
    const backdrop = w.findAll("div").find((d) => d.classes().includes("backdrop-blur-sm"));
    await backdrop.trigger("keydown.esc");
    expect(w.emitted("close")).toBeTruthy();
  });
});
