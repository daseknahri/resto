/**
 * Unit tests for CartWhatsAppButton — the "send via WhatsApp" CTA, a DUMB
 * presentational button with two styles (RISK FE-2). busy / label / variant are
 * props; the tap emits `whatsapp`; the parent keeps openWhatsApp + the state.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../AppIcon.vue", () => ({
  default: { name: "AppIcon", props: ["name"], template: '<span class="app-icon" />' },
}));

import CartWhatsAppButton from "../CartWhatsAppButton.vue";

const mountBtn = (props = {}) =>
  mount(CartWhatsAppButton, { props: { busy: false, label: "Send via WhatsApp", variant: "primary", ...props } });

describe("CartWhatsAppButton", () => {
  it("renders the label", () => {
    expect(mountBtn({ label: "Send via WhatsApp" }).text()).toContain("Send via WhatsApp");
  });

  it("uses the outline style for primary and the underline link style for link", () => {
    expect(mountBtn({ variant: "primary" }).find("button").classes()).toContain("ui-btn-outline");
    expect(mountBtn({ variant: "link" }).find("button").classes()).toContain("ui-top-link");
  });

  it("sizes the icon per variant", () => {
    expect(mountBtn({ variant: "primary" }).find(".app-icon").classes()).toContain("h-4");
    expect(mountBtn({ variant: "link" }).find(".app-icon").classes()).toContain("h-3.5");
  });

  it("shows the spinner when busy and disables the button", () => {
    const busy = mountBtn({ busy: true });
    expect(busy.find(".animate-spin").exists()).toBe(true);
    expect(busy.find(".app-icon").exists()).toBe(false);
    expect(busy.find("button").attributes("disabled")).toBeDefined();
  });

  it("emits whatsapp when clicked", async () => {
    const w = mountBtn();
    await w.find("button").trigger("click");
    expect(w.emitted("whatsapp")).toBeTruthy();
  });
});
