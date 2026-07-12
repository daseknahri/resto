/**
 * Unit tests for OwnerPromotionsEmptyState — the empty-list state of
 * OwnerPromotions.vue, extracted into a standalone presentational component
 * (RISK FE-2). Purely static markup with a single CTA that asks the parent
 * to open the create drawer via the `create` emit.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

import OwnerPromotionsEmptyState from "../OwnerPromotionsEmptyState.vue";

describe("OwnerPromotionsEmptyState", () => {
  it("renders the empty-state copy", () => {
    const w = mount(OwnerPromotionsEmptyState);
    expect(w.text()).toContain("ownerPromotions.noPromotions");
    expect(w.text()).toContain("ownerPromotions.noPromotionsHint");
    expect(w.text()).toContain("ownerPromotions.newPromotion");
  });

  it("emits create when the CTA button is clicked", async () => {
    const w = mount(OwnerPromotionsEmptyState);
    await w.find("button").trigger("click");
    expect(w.emitted("create")).toHaveLength(1);
  });

  it("emits no create event before any interaction", () => {
    const w = mount(OwnerPromotionsEmptyState);
    expect(w.emitted("create")).toBeUndefined();
  });
});
