/**
 * Unit tests for OwnerOrders86Board — the 86-board modal extracted from
 * OwnerOrders.vue (RISK FE-2, entangled tier; sibling of OwnerKitchen86Board with
 * the extra sold-out count + bulk mark/reset actions). Presentational shell: it
 * renders the search box, the parent-filtered dish list, the per-dish toggles and
 * the bulk actions, forwarding intent via emits. The dish data, fetch, toggle API,
 * bulk actions and the sort-order Map + filter computed stay in the parent.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) => k,
  }),
}));

import OwnerOrders86Board from "../OwnerOrders86Board.vue";

const dish = (overrides = {}) => ({
  id: 1,
  name: "Margherita",
  category_name: "Pizza",
  is_available: true,
  ...overrides,
});

const mountBoard = (props = {}) =>
  mount(OwnerOrders86Board, {
    props: {
      open: true,
      search: "",
      dishes: [dish()],
      fetching: false,
      togglingId: null,
      soldOutCount: 0,
      hasAvailable: true,
      markingUnavailable: false,
      resetting: false,
      ...props,
    },
    global: { stubs: { teleport: true, transition: true } },
  });

describe("OwnerOrders86Board", () => {
  it("renders nothing when closed", () => {
    expect(mountBoard({ open: false }).find('[role="dialog"]').exists()).toBe(false);
  });

  it("renders the title and a dish row when open", () => {
    const w = mountBoard();
    expect(w.text()).toContain("kitchen.eightySixTitle");
    expect(w.text()).toContain("Margherita");
  });

  it("shows the sold-out count badge only when there are sold-out dishes", () => {
    expect(mountBoard({ soldOutCount: 0 }).find("h2 span").exists()).toBe(false);
    const w = mountBoard({ soldOutCount: 3 });
    expect(w.find("h2 span").text()).toBe("3");
  });

  it("round-trips the search value via v-model:search", async () => {
    const w = mountBoard();
    await w.find('input[type="search"]').setValue("burger");
    expect(w.emitted("update:search")[0]).toEqual(["burger"]);
  });

  it("shows the loading skeleton while fetching and the empty state otherwise", () => {
    expect(mountBoard({ fetching: true, dishes: [] }).find(".animate-pulse").exists()).toBe(true);
    expect(mountBoard({ fetching: false, dishes: [] }).text()).toContain("kitchen.eightySixEmpty");
  });

  it("emits toggle with the dish when its switch is clicked", async () => {
    const d = dish();
    const w = mountBoard({ dishes: [d] });
    await w.find('button[role="switch"]').trigger("click");
    expect(w.emitted("toggle")[0]).toEqual([d]);
  });

  it("shows mark-all-unavailable only when a dish is available and emits it", async () => {
    expect(mountBoard({ hasAvailable: false }).findAll("button").some((b) => b.text().includes("kitchen.markAllUnavailable"))).toBe(false);
    const w = mountBoard({ hasAvailable: true });
    const btn = w.findAll("button").find((b) => b.text().includes("kitchen.markAllUnavailable"));
    await btn.trigger("click");
    expect(w.emitted("markAllUnavailable")).toBeTruthy();
  });

  it("disables mark-all-unavailable while that request is in flight", () => {
    const w = mountBoard({ hasAvailable: true, markingUnavailable: true });
    const btn = w.findAll("button").find((b) => b.text().includes("common.loading"));
    expect(btn).toBeTruthy();
    expect(btn.attributes("disabled")).toBeDefined();
  });

  it("shows reset-all only when there are sold-out dishes and emits it", async () => {
    expect(mountBoard({ soldOutCount: 0 }).findAll("button").some((b) => b.text().includes("ownerHome.resetAllAvailable"))).toBe(false);
    const w = mountBoard({ soldOutCount: 2 });
    const btn = w.findAll("button").find((b) => b.text().includes("ownerHome.resetAllAvailable"));
    await btn.trigger("click");
    expect(w.emitted("resetAll")).toBeTruthy();
  });

  it("emits close from the close button, the backdrop and Escape", async () => {
    const w = mountBoard();
    const closeBtn = w.findAll("button").find((b) => b.attributes("aria-label") === "common.close");
    await closeBtn.trigger("click");
    const dialog = w.find('[role="dialog"]');
    await dialog.find(".absolute.inset-0").trigger("click");
    await dialog.trigger("keydown.esc");
    expect(w.emitted("close").length).toBe(3);
  });
});
