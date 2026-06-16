/**
 * Unit tests for Directory.vue — "Load More" logic (R9d)
 *
 * Mounting approach: full component mount via @vue/test-utils, with:
 *   - vi.mock for ../../lib/api    (controls fetch payloads)
 *   - vi.mock for ../../composables/useI18n  (deterministic keys)
 * No router is needed — Directory.vue does not use useRoute/useRouter.
 *
 * Covers:
 *   (a) results APPEND (not replace) on load-more
 *   (b) rapid-click guard: second loadMore while in-flight is a no-op
 *   (c) next-page request carries the incremented page number
 *   (d) has_more=false hides the Load More button
 *   (e) showLoadMore is false when a client-side filter is active AND
 *       the filtered list is empty
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// ── i18n mock ─────────────────────────────────────────────────────────────────
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

// ── api mock ──────────────────────────────────────────────────────────────────
vi.mock("../../lib/api", () => ({
  default: { get: vi.fn() },
}));

import api from "../../lib/api";
import Directory from "../Directory.vue";

// ── helpers ───────────────────────────────────────────────────────────────────
/** Build a fake restaurant object. */
const makeRestaurant = (n) => ({
  slug: `rest-${n}`,
  name: `Restaurant ${n}`,
  cuisine_type: "Italian",
  city: "Casablanca",
  tagline: "tagline",
  is_open: true,
  logo_url: null,
  business_type: "restaurant",
  delivery_enabled: false,
  rating_average: null,
  rating_count: 0,
});

const PAGE1 = [makeRestaurant(1), makeRestaurant(2)];
const PAGE2 = [makeRestaurant(3), makeRestaurant(4)];

/**
 * Mount Directory with an initial GET that resolves with page-1 data.
 * @param {boolean} hasMore  whether the initial response reports has_more
 */
async function mountDirectory({ hasMore = true } = {}) {
  setActivePinia(createPinia());

  api.get.mockResolvedValueOnce({
    data: {
      restaurants: PAGE1,
      has_more: hasMore,
      page: 1,
      filters: { cities: ["Casablanca"], cuisines: ["Italian"] },
    },
  });

  const wrapper = mount(Directory, {
    global: {
      stubs: {
        // Directory.vue has no router-link, but stub anything that might be
        // pulled in by child components to keep the mount lean.
        RouterLink: { template: "<a><slot /></a>" },
      },
    },
  });

  // Wait for onMounted fetchDirectory() to complete.
  await flushPromises();
  return wrapper;
}

// ── tests ─────────────────────────────────────────────────────────────────────
describe("Directory — Load More logic", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── (a) results APPEND ────────────────────────────────────────────────────
  it("(a) appends page-2 results to existing list (no replace)", async () => {
    const wrapper = await mountDirectory({ hasMore: true });

    // Confirm page-1 items rendered.
    expect(wrapper.text()).toContain("Restaurant 1");
    expect(wrapper.text()).toContain("Restaurant 2");

    // Prime page-2 response.
    api.get.mockResolvedValueOnce({
      data: { restaurants: PAGE2, has_more: false, page: 2, filters: {} },
    });

    // Click the load-more button.
    const btn = wrapper.find("button[aria-label='directory.loadMoreAriaLabel']");
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    await flushPromises();

    // All 4 restaurants must be present.
    expect(wrapper.text()).toContain("Restaurant 1");
    expect(wrapper.text()).toContain("Restaurant 2");
    expect(wrapper.text()).toContain("Restaurant 3");
    expect(wrapper.text()).toContain("Restaurant 4");
  });

  // ── (b) rapid-click guard ─────────────────────────────────────────────────
  it("(b) a second loadMore while one is in-flight does not fire a second request", async () => {
    const wrapper = await mountDirectory({ hasMore: true });

    // Slow promise — won't resolve until we explicitly do so.
    let resolvePage2;
    const slowPromise = new Promise((res) => { resolvePage2 = res; });
    api.get.mockReturnValueOnce(slowPromise);

    const btn = wrapper.find("button[aria-label='directory.loadMoreAriaLabel']");

    // First click — starts the in-flight request.
    await btn.trigger("click");
    // Second click — should be a no-op because loadingMore is true.
    await btn.trigger("click");

    // Resolve the first (and only) request.
    resolvePage2({
      data: { restaurants: PAGE2, has_more: false, page: 2, filters: {} },
    });
    await flushPromises();

    // api.get was called once for initial mount + exactly once for load-more (not twice).
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  // ── (c) next-page request carries incremented page ────────────────────────
  it("(c) the load-more request sends page=2", async () => {
    const wrapper = await mountDirectory({ hasMore: true });

    api.get.mockResolvedValueOnce({
      data: { restaurants: PAGE2, has_more: false, page: 2, filters: {} },
    });

    const btn = wrapper.find("button[aria-label='directory.loadMoreAriaLabel']");
    await btn.trigger("click");
    await flushPromises();

    // The second api.get call (index 1) must have page: 2 in its params.
    const secondCall = api.get.mock.calls[1];
    expect(secondCall[1].params).toMatchObject({ page: 2 });
  });

  // ── (d) has_more=false hides the button ───────────────────────────────────
  it("(d) Load More button is absent when has_more is false from the start", async () => {
    const wrapper = await mountDirectory({ hasMore: false });

    const btn = wrapper.find("button[aria-label='directory.loadMoreAriaLabel']");
    expect(btn.exists()).toBe(false);
  });

  it("(d) Load More button disappears after the last page is loaded", async () => {
    const wrapper = await mountDirectory({ hasMore: true });

    api.get.mockResolvedValueOnce({
      data: { restaurants: PAGE2, has_more: false, page: 2, filters: {} },
    });

    const btn = wrapper.find("button[aria-label='directory.loadMoreAriaLabel']");
    await btn.trigger("click");
    await flushPromises();

    // has_more is now false — button must be gone.
    const btnAfter = wrapper.find("button[aria-label='directory.loadMoreAriaLabel']");
    expect(btnAfter.exists()).toBe(false);
  });

  // ── (e) showLoadMore false when filter active AND filtered list empty ──────
  it("(e) Load More button is hidden when a search filter narrows the list to zero results", async () => {
    const wrapper = await mountDirectory({ hasMore: true });

    // Set a search query that matches no loaded restaurants.
    const input = wrapper.find("input[type='search']");
    await input.setValue("zzz-no-match");
    await wrapper.vm.$nextTick();

    // filteredRestaurants should be empty + anyFilterActive is true → showLoadMore = false.
    const btn = wrapper.find("button[aria-label='directory.loadMoreAriaLabel']");
    expect(btn.exists()).toBe(false);
  });

  it("(e) Load More button is still shown when a filter is active but results are non-empty", async () => {
    const wrapper = await mountDirectory({ hasMore: true });

    // "Restaurant 1" matches the search → filteredRestaurants is non-empty.
    const input = wrapper.find("input[type='search']");
    await input.setValue("Restaurant 1");
    await wrapper.vm.$nextTick();

    const btn = wrapper.find("button[aria-label='directory.loadMoreAriaLabel']");
    expect(btn.exists()).toBe(true);
  });
});
