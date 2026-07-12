/**
 * Unit tests for CartPromoCode — the promo-code row of Cart.vue (customer
 * checkout page), extracted into a standalone presentational component
 * (RISK FE-2). This component does no money/discount computation and makes
 * no API calls; it only renders whatever it's given and asks the parent to
 * apply mutations via emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import CartPromoCode from "../CartPromoCode.vue";

const AppIconStub = { props: ["name"], template: "<i />" };

const mountComp = (props = {}) =>
  mount(CartPromoCode, {
    props: {
      promoApplied: null,
      promoOpen: false,
      promoCode: "",
      promoChecking: false,
      promoError: "",
      ...props,
    },
    global: { stubs: { AppIcon: AppIconStub } },
  });

describe("CartPromoCode", () => {
  it("renders the collapsed CTA when no promo is applied and no code is entered", () => {
    const w = mountComp();
    expect(w.text()).toContain("cartPage.promoCodeCta");
    expect(w.find('input[type="text"]').isVisible()).toBe(false);
  });

  it("emits toggle-open when the CTA button is clicked", async () => {
    const w = mountComp();
    await w.find("button").trigger("click");
    expect(w.emitted("toggle-open")).toBeTruthy();
  });

  it("shows the input row and apply button once promoOpen is true", () => {
    const w = mountComp({ promoOpen: true });
    expect(w.find('input[type="text"]').isVisible()).toBe(true);
    expect(w.text()).toContain("cartPage.promoApply");
  });

  it("emits promo-code-input with the raw typed value on input", async () => {
    const w = mountComp({ promoOpen: true, promoCode: "SAVE" });
    const input = w.find('input[type="text"]');
    await input.setValue("save10");
    const emitted = w.emitted("promo-code-input");
    expect(emitted).toBeTruthy();
    expect(emitted[0]).toEqual(["save10"]);
  });

  it("emits apply when Enter is pressed in the input", async () => {
    const w = mountComp({ promoOpen: true, promoCode: "SAVE10" });
    await w.find('input[type="text"]').trigger("keyup.enter");
    expect(w.emitted("apply")).toBeTruthy();
  });

  it("emits apply when the apply button is clicked", async () => {
    const w = mountComp({ promoOpen: true, promoCode: "SAVE10" });
    const applyBtn = w.findAll("button")[1];
    await applyBtn.trigger("click");
    expect(w.emitted("apply")).toBeTruthy();
  });

  it("disables the apply button when the code is blank", () => {
    const w = mountComp({ promoOpen: true, promoCode: "   " });
    const applyBtn = w.findAll("button")[1];
    expect(applyBtn.attributes("disabled")).toBeDefined();
  });

  it("disables the apply button and shows loading text while checking", () => {
    const w = mountComp({ promoOpen: true, promoCode: "SAVE10", promoChecking: true });
    const applyBtn = w.findAll("button")[1];
    expect(applyBtn.attributes("disabled")).toBeDefined();
    expect(applyBtn.attributes("aria-busy")).toBe("true");
    expect(w.text()).toContain("common.loading");
  });

  it("shows the error message when promoError is set", () => {
    const w = mountComp({ promoOpen: true, promoError: "cartPage.promoInvalid" });
    expect(w.text()).toContain("cartPage.promoInvalid");
  });

  it("renders the applied state with a percentage label and hides the input row", () => {
    const w = mountComp({
      promoApplied: { name: "WELCOME10", promo_type: "percentage", discount_value: 10 },
    });
    expect(w.text()).toContain("WELCOME10");
    expect(w.text()).toContain("ownerPromotions.labelPercentage");
    expect(w.find('input[type="text"]').exists()).toBe(false);
    expect(w.text()).toContain("cartPage.promoRemove");
  });

  it("renders the applied state with a fixed-amount label", () => {
    const w = mountComp({
      promoApplied: { name: "FLAT20", promo_type: "fixed", discount_value: 20 },
    });
    expect(w.text()).toContain("ownerPromotions.labelFixed");
  });

  it("renders the applied state with a free-delivery label", () => {
    const w = mountComp({
      promoApplied: { name: "FREEDEL", promo_type: "free_delivery", discount_value: 0 },
    });
    expect(w.text()).toContain("ownerPromotions.typeFreeDelivery");
  });

  it("emits remove when the remove button is clicked in the applied state", async () => {
    const w = mountComp({
      promoApplied: { name: "WELCOME10", promo_type: "percentage", discount_value: 10 },
    });
    await w.find("button").trigger("click");
    expect(w.emitted("remove")).toBeTruthy();
  });
});
