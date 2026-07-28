/**
 * Unit tests for OwnerPromotionFormDrawer — the promotion create/edit form drawer
 * extracted from OwnerPromotions.vue (RISK FE-2 supervised v-model slice). The
 * form object is a v-model (defineModel) owned by the parent and passed by
 * reference, so the field bindings, the promo-type/day toggles and the uppercase
 * code @input mutate that same object; validation, the save API call and open/
 * edit state stay in the parent, reached via close/submit emits.
 */
import { describe, it, expect, vi } from "vitest";
import { reactive } from "vue";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import OwnerPromotionFormDrawer from "../OwnerPromotionFormDrawer.vue";

// The parent passes a `reactive` form object, so mirror that here — nested
// mutations from the child (v-model / toggles) then reactively re-render, just
// like in the app (a plain object would mutate but not re-render aria state).
const form = (overrides = {}) => reactive({
  name: "",
  description: "",
  code: "",
  promo_type: "percentage",
  discount_value: "",
  min_order_amount: "0",
  days: [],
  time_start: "",
  time_end: "",
  active_from: "",
  active_until: "",
  max_uses: "",
  is_active: true,
  ...overrides,
});

const promoTypes = [
  { value: "percentage", label: "Percent" },
  { value: "fixed", label: "Fixed" },
  { value: "free_delivery", label: "Free delivery" },
];
const dayOptions = [
  { key: "mon", label: "Mon" },
  { key: "tue", label: "Tue" },
];

const mountDrawer = (props = {}) =>
  mount(OwnerPromotionFormDrawer, {
    props: {
      form: form(),
      open: true,
      isEdit: false,
      error: "",
      submitting: false,
      promoTypes,
      dayOptions,
      ...props,
    },
    global: { stubs: { teleport: true } },
  });

describe("OwnerPromotionFormDrawer", () => {
  it("renders nothing when open is false", () => {
    expect(mountDrawer({ open: false }).find('[role="dialog"]').exists()).toBe(false);
  });

  it("shows the new-promotion title when creating and the edit title when editing", () => {
    expect(mountDrawer({ isEdit: false }).text()).toContain("ownerPromotions.newPromotion");
    expect(mountDrawer({ isEdit: true }).text()).toContain("common.edit");
  });

  it("writes the name edit back into the shared form object", async () => {
    const model = form();
    const w = mountDrawer({ form: model });
    await w.find("#promo-name").setValue("Launch deal");
    expect(model.name).toBe("Launch deal");
  });

  it("uppercases the promo code on input", async () => {
    const model = form();
    const w = mountDrawer({ form: model });
    await w.find("#promo-code").setValue("save10");
    expect(model.code).toBe("SAVE10");
  });

  it("selects the promo type when a type button is clicked", async () => {
    const model = form({ promo_type: "percentage" });
    const w = mountDrawer({ form: model });
    await w.findAll("button").find((b) => b.text() === "Fixed").trigger("click");
    await w.vm.$nextTick();
    expect(model.promo_type).toBe("fixed");
    // re-query after the re-render: the selected type reflects in aria-pressed
    const fixedAfter = w.findAll("button").find((b) => b.text() === "Fixed");
    const percentAfter = w.findAll("button").find((b) => b.text() === "Percent");
    expect(fixedAfter.attributes("aria-pressed")).toBe("true");
    expect(percentAfter.attributes("aria-pressed")).toBe("false");
  });

  it("hides the discount-value field for free_delivery", () => {
    expect(mountDrawer({ form: form({ promo_type: "percentage" }) }).find("#promo-discount-value").exists()).toBe(true);
    expect(mountDrawer({ form: form({ promo_type: "free_delivery" }) }).find("#promo-discount-value").exists()).toBe(false);
  });

  it("toggles a day in and out of form.days", async () => {
    const model = form({ days: [] });
    const w = mountDrawer({ form: model });
    const tue = w.findAll("button").find((b) => b.text() === "Tue");
    await tue.trigger("click");
    expect(model.days).toEqual(["tue"]);
    await tue.trigger("click");
    expect(model.days).toEqual([]);
  });

  it("renders the live promo preview from the form (percentage + min clause)", () => {
    const w = mountDrawer({ form: form({ promo_type: "percentage", discount_value: "20", min_order_amount: "50" }) });
    expect(w.text()).toContain('ownerPromotions.labelPercentage:{"value":20}');
    expect(w.text()).toContain('ownerPromotions.previewMinClause:{"min":50}');
  });

  it("previews free delivery without a discount value", () => {
    const w = mountDrawer({ form: form({ promo_type: "free_delivery", min_order_amount: "0" }) });
    expect(w.text()).toContain("ownerPromotions.typeFreeDelivery");
    expect(w.text()).not.toContain("previewMinClause");
  });

  it("shows the error alert when an error is provided", () => {
    const w = mountDrawer({ error: "ownerPromotions.nameRequired" });
    expect(w.find('[role="alert"]').exists()).toBe(true);
    expect(w.text()).toContain("ownerPromotions.nameRequired");
  });

  it("emits submit when the submit button is clicked", async () => {
    const w = mountDrawer();
    const submitBtn = w.findAll("button").find((b) => b.text().includes("ownerPromotions.create"));
    await submitBtn.trigger("click");
    expect(w.emitted("submit")).toBeTruthy();
  });

  it("disables the submit button and swaps its label while submitting", () => {
    const w = mountDrawer({ submitting: true, isEdit: true });
    const submitBtn = w.findAll("button").find((b) => b.text().includes("ownerPromotions.saving"));
    expect(submitBtn).toBeTruthy();
    expect(submitBtn.attributes("disabled")).toBeDefined();
  });

  it("emits close from the close button, the backdrop and Escape", async () => {
    const w = mountDrawer();
    const closeBtn = w.findAll("button").find((b) => b.attributes("aria-label") === "common.close");
    await closeBtn.trigger("click");
    const backdrop = w.find(".fixed.inset-0");
    await backdrop.trigger("click");
    await backdrop.trigger("keydown.esc");
    expect(w.emitted("close").length).toBe(3);
  });

  it("registers and removes the keydown focus trap across open transitions", async () => {
    const addSpy = vi.spyOn(document, "addEventListener");
    const removeSpy = vi.spyOn(document, "removeEventListener");
    const w = mountDrawer({ open: false });
    expect(addSpy).not.toHaveBeenCalledWith("keydown", expect.any(Function));
    await w.setProps({ open: true });
    await new Promise((r) => setTimeout(r, 0));
    expect(addSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
    await w.setProps({ open: false });
    expect(removeSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
    addSpy.mockRestore();
    removeSpy.mockRestore();
  });
});
