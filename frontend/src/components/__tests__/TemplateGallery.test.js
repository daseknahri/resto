/**
 * Unit tests for TemplateGallery — shared starter-template picker.
 *
 * Verifies template card rendering after mount fetch, business-type filter chip
 * behaviour, template application (api.post call + "applied" emit), and the
 * with_sample_content toggle.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

// Deterministic i18n: keys pass through with optional param suffix.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? k + JSON.stringify(p) : k) }),
}));

// api mock — get returns two templates; post returns an apply result.
vi.mock("../../lib/api", () => {
  const get = vi.fn().mockResolvedValue({
    data: {
      templates: [
        {
          key: "cafe",
          business_type: "cafe",
          theme: { primary_color: "#111111", secondary_color: "#222222" },
          categories: ["A", "B"],
          dish_count: 5,
        },
        {
          key: "burger",
          business_type: "restaurant",
          theme: { primary_color: "#333333", secondary_color: "#444444" },
          categories: ["C"],
          dish_count: 3,
        },
      ],
    },
  });
  const post = vi.fn().mockResolvedValue({
    data: { applied: "burger", created_dishes: 3, created_categories: 1 },
  });
  return { default: { get, post } };
});

// Toast and tenant stores.
const showMock = vi.fn();
const fetchMetaMock = vi.fn().mockResolvedValue();

vi.mock("../../stores/toast", () => ({
  useToastStore: () => ({ show: showMock }),
}));

vi.mock("../../stores/tenant", () => ({
  useTenantStore: () => ({ fetchMeta: fetchMetaMock }),
}));

import api from "../../lib/api";
import { __resetTemplateCatalog } from "../../lib/templateCatalog";
import TemplateGallery from "../TemplateGallery.vue";

/** Helper: mount with AppIcon stubbed out. */
function mountGallery(props = {}) {
  return mount(TemplateGallery, {
    props,
    global: {
      stubs: { AppIcon: true },
    },
  });
}

describe("TemplateGallery", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // The catalog caches the template list at module scope (one fetch per page
    // load in the app) — reset it so every test exercises the fetch path.
    __resetTemplateCatalog();
    // Re-attach resolved values cleared by clearAllMocks.
    api.get.mockResolvedValue({
      data: {
        templates: [
          {
            key: "cafe",
            business_type: "cafe",
            theme: { primary_color: "#111111", secondary_color: "#222222" },
            categories: ["A", "B"],
            dish_count: 5,
          },
          {
            key: "burger",
            business_type: "restaurant",
            theme: { primary_color: "#333333", secondary_color: "#444444" },
            categories: ["C"],
            dish_count: 3,
          },
        ],
      },
    });
    api.post.mockResolvedValue({
      data: { applied: "burger", created_dishes: 3, created_categories: 1 },
    });
    fetchMetaMock.mockResolvedValue();
  });

  it("renders one card per template after the mount fetch", async () => {
    const wrapper = mountGallery();
    await flushPromises();

    const cardButtons = wrapper
      .findAll("button")
      .filter((b) => b.text().includes("ownerTemplates.kinds."));

    expect(cardButtons).toHaveLength(2);
    expect(cardButtons.some((b) => b.text().includes("ownerTemplates.kinds.cafe"))).toBe(true);
    expect(cardButtons.some((b) => b.text().includes("ownerTemplates.kinds.burger"))).toBe(true);
  });

  it("renders business-type filter chips and hides cards on filter click", async () => {
    const wrapper = mountGallery();
    await flushPromises();

    // Two distinct business types → two type chips (plus the "All" chip).
    const chips = wrapper
      .findAll("button")
      .filter((b) =>
        b.text().includes("stepPublish.businessType"),
      );
    expect(chips).toHaveLength(2);

    // Click the restaurant chip.
    const restaurantChip = chips.find((b) =>
      b.text().includes("stepPublish.businessTypeRestaurant"),
    );
    expect(restaurantChip).toBeDefined();
    await restaurantChip.trigger("click");

    // cafe card must no longer be visible.
    const cardTexts = wrapper
      .findAll("button")
      .filter((b) => b.text().includes("ownerTemplates.kinds."))
      .map((b) => b.text());

    expect(cardTexts.some((t) => t.includes("ownerTemplates.kinds.cafe"))).toBe(false);
    expect(cardTexts.some((t) => t.includes("ownerTemplates.kinds.burger"))).toBe(true);
  });

  it("calls api.post and emits 'applied' with response data when a card is clicked", async () => {
    const wrapper = mountGallery();
    await flushPromises();

    const burgerCard = wrapper
      .findAll("button")
      .find((b) => b.text().includes("ownerTemplates.kinds.burger"));
    expect(burgerCard).toBeDefined();

    await burgerCard.trigger("click");
    await flushPromises();

    expect(api.post).toHaveBeenCalledWith("/owner/apply-template/", {
      template: "burger",
      with_sample_content: true,
    });

    expect(wrapper.emitted("applied")).toHaveLength(1);
    expect(wrapper.emitted("applied")[0][0]).toEqual({
      applied: "burger",
      created_dishes: 3,
      created_categories: 1,
    });
  });

  it("posts with_sample_content: false when the sample toggle is unchecked", async () => {
    const wrapper = mountGallery({ showSampleToggle: true, initialWithSample: true });
    await flushPromises();

    // Uncheck the sample-content checkbox.
    const checkbox = wrapper.find("input[type='checkbox']");
    expect(checkbox.exists()).toBe(true);
    await checkbox.setValue(false);

    // Click the burger card.
    const burgerCard = wrapper
      .findAll("button")
      .find((b) => b.text().includes("ownerTemplates.kinds.burger"));
    await burgerCard.trigger("click");
    await flushPromises();

    expect(api.post).toHaveBeenCalledWith("/owner/apply-template/", {
      template: "burger",
      with_sample_content: false,
    });
  });
});
