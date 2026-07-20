/**
 * Unit tests for OwnerHappyHourFormDrawer — the happy-hour create/edit form
 * drawer extracted from OwnerPromotions.vue (RISK FE-2, the first supervised
 * v-model slice). The form object is a v-model (defineModel) owned by the parent
 * and passed by reference, so the field bindings + day/category toggles mutate
 * that same object; validation, the save API call and open/edit state stay in
 * the parent, reached via the close/submit emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) => k,
  }),
}));

import OwnerHappyHourFormDrawer from "../OwnerHappyHourFormDrawer.vue";

const form = (overrides = {}) => ({
  name: "",
  percent_off: 20,
  start_time: "",
  end_time: "",
  days: [],
  category_ids: [],
  is_active: true,
  ...overrides,
});

const dayOptions = [
  { value: 0, label: "Mon" },
  { value: 1, label: "Tue" },
  { value: 2, label: "Wed" },
];
const categories = [
  { id: 10, name: "Drinks" },
  { id: 11, name: "Food" },
];

const mountDrawer = (props = {}) =>
  mount(OwnerHappyHourFormDrawer, {
    props: {
      form: form(),
      open: true,
      isEdit: false,
      error: "",
      submitting: false,
      dayOptions,
      categories,
      ...props,
    },
    global: { stubs: { teleport: true } },
  });

describe("OwnerHappyHourFormDrawer", () => {
  it("renders nothing when open is false", () => {
    const w = mountDrawer({ open: false });
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("shows the add title when creating and the edit title when editing", () => {
    expect(mountDrawer({ isEdit: false }).text()).toContain("happyHour.add");
    expect(mountDrawer({ isEdit: true }).text()).toContain("happyHour.edit");
  });

  it("reflects the form name into the input and writes edits back into the form object", async () => {
    const model = form({ name: "Sunset" });
    const w = mountDrawer({ form: model });
    const nameInput = w.find("#hh-name");
    expect(nameInput.element.value).toBe("Sunset");
    await nameInput.setValue("Late Night");
    expect(model.name).toBe("Late Night"); // mutated in place (shared object)
  });

  it("coerces percent_off to a number (v-model.number)", async () => {
    const model = form();
    const w = mountDrawer({ form: model });
    await w.find("#hh-pct").setValue("35");
    expect(model.percent_off).toBe(35);
    expect(typeof model.percent_off).toBe("number");
  });

  it("toggles a day in and out of form.days when its button is clicked", async () => {
    const model = form({ days: [] });
    const w = mountDrawer({ form: model });
    const tueBtn = w.findAll("button").find((b) => b.text() === "Tue");
    await tueBtn.trigger("click");
    expect(model.days).toEqual([1]);
    await tueBtn.trigger("click");
    expect(model.days).toEqual([]);
  });

  it("toggles a category in and out of form.category_ids", async () => {
    const model = form({ category_ids: [] });
    const w = mountDrawer({ form: model });
    const drinks = w.findAll("button").find((b) => b.text() === "Drinks");
    await drinks.trigger("click");
    expect(model.category_ids).toEqual([10]);
    await drinks.trigger("click");
    expect(model.category_ids).toEqual([]);
  });

  it("marks day/category buttons pressed based on the form", () => {
    const w = mountDrawer({ form: form({ days: [1], category_ids: [11] }) });
    const tue = w.findAll("button").find((b) => b.text() === "Tue");
    const food = w.findAll("button").find((b) => b.text() === "Food");
    expect(tue.attributes("aria-pressed")).toBe("true");
    expect(food.attributes("aria-pressed")).toBe("true");
  });

  it("shows the overnight hint only when start_time > end_time", () => {
    expect(mountDrawer({ form: form({ start_time: "22:00", end_time: "02:00" }) }).text()).toContain("happyHour.overnightHint");
    expect(mountDrawer({ form: form({ start_time: "17:00", end_time: "19:00" }) }).text()).not.toContain("happyHour.overnightHint");
  });

  it("shows the error alert when an error is provided", () => {
    const w = mountDrawer({ error: "happyHour.nameRequired" });
    expect(w.find('[role="alert"]').exists()).toBe(true);
    expect(w.text()).toContain("happyHour.nameRequired");
  });

  it("emits submit when the submit button is clicked", async () => {
    const w = mountDrawer();
    const submitBtn = w.findAll("button").find((b) => b.text().includes("happyHour.create"));
    await submitBtn.trigger("click");
    expect(w.emitted("submit")).toBeTruthy();
  });

  it("disables the submit button and swaps its label while submitting", () => {
    const w = mountDrawer({ submitting: true, isEdit: false });
    const submitBtn = w.findAll("button").find((b) => b.text().includes("happyHour.creating"));
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
