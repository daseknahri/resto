/**
 * Unit tests for OwnerPromotionCard — a single promotion card from
 * OwnerPromotions.vue's list, extracted into a standalone presentational
 * component (RISK FE-2). Display only: it renders one promo and forwards the four
 * actions (toggle / clone / edit / delete) to the parent via emits; the parent
 * keeps the promotions list and the API mutations.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import OwnerPromotionCard from "../OwnerPromotionCard.vue";

const promo = (overrides = {}) => ({
  id: 5,
  name: "Weekend 20%",
  is_active: true,
  code: "WK20",
  description: "20% off weekends",
  min_order_amount: "100",
  days: ["Sat", "Sun"],
  time_start: "18:00",
  time_end: "22:00",
  active_from: null,
  active_until: null,
  use_count: 12,
  ...overrides,
});

const promoLabel = (p) => `label(${p.name})`;

const mountCard = (props = {}) =>
  mount(OwnerPromotionCard, {
    props: { promo: promo(), index: 0, promoLabel, toggling: false, deleting: false, ...props },
  });

describe("OwnerPromotionCard", () => {
  it("renders the name and the discount label from the formatter", () => {
    const w = mountCard();
    expect(w.text()).toContain("Weekend 20%");
    expect(w.text()).toContain("label(Weekend 20%)");
  });

  it("shows the active badge when the promo is active, inactive otherwise", () => {
    expect(mountCard({ promo: promo({ is_active: true }) }).text()).toContain("ownerPromotions.activeNow");
    expect(mountCard({ promo: promo({ is_active: false }) }).text()).toContain("ownerPromotions.inactive");
  });

  it("renders the code badge only when a code is set", () => {
    expect(mountCard({ promo: promo({ code: "WK20" }) }).text()).toContain("WK20");
    expect(mountCard({ promo: promo({ code: "" }) }).text()).not.toContain("ownerPromotions.codeLabel");
  });

  it("renders the description only when present", () => {
    expect(mountCard({ promo: promo({ description: "hi there" }) }).text()).toContain("hi there");
    const noDesc = mountCard({ promo: promo({ description: "" }) });
    expect(noDesc.text()).not.toContain("hi there");
  });

  it("renders the use-count metadata chip", () => {
    const w = mountCard({ promo: promo({ use_count: 12 }) });
    expect(w.text()).toContain('ownerPromotions.useCount_other:{"count":12}');
  });

  it("emits toggle with the promo when the switch is clicked", async () => {
    const p = promo();
    const w = mountCard({ promo: p });
    await w.find('[role="switch"]').trigger("click");
    expect(w.emitted("toggle")[0]).toEqual([p]);
  });

  it("emits clone, edit and delete with the promo", async () => {
    const p = promo();
    const w = mountCard({ promo: p });
    const buttons = w.findAll("button");
    // clone is the button with the duplicate svg (no text), edit/delete carry text
    const editBtn = buttons.find((b) => b.text() === "common.edit");
    const deleteBtn = buttons.find((b) => b.text() === "common.delete");
    const cloneBtn = buttons.find(
      (b) => b.attributes("aria-label")?.includes("clonePromoAriaLabel"),
    );
    await cloneBtn.trigger("click");
    await editBtn.trigger("click");
    await deleteBtn.trigger("click");
    expect(w.emitted("clone")[0]).toEqual([p]);
    expect(w.emitted("edit")[0]).toEqual([p]);
    expect(w.emitted("delete")[0]).toEqual([p]);
  });

  it("disables the toggle while its request is in flight", () => {
    const w = mountCard({ toggling: true });
    expect(w.find('[role="switch"]').attributes("disabled")).toBeDefined();
  });

  it("disables the delete button while its request is in flight", () => {
    const w = mountCard({ deleting: true });
    const deleteBtn = w.findAll("button").find((b) => b.text() === "common.delete");
    expect(deleteBtn.attributes("disabled")).toBeDefined();
  });
});
