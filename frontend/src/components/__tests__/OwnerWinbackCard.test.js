/**
 * Unit tests for OwnerWinbackCard — the win-back automation config card extracted
 * from OwnerPromotions.vue (RISK FE-2 supervised v-model slice). The winbackForm
 * object is a v-model (defineModel) owned by the parent and passed by reference,
 * so the toggle/weeks/message bindings mutate that same object; the save API call
 * + saving/error flags stay in the parent, reached via the save emit (fired on
 * every field @change and the save button, matching the save-on-change original).
 */
import { describe, it, expect, vi } from "vitest";
import { reactive } from "vue";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import OwnerWinbackCard from "../OwnerWinbackCard.vue";

const form = (overrides = {}) => reactive({
  enabled: true,
  inactive_weeks: 6,
  message: "We miss you!",
  ...overrides,
});

const mountCard = (props = {}) =>
  mount(OwnerWinbackCard, {
    props: { form: form(), saving: false, error: "", ...props },
  });

describe("OwnerWinbackCard", () => {
  it("renders the kicker, title and explainer with the weeks value", () => {
    const w = mountCard({ form: form({ inactive_weeks: 8 }) });
    expect(w.text()).toContain("winback.kicker");
    expect(w.text()).toContain("winback.title");
    expect(w.text()).toContain('winback.explainer:{"weeks":8}');
  });

  it("hides the fields when disabled and shows them when enabled", () => {
    expect(mountCard({ form: form({ enabled: false }) }).find("#winback-weeks").exists()).toBe(false);
    expect(mountCard({ form: form({ enabled: true }) }).find("#winback-weeks").exists()).toBe(true);
  });

  it("binds the weeks input to the form as a number and emits save on change", async () => {
    const model = form();
    const w = mountCard({ form: model });
    const weeks = w.find("#winback-weeks");
    await weeks.setValue("12");
    expect(model.inactive_weeks).toBe(12);
    await weeks.trigger("change");
    expect(w.emitted("save")).toBeTruthy();
  });

  it("binds the message textarea to the form and shows the char count", async () => {
    const model = form({ message: "hi" });
    const w = mountCard({ form: model });
    expect(w.text()).toContain("2/200");
    await w.find("#winback-msg").setValue("come back");
    expect(model.message).toBe("come back");
  });

  it("emits save when the enabled toggle changes", async () => {
    const w = mountCard();
    await w.find('input[type="checkbox"]').trigger("change");
    expect(w.emitted("save")).toBeTruthy();
  });

  it("shows the save error when provided", () => {
    const w = mountCard({ error: "winback.saveFailed" });
    expect(w.find('[role="alert"]').exists()).toBe(true);
    expect(w.text()).toContain("winback.saveFailed");
  });

  it("emits save and disables/relabels the button while saving", async () => {
    const w = mountCard({ saving: true });
    const saveBtn = w.findAll("button").find((b) => b.text().includes("winback.saving"));
    expect(saveBtn).toBeTruthy();
    expect(saveBtn.attributes("disabled")).toBeDefined();
  });

  it("emits save when the save button is clicked", async () => {
    const w = mountCard();
    const saveBtn = w.findAll("button").find((b) => b.text().includes("winback.save"));
    await saveBtn.trigger("click");
    expect(w.emitted("save")).toBeTruthy();
  });
});
