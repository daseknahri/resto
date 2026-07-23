/**
 * Unit tests for CartLineItem — a single cart line-item card extracted from
 * Cart.vue (RISK FE-2). Display + qty stepper / edit / remove affordances,
 * forwarded to the parent as decrement / increment / remove / edit emits; the
 * parent keeps the cart-store mutations. Nothing pricing/payment lives here.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

// Stub QtyStepperButton to a plain button that forwards clicks.
vi.mock("../QtyStepperButton.vue", () => ({
  default: {
    name: "QtyStepperButton",
    template: '<button class="qsb" @click="$emit(\'click\')"><slot /></button>',
  },
}));

import CartLineItem from "../CartLineItem.vue";

const item = (overrides = {}) => ({
  key: "k1",
  name: "Margherita",
  note: "",
  option_labels: [],
  price: 50,
  qty: 2,
  ...overrides,
});

const mountItem = (props = {}) =>
  mount(CartLineItem, {
    props: { item: item(), index: 0, editable: true, formatPrice: (n) => `$${n}`, ...props },
  });

describe("CartLineItem", () => {
  it("renders the name, price-each and line subtotal", () => {
    const w = mountItem({ item: item({ price: 50, qty: 2 }) });
    expect(w.text()).toContain("Margherita");
    expect(w.text()).toContain("$50"); // price each
    expect(w.text()).toContain("$100"); // subtotal 50*2
    expect(w.text()).toContain("cartPage.each");
  });

  it("shows the note, or the option labels when there is no note", () => {
    expect(mountItem({ item: item({ note: "no basil" }) }).text()).toContain("no basil");
    const opts = mountItem({ item: item({ note: "", option_labels: ["Large", "Extra cheese"] }) });
    expect(opts.text()).toContain("Large · Extra cheese");
  });

  it("emits decrement / increment from the two stepper buttons", async () => {
    const w = mountItem();
    const steppers = w.findAll(".qsb");
    await steppers[0].trigger("click"); // −
    await steppers[1].trigger("click"); // +
    expect(w.emitted("decrement")).toBeTruthy();
    expect(w.emitted("increment")).toBeTruthy();
  });

  it("shows the edit button only when editable and emits edit", async () => {
    expect(mountItem({ editable: false }).findAll("button").some((b) => b.text() === "cartPage.editItem")).toBe(false);
    const w = mountItem({ editable: true });
    await w.findAll("button").find((b) => b.text() === "cartPage.editItem").trigger("click");
    expect(w.emitted("edit")).toBeTruthy();
  });

  it("emits remove from the remove button", async () => {
    const w = mountItem();
    await w.findAll("button").find((b) => b.text() === "cartPage.remove").trigger("click");
    expect(w.emitted("remove")).toBeTruthy();
  });
});
