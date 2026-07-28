/**
 * Unit tests for CartPlaceOrderButton — the primary place-order CTA, extracted as
 * a DUMB presentational button (RISK FE-2). It owns no checkout logic: busy /
 * disabled / label are props (the parent's verbatim expressions) and the tap emits
 * `place`. The parent keeps placeInAppOrder and every condition.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../AppIcon.vue", () => ({
  default: { name: "AppIcon", props: ["name"], template: '<span class="app-icon" />' },
}));

import CartPlaceOrderButton from "../CartPlaceOrderButton.vue";

const mountBtn = (props = {}) =>
  mount(CartPlaceOrderButton, {
    props: { busy: false, disabled: false, label: "Place order", ...props },
  });

describe("CartPlaceOrderButton", () => {
  it("renders the label passed by the parent", () => {
    expect(mountBtn({ label: "Place order" }).text()).toContain("Place order");
    expect(mountBtn({ label: "Restaurant closed" }).text()).toContain("Restaurant closed");
  });

  it("shows the cart icon when idle and the spinner (no icon) when busy", () => {
    const idle = mountBtn({ busy: false });
    expect(idle.find(".app-icon").exists()).toBe(true);
    expect(idle.find(".animate-spin").exists()).toBe(false);
    const busy = mountBtn({ busy: true });
    expect(busy.find(".animate-spin").exists()).toBe(true);
    expect(busy.find(".app-icon").exists()).toBe(false);
    expect(busy.find("button").attributes("aria-busy")).toBe("true");
  });

  it("reflects the disabled prop on the button", () => {
    expect(mountBtn({ disabled: true }).find("button").attributes("disabled")).toBeDefined();
    expect(mountBtn({ disabled: false }).find("button").attributes("disabled")).toBeUndefined();
  });

  it("emits place when clicked", async () => {
    const w = mountBtn({ disabled: false });
    await w.find("button").trigger("click");
    expect(w.emitted("place")).toBeTruthy();
  });
});
