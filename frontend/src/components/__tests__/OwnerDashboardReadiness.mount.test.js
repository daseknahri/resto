/**
 * Mount test for OwnerDashboardReadiness.vue — G4b-E (B-38).
 *
 * WHY: the categories/dishes fetch failure used to emit "loaded" with all-zero
 * counts, so a network failure made an established restaurant look unlaunched
 * (0%, every item "missing") — and drafts counted as "added". Mounting the REAL
 * component exercises the fetch → counts → emit path end to end.
 *
 * Pattern-faithful to components/__tests__/OwnerDashboardDishPanel.mount.test.js:
 *   - mount + real pinia (tenant store runs for real; the profile is empty in
 *     these tests, so contact/theme/published checks are all false) + mocked
 *     lib/api, URL-routed per test via mockImplementation
 *   - useI18n mocked (key verbatim → assertions read the raw key)
 *   - vue-router mocked with a RouterLink stub (the component imports RouterLink
 *     and renders it for each not-ready checklist item).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
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
import OwnerDashboardReadiness from "../OwnerDashboardReadiness.vue";

const mountReadiness = () =>
  mount(OwnerDashboardReadiness, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
      },
    },
  });

const retryButton = (wrapper) =>
  wrapper.findAll("button").find((b) => b.text().includes("common.retry"));

describe("OwnerDashboardReadiness — G4b-E (B-38 error state + published counts)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    api.get.mockImplementation(() => Promise.resolve({ data: [] }));
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // B-38 (published counts): 1 published + 1 draft category, 2 published +
  // 1 draft dish → the emitted counts are 1 / 2, not 2 / 3. With the empty
  // tenant profile, contact/theme/published are false, so the score is
  // 2 of 5 = 40%.
  it("counts published items only — drafts do not score as added", async () => {
    api.get.mockImplementation((url) =>
      url.includes("/categories/")
        ? Promise.resolve({ data: [
            { slug: "starters", name: "Starters", is_published: true },
            { slug: "secret", name: "Secret", is_published: false },
          ] })
        : url.includes("/dishes/")
          ? Promise.resolve({ data: [
              { slug: "soup", name: "Soup", is_published: true, is_available: true },
              { slug: "salad", name: "Salad", is_published: true, is_available: true },
              { slug: "draft", name: "Draft", is_published: false, is_available: true },
            ] })
          : Promise.resolve({ data: [] }),
    );

    wrapper = mountReadiness();
    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const loaded = wrapper.emitted("loaded");
    expect(loaded).toBeTruthy();
    expect(loaded[0][0].categoriesCount).toBe(1);
    expect(loaded[0][0].dishesCount).toBe(2);
    expect(wrapper.emitted("error")).toBeFalsy();
    expect(wrapper.text()).toContain("40%");
  });

  // B-38 (error state): fetch failure → NO "loaded" with zeros, an "error"
  // emit instead, and an error + Retry UI (not a false 0% checklist).
  it("emits error (not zero counts) and shows Retry when the fetch fails", async () => {
    api.get.mockImplementation(() => Promise.reject(new Error("network down")));

    wrapper = mountReadiness();
    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.emitted("loaded")).toBeFalsy();
    expect(wrapper.emitted("error")).toBeTruthy();
    expect(wrapper.text()).toContain("ownerHome.readinessLoadError");
    expect(wrapper.text()).not.toContain("0%");
    expect(retryButton(wrapper)).not.toBeUndefined();

    // Retry with the network healthy again → the checklist loads.
    api.get.mockImplementation((url) =>
      url.includes("/categories/")
        ? Promise.resolve({ data: [{ slug: "starters", name: "Starters", is_published: true }] })
        : url.includes("/dishes/")
          ? Promise.resolve({ data: [{ slug: "soup", name: "Soup", is_published: true, is_available: true }] })
          : Promise.resolve({ data: [] }),
    );
    await retryButton(wrapper).trigger("click");
    await flushPromises();
    await flushPromises();

    expect(wrapper.emitted("loaded")).toBeTruthy();
    expect(wrapper.emitted("loaded")[0][0].categoriesCount).toBe(1);
    expect(wrapper.text()).not.toContain("ownerHome.readinessLoadError");
    expect(wrapper.text()).toContain("40%");
  });

  // Draft-only menu → counts are 0 / 0 and the score is genuinely 0% (this is
  // a real empty menu, not a fetch failure — no error UI).
  it("scores a drafts-only menu at 0% without an error state", async () => {
    api.get.mockImplementation((url) =>
      url.includes("/categories/")
        ? Promise.resolve({ data: [{ slug: "secret", name: "Secret", is_published: false }] })
        : url.includes("/dishes/")
          ? Promise.resolve({ data: [{ slug: "draft", name: "Draft", is_published: false, is_available: true }] })
          : Promise.resolve({ data: [] }),
    );

    wrapper = mountReadiness();
    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const loaded = wrapper.emitted("loaded");
    expect(loaded).toBeTruthy();
    expect(loaded[0][0].categoriesCount).toBe(0);
    expect(loaded[0][0].dishesCount).toBe(0);
    expect(wrapper.emitted("error")).toBeFalsy();
    expect(wrapper.text()).toContain("0%");
    expect(wrapper.text()).not.toContain("ownerHome.readinessLoadError");
  });
});
