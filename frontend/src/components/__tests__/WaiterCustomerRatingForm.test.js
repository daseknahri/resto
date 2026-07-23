/**
 * Unit tests for WaiterCustomerRatingForm — the inner form body of WaiterPage's
 * customer trust-rating modal, a FRAGMENT child with two-way score/note models
 * (RISK FE-2). The parent keeps the modal shell + focus trap + submit handler;
 * here we verify the stars/note/cancel/submit behaviour.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));

import WaiterCustomerRatingForm from "../WaiterCustomerRatingForm.vue";

const order = { customer_name: "Alice", order_number: 12 };
const mountIt = (props = {}) =>
  mount(WaiterCustomerRatingForm, { props: { order, busy: false, score: 0, note: "", ...props } });

describe("WaiterCustomerRatingForm", () => {
  it("renders the identity line, five stars and the note input", () => {
    const w = mountIt();
    expect(w.text()).toContain("Alice");
    // 5 star buttons + cancel + submit = 7 buttons.
    expect(w.findAll("button")).toHaveLength(7);
    expect(w.find("input").exists()).toBe(true);
  });

  it("highlights stars up to the current score", () => {
    const stars = mountIt({ score: 3 }).findAll('button[aria-pressed]');
    expect(stars.map((s) => s.attributes("aria-pressed"))).toEqual([
      "true", "true", "true", "false", "false",
    ]);
  });

  it("emits update:score when a star is clicked", async () => {
    const w = mountIt({ score: 0 });
    await w.findAll('button[aria-pressed]')[3].trigger("click");
    expect(w.emitted("update:score")[0]).toEqual([4]);
  });

  it("emits update:note when the note is typed", async () => {
    const w = mountIt();
    await w.find("input").setValue("great guest");
    expect(w.emitted("update:note")[0]).toEqual(["great guest"]);
  });

  it("disables submit when score is 0 and enables it once a score is set", () => {
    expect(mountIt({ score: 0 }).find(".ui-btn-primary").attributes("disabled")).toBeDefined();
    expect(mountIt({ score: 4 }).find(".ui-btn-primary").attributes("disabled")).toBeUndefined();
  });

  it("shows the spinner + loading label and disables submit while busy", () => {
    const w = mountIt({ score: 4, busy: true });
    expect(w.find(".animate-spin").exists()).toBe(true);
    expect(w.text()).toContain("common.loading");
    expect(w.find(".ui-btn-primary").attributes("disabled")).toBeDefined();
  });

  it("emits close from cancel and submit from the primary button", async () => {
    const w = mountIt({ score: 4 });
    const buttons = w.findAll("button");
    await buttons[5].trigger("click"); // cancel
    await buttons[6].trigger("click"); // submit
    expect(w.emitted("close")).toBeTruthy();
    expect(w.emitted("submit")).toBeTruthy();
  });
});
