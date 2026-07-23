/**
 * Unit tests for CartCheckoutButton — the "proceed to checkout" (PSP) CTA, a DUMB
 * presentational button (RISK FE-2). busy / label are props (parent's verbatim
 * values) and the tap emits `checkout`; the parent keeps startCheckout.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../AppIcon.vue", () => ({
  default: { name: "AppIcon", props: ["name"], template: '<span class="app-icon" />' },
}));

import CartCheckoutButton from "../CartCheckoutButton.vue";

const mountBtn = (props = {}) =>
  mount(CartCheckoutButton, { props: { busy: false, label: "Proceed to checkout", ...props } });

describe("CartCheckoutButton", () => {
  it("renders the label", () => {
    expect(mountBtn({ label: "Proceed to checkout" }).text()).toContain("Proceed to checkout");
  });

  it("shows the card icon when idle and the spinner when busy (disabled + aria-busy)", () => {
    const idle = mountBtn({ busy: false });
    expect(idle.find(".app-icon").exists()).toBe(true);
    expect(idle.find(".animate-spin").exists()).toBe(false);
    const busy = mountBtn({ busy: true });
    expect(busy.find(".animate-spin").exists()).toBe(true);
    expect(busy.find("button").attributes("disabled")).toBeDefined();
    expect(busy.find("button").attributes("aria-busy")).toBe("true");
  });

  it("emits checkout when clicked", async () => {
    const w = mountBtn();
    await w.find("button").trigger("click");
    expect(w.emitted("checkout")).toBeTruthy();
  });
});
