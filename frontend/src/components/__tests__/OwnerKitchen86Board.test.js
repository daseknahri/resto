/**
 * Unit tests for OwnerKitchen86Board — the 86-board modal extracted from
 * OwnerKitchen.vue (RISK FE-2, entangled tier). Presentational shell: it renders
 * the search box, the (parent-filtered + stably-sorted) dish list and the per-dish
 * availability toggles, and forwards intent via emits. The dish data, fetch, the
 * toggle API and the sort-order Map + filter computed stay in the parent; the
 * search string round-trips via v-model:search.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) => k,
  }),
}));

import OwnerKitchen86Board from "../OwnerKitchen86Board.vue";

const dish = (overrides = {}) => ({
  id: 1,
  name: "Margherita",
  category_name: "Pizza",
  is_available: true,
  ...overrides,
});

const mountBoard = (props = {}) =>
  mount(OwnerKitchen86Board, {
    props: {
      open: true,
      search: "",
      dishes: [dish()],
      fetching: false,
      togglingId: null,
      ...props,
    },
    global: { stubs: { teleport: true, transition: true } },
  });

describe("OwnerKitchen86Board", () => {
  it("renders nothing when closed", () => {
    const w = mountBoard({ open: false });
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("renders the title and a dish row when open", () => {
    const w = mountBoard();
    expect(w.find('[role="dialog"]').exists()).toBe(true);
    expect(w.text()).toContain("kitchen.eightySixTitle");
    expect(w.text()).toContain("Margherita");
    expect(w.text()).toContain("Pizza");
  });

  it("round-trips the search value via v-model:search", async () => {
    const w = mountBoard({ search: "" });
    await w.find('input[type="search"]').setValue("burger");
    expect(w.emitted("update:search")[0]).toEqual(["burger"]);
  });

  it("shows the loading skeleton while fetching", () => {
    const w = mountBoard({ fetching: true, dishes: [] });
    expect(w.find(".animate-pulse").exists()).toBe(true);
  });

  it("shows the empty state when there are no dishes and not fetching", () => {
    const w = mountBoard({ dishes: [], fetching: false });
    expect(w.text()).toContain("kitchen.eightySixEmpty");
  });

  it("labels the toggle available / sold-out from is_available", () => {
    expect(mountBoard({ dishes: [dish({ is_available: true })] }).text()).toContain("kitchen.eightySixAvailable");
    expect(mountBoard({ dishes: [dish({ is_available: false })] }).text()).toContain("kitchen.eightySixSoldOut");
  });

  it("emits toggle with the dish when its switch is clicked", async () => {
    const d = dish();
    const w = mountBoard({ dishes: [d] });
    await w.find('button[role="switch"]').trigger("click");
    expect(w.emitted("toggle")[0]).toEqual([d]);
  });

  it("disables the toggle and shows an ellipsis while that dish is toggling", () => {
    const w = mountBoard({ dishes: [dish({ id: 7 })], togglingId: 7 });
    const sw = w.find('button[role="switch"]');
    expect(sw.attributes("disabled")).toBeDefined();
    expect(sw.attributes("aria-busy")).toBe("true");
    expect(sw.text()).toBe("…");
  });

  it("emits close from the close button, the backdrop and Escape", async () => {
    const w = mountBoard();
    const closeBtn = w.findAll("button").find((b) => b.attributes("aria-label") === "common.close");
    await closeBtn.trigger("click");
    const dialog = w.find('[role="dialog"]');
    await dialog.find(".absolute.inset-0").trigger("click"); // backdrop
    await dialog.trigger("keydown.esc");
    expect(w.emitted("close").length).toBe(3);
  });
});
