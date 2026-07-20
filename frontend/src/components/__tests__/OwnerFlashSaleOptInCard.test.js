/**
 * Unit tests for OwnerFlashSaleOptInCard — a single platform flash-sale opt-in
 * card from OwnerPromotions.vue, extracted into a standalone presentational
 * component (RISK FE-2). Display only: it renders one platform flash sale and an
 * opt-in/opt-out button that forwards intent to the parent via the `toggle` emit;
 * the parent keeps the list and the opt-in API mutation.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import OwnerFlashSaleOptInCard from "../OwnerFlashSaleOptInCard.vue";

const sale = (overrides = {}) => ({
  id: 9,
  name: "Summer Blast",
  discount_value: 30,
  is_live: false,
  description: "Site-wide summer sale",
  active_until: "2026-08-01",
  opted_in: false,
  ...overrides,
});

const fmtFlashDate = (d) => `date(${d})`;

const mountCard = (props = {}) =>
  mount(OwnerFlashSaleOptInCard, {
    props: { sale: sale(), index: 0, fmtFlashDate, busy: false, ...props },
  });

describe("OwnerFlashSaleOptInCard", () => {
  it("renders the name, discount and formatted until date", () => {
    const w = mountCard();
    expect(w.text()).toContain("Summer Blast");
    expect(w.text()).toContain("30%");
    expect(w.text()).toContain('ownerPromotions.flashUntil:{"date":"date(2026-08-01)"}');
  });

  it("shows the live badge only when the sale is live", () => {
    expect(mountCard({ sale: sale({ is_live: true }) }).text()).toContain("adminFlashSales.live");
    expect(mountCard({ sale: sale({ is_live: false }) }).text()).not.toContain("adminFlashSales.live");
  });

  it("renders the description only when present", () => {
    expect(mountCard({ sale: sale({ description: "hi" }) }).text()).toContain("hi");
    expect(mountCard({ sale: sale({ description: "" }) }).text()).not.toContain("Site-wide");
  });

  it("labels the button opt-in when not opted in, opt-out when opted in", () => {
    expect(mountCard({ sale: sale({ opted_in: false }) }).text()).toContain("ownerPromotions.flashOptIn");
    const optedIn = mountCard({ sale: sale({ opted_in: true }) });
    expect(optedIn.text()).toContain("ownerPromotions.flashOptOut");
    expect(optedIn.find("button").attributes("aria-pressed")).toBe("true");
  });

  it("shows the spinner + loading label and disables the button while busy", () => {
    const w = mountCard({ busy: true });
    const btn = w.find("button");
    expect(btn.attributes("disabled")).toBeDefined();
    expect(btn.find(".animate-spin").exists()).toBe(true);
    expect(w.text()).toContain("common.loading");
  });

  it("emits toggle with the sale when the button is clicked", async () => {
    const s = sale();
    const w = mountCard({ sale: s });
    await w.find("button").trigger("click");
    expect(w.emitted("toggle")[0]).toEqual([s]);
  });
});
