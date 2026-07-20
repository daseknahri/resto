/**
 * Unit tests for OwnerReferralCard — the referral-programme config card extracted
 * from OwnerPromotions.vue (RISK FE-2 supervised v-model slice, mirrors
 * OwnerWinbackCard). The referralForm object is a v-model (defineModel) owned by
 * the parent and passed by reference, so the toggle/points bindings mutate that
 * same object; the save API call + saving/error flags stay in the parent, reached
 * via the save emit (fired on every field @change and the save button).
 */
import { describe, it, expect, vi } from "vitest";
import { reactive } from "vue";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import OwnerReferralCard from "../OwnerReferralCard.vue";

const form = (overrides = {}) => reactive({
  enabled: true,
  reward_points: 50,
  ...overrides,
});

const mountCard = (props = {}) =>
  mount(OwnerReferralCard, {
    props: { form: form(), saving: false, error: "", ...props },
  });

describe("OwnerReferralCard", () => {
  it("renders the kicker, title and explainer", () => {
    const w = mountCard();
    expect(w.text()).toContain("referral.kicker");
    expect(w.text()).toContain("referral.title");
    expect(w.text()).toContain("referral.explainer");
  });

  it("hides the points field when disabled and shows it when enabled", () => {
    expect(mountCard({ form: form({ enabled: false }) }).find("#referral-points").exists()).toBe(false);
    expect(mountCard({ form: form({ enabled: true }) }).find("#referral-points").exists()).toBe(true);
  });

  it("binds the reward-points input to the form as a number and emits save on change", async () => {
    const model = form();
    const w = mountCard({ form: model });
    const points = w.find("#referral-points");
    await points.setValue("120");
    expect(model.reward_points).toBe(120);
    await points.trigger("change");
    expect(w.emitted("save")).toBeTruthy();
  });

  it("emits save when the enabled toggle changes", async () => {
    const w = mountCard();
    await w.find('input[type="checkbox"]').trigger("change");
    expect(w.emitted("save")).toBeTruthy();
  });

  it("shows the save error when provided", () => {
    const w = mountCard({ error: "referral.saveFailed" });
    expect(w.find('[role="alert"]').exists()).toBe(true);
    expect(w.text()).toContain("referral.saveFailed");
  });

  it("disables and relabels the save button while saving", () => {
    const w = mountCard({ saving: true });
    const saveBtn = w.findAll("button").find((b) => b.text().includes("referral.saving"));
    expect(saveBtn).toBeTruthy();
    expect(saveBtn.attributes("disabled")).toBeDefined();
  });

  it("emits save when the save button is clicked", async () => {
    const w = mountCard();
    const saveBtn = w.findAll("button").find((b) => b.text().includes("referral.save"));
    await saveBtn.trigger("click");
    expect(w.emitted("save")).toBeTruthy();
  });
});
