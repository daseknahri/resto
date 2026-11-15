/**
 * Mount test for OwnerDashboardDishPanel.vue (the 86 / dish-availability panel
 * on the owner dashboard, ~340 lines).
 *
 * WHY (S1-A, B-04): this panel's reset-all action used to call the bare
 * whole-menu `/owner/dishes/reset-availability/` endpoint with no scope and no
 * confirmation. It now confirms with the sold-out count and posts the explicit
 * dish ids to the dedicated `/owner/dishes/bulk-reset-availability/` endpoint.
 * Mounting the REAL panel (not a stub) exercises the open → reset → confirm →
 * post → local-state path end to end.
 *
 * Pattern-faithful to pages/__tests__/OwnerOrders.mount.test.js:
 *   - mount (the panel's only child is AppIcon, stubbed)
 *   - real pinia (toast store runs for real) + a mocked lib/api
 *   - useI18n mocked (key verbatim → assertions read the raw key)
 *   - useConfirmModal left REAL (jsdom-safe singleton): tests settle the pending
 *     confirm with `_settle(true/false)`, exactly like a user tapping the modal.
 *   - staleCache left REAL (jsdom-safe: localStorage-backed, falls through).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) => k, // key verbatim → assertions read the raw key
  }),
}));

vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import api from "../../lib/api";
import { useConfirmModal } from "../../composables/useConfirmModal";
import OwnerDashboardDishPanel from "../OwnerDashboardDishPanel.vue";

// Two sold-out dishes (ids 11, 12) + one available dish (id 13). The panel's
// reset scope is exactly the sold-out pair — the available dish must never be
// sent, and the unpublished dish (id 14) must never be sent either.
const dishes = [
  { id: 11, name: "Soup", slug: "soup", is_published: true, is_available: false, stock_qty: 0, category_name: "Starters", category_slug: "starters" },
  { id: 12, name: "Salad", slug: "salad", is_published: true, is_available: false, stock_qty: 0, category_name: "Starters", category_slug: "starters" },
  { id: 13, name: "Steak", slug: "steak", is_published: true, is_available: true, stock_qty: 5, category_name: "Mains", category_slug: "mains" },
  { id: 14, name: "Secret Soup", slug: "secret-soup", is_published: false, is_available: false, stock_qty: 0, category_name: "Starters", category_slug: "starters" },
];

const mountPanel = (props = {}) =>
  mount(OwnerDashboardDishPanel, {
    props: { initialSoldOutCount: 2, preloadedDishes: dishes.map((d) => ({ ...d })), ...props },
    global: {
      stubs: {
        AppIcon: { template: "<span />" },
      },
    },
  });

// NOTE: mountPanel deep-copies the shared `dishes` fixture — the panel mutates
// dish.is_available in place on reset, so a shared array would leak test 2's
// restore into test 3 (soldOutCount 0, no reset button).
// Open the panel (summary click → toggle → preloaded dishes load) and return
// the reset-all button. The button only renders while soldOutCount > 0.
const openPanelAndFindReset = async (wrapper) => {
  await wrapper.find("summary").trigger("click");
  await flushPromises();
  const btn = wrapper.findAll("button").find((b) => b.text().includes("ownerHome.resetAllAvailable"));
  expect(btn.exists()).toBe(true);
  return btn;
};

describe("OwnerDashboardDishPanel — S1-A (B-04 scoped reset-all)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  it("mounts closed with the sold-out badge and no crash", async () => {
    wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerHome.dishAvailability");
    // Summary badge: 2 sold out (from the initialSoldOutCount prop, pre-load).
    expect(wrapper.text()).toContain("ownerHome.soldOut");
  });

  it("B-04: reset-all confirms with the sold-out count and posts the explicit dish ids", async () => {
    wrapper = mountPanel();
    const btn = await openPanelAndFindReset(wrapper);
    api.post.mockResolvedValueOnce({ data: { restored: 2, stock_cleared: 2, requested: 2 } });
    await btn.trigger("click");
    await flushPromises();
    // No POST before the owner approves the confirm dialog.
    expect(api.post).not.toHaveBeenCalledWith("/owner/dishes/bulk-reset-availability/", expect.anything());
    useConfirmModal()._settle(true);
    await flushPromises();
    await flushPromises();
    // Only the visible sold-out dishes — never the available one (13) or the
    // unpublished one (14), and never the bare whole-menu endpoint.
    expect(api.post).toHaveBeenCalledWith("/owner/dishes/bulk-reset-availability/", { dish_ids: [11, 12] });
    expect(api.post).not.toHaveBeenCalledWith("/owner/dishes/reset-availability/", expect.anything());
    // Local state: both dishes are available again, so the reset button and the
    // sold-out badge disappear and every toggle reads "available".
    expect(wrapper.findAll("button").some((b) => b.text().includes("ownerHome.resetAllAvailable"))).toBe(false);
    expect(wrapper.text()).not.toContain("ownerHome.soldOut");
    expect(wrapper.text()).not.toContain("ownerHome.dish86d");
  });

  it("B-04: declining the reset confirm posts nothing and leaves dishes sold out", async () => {
    wrapper = mountPanel();
    const btn = await openPanelAndFindReset(wrapper);
    await btn.trigger("click");
    await flushPromises();
    useConfirmModal()._settle(false);
    await flushPromises();
    expect(api.post).not.toHaveBeenCalled();
    // The reset button is still there — nothing was restored.
    expect(wrapper.findAll("button").some((b) => b.text().includes("ownerHome.resetAllAvailable"))).toBe(true);
    expect(wrapper.text()).toContain("ownerHome.dish86d");
  });

  it("B-04: no reset button when nothing is sold out (count pre-check)", async () => {
    wrapper = mountPanel({
      initialSoldOutCount: 0,
      preloadedDishes: [
        { id: 13, name: "Steak", slug: "steak", is_published: true, is_available: true, stock_qty: 5, category_name: "Mains", category_slug: "mains" },
      ],
    });
    await wrapper.find("summary").trigger("click");
    await flushPromises();
    expect(wrapper.findAll("button").some((b) => b.text().includes("ownerHome.resetAllAvailable"))).toBe(false);
    expect(api.post).not.toHaveBeenCalled();
  });
});
