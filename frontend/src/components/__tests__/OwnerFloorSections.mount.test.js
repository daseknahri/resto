/**
 * Mount test for OwnerFloorSections.vue — G4b-E (B-39).
 *
 * WHY: fetchSections / fetchStaff failures used to be swallowed as "non-fatal"
 * with no UI, so the section manager and the staff-assignment dropdown rendered
 * empty with no indication the load had failed. Mounting the REAL component
 * exercises the load → error-banner → Retry path end to end.
 *
 * Pattern-faithful to components/__tests__/OwnerDashboardDishPanel.mount.test.js:
 *   - mount (child AppIcon stubbed) + real pinia (toast store runs for real) +
 *     mocked lib/api, URL-routed per test via mockImplementation
 *   - useI18n mocked (key verbatim → assertions read the raw key).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import api from "../../lib/api";
import OwnerFloorSections from "../OwnerFloorSections.vue";

const sectionsPayload = {
  sections: [
    {
      id: 1,
      name: "Terrace",
      color: "#f59e0b",
      tables: [{ id: 1, label: "T1" }],
      servers: [{ id: 7, name: "Amine", email: "amine@example.test" }],
    },
  ],
};
const staffPayload = { staff: [{ id: 7, name: "Amine", email: "amine@example.test" }] };

const mountSections = () =>
  mount(OwnerFloorSections, {
    props: { tables: [] },
    global: {
      stubs: {
        AppIcon: { template: "<span />" },
      },
    },
  });

const retryButton = (wrapper) =>
  wrapper.findAll("button").find((b) => b.text().includes("common.retry"));

describe("OwnerFloorSections — G4b-E (B-39 load-failure UI + retry)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    api.get.mockImplementation(() => Promise.resolve({ data: {} }));
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // B-39: sections load fails (staff loads fine) → an error banner + Retry
  // render, and the "no sections yet" empty state does NOT render (it would
  // misread as "nothing configured"). Retry with a healthy backend → the
  // section list renders and the banner clears.
  it("shows an error + Retry (not the empty state) when the sections load fails", async () => {
    api.get.mockImplementation((url) =>
      url.includes("/owner/sections/")
        ? Promise.reject(new Error("sections down"))
        : url.includes("/owner/staff/")
          ? Promise.resolve({ data: staffPayload })
          : Promise.resolve({ data: {} }),
    );

    wrapper = mountSections();
    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerSections.loadError");
    expect(retryButton(wrapper)).not.toBeUndefined();
    expect(wrapper.text()).not.toContain("ownerSections.emptyTitle");
    expect(wrapper.text()).not.toContain("Terrace");

    api.get.mockImplementation((url) =>
      url.includes("/owner/sections/")
        ? Promise.resolve({ data: sectionsPayload })
        : url.includes("/owner/staff/")
          ? Promise.resolve({ data: staffPayload })
          : Promise.resolve({ data: {} }),
    );
    await retryButton(wrapper).trigger("click");
    await flushPromises();
    await flushPromises();

    expect(wrapper.text()).not.toContain("ownerSections.loadError");
    expect(wrapper.text()).toContain("Terrace");
  });

  // B-39: staff load fails while sections load fine → the sections still
  // render, but the error banner shows (the waiter-assignment checkboxes
  // would otherwise render empty with a misleading "no staff yet" note).
  it("shows the error banner when only the staff load fails", async () => {
    api.get.mockImplementation((url) =>
      url.includes("/owner/sections/")
        ? Promise.resolve({ data: sectionsPayload })
        : url.includes("/owner/staff/")
          ? Promise.reject(new Error("staff down"))
          : Promise.resolve({ data: {} }),
    );

    wrapper = mountSections();
    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("Terrace");
    expect(wrapper.text()).toContain("ownerSections.loadError");
    expect(retryButton(wrapper)).not.toBeUndefined();
  });

  // Regression guard: healthy loads → sections render, no error banner.
  it("renders sections with no error banner when both loads succeed", async () => {
    api.get.mockImplementation((url) =>
      url.includes("/owner/sections/")
        ? Promise.resolve({ data: sectionsPayload })
        : url.includes("/owner/staff/")
          ? Promise.resolve({ data: staffPayload })
          : Promise.resolve({ data: {} }),
    );

    wrapper = mountSections();
    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("Terrace");
    expect(wrapper.text()).not.toContain("ownerSections.loadError");
    expect(retryButton(wrapper)).toBeUndefined();
  });
});
