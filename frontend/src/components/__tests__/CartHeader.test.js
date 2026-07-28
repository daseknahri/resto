/**
 * Unit tests for CartHeader — the Cart page header extracted as a standalone
 * presentational child (RISK FE-2). Display only: kicker + title, the count/plan/
 * table chips (when the cart has items), and a clear-cart button that forwards
 * intent via the `clear` emit. It owns no cart state and touches no pricing.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

vi.mock("../AppIcon.vue", () => ({
  default: { name: "AppIcon", props: ["name"], template: "<span />" },
}));

import CartHeader from "../CartHeader.vue";

const mountHeader = (props = {}) =>
  mount(CartHeader, {
    props: { hasItems: true, countLabel: "3 items", planLabel: "Pro", tableLabel: "", ...props },
  });

describe("CartHeader", () => {
  it("renders the kicker and title", () => {
    const w = mountHeader();
    expect(w.text()).toContain("cartPage.kicker");
    expect(w.text()).toContain("common.cart");
  });

  it("shows the count + plan chips when the cart has items", () => {
    const w = mountHeader({ hasItems: true, countLabel: "3 items", planLabel: "Pro" });
    expect(w.text()).toContain("3 items");
    expect(w.text()).toContain("Pro");
  });

  it("shows the table chip only when a table label is set", () => {
    expect(mountHeader({ tableLabel: "" }).text()).not.toContain("cartPage.table");
    expect(mountHeader({ tableLabel: "T5" }).text()).toContain('cartPage.table:{"table":"T5"}');
  });

  it("hides the chips and clear button when the cart is empty", () => {
    const w = mountHeader({ hasItems: false });
    expect(w.text()).not.toContain("3 items");
    expect(w.find("button").exists()).toBe(false);
  });

  it("emits clear when the clear button is clicked", async () => {
    const w = mountHeader({ hasItems: true });
    await w.find("button").trigger("click");
    expect(w.emitted("clear")).toBeTruthy();
  });
});
