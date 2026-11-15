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

  it("force-refetches meta after applying, so a still-fresh cached theme/vertical is replaced", async () => {
    const wrapper = mountGallery();
    await flushPromises();

    const burgerCard = wrapper
      .findAll("button")
      .find((b) => b.text().includes("ownerTemplates.kinds.burger"));
    await burgerCard.trigger("click");
    await flushPromises();

    expect(fetchMetaMock).toHaveBeenCalledTimes(1);
    expect(fetchMetaMock).toHaveBeenCalledWith({ force: true });
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
// ── Run 8 G4b-K2 (A3-35, A3-36) — appended 2026-11-15 ──────────────────────
// The 5 base tests above are untouched; everything below this line is new.
// 5 tests: load-failure empty-state + retry (1), apply confirm cancel /
// proceed (2), apply failure translated (1), A3-35 kind-key passthrough (1).
//
// Mock note — the hoisted useConfirmModal mock below applies file-wide: the
// base tests never mocked it, and the real composable's confirm() returns a
// promise that only settles via the modal UI, so without this mock every base
// card-click test would hang at the new confirm step. The mock resolves true
// by default, preserving all 5 base tests; the cancel path flips it per test.
const galleryConfirmMock = vi.hoisted(() => vi.fn(() => Promise.resolve(true)));
vi.mock("../../composables/useConfirmModal", () => ({
  useConfirmModal: () => ({ confirm: galleryConfirmMock }),
}));

describe("TemplateGallery — G4b-K2 A3-36 (load failure, apply confirm)", () => {
  const TEMPLATES_PAYLOAD = {
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
  };

  beforeEach(() => {
    vi.clearAllMocks();
    __resetTemplateCatalog();
    api.get.mockResolvedValue({ data: TEMPLATES_PAYLOAD });
    api.post.mockResolvedValue({
      data: { applied: "burger", created_dishes: 3, created_categories: 1 },
    });
    fetchMetaMock.mockResolvedValue();
  });

  const burgerCard = (wrapper) =>
    wrapper.findAll("button").find((b) => b.text().includes("ownerTemplates.kinds.burger"));

  it("load failure shows an inline message with Retry instead of a silently empty grid", async () => {
    api.get.mockRejectedValueOnce(new Error("offline"));
    const wrapper = mountGallery();
    await flushPromises();

    expect(wrapper.text()).toContain("ownerTemplates.loadFailed");
    const retryBtn = wrapper.findAll("button").find((b) => b.text().includes("common.retry"));
    expect(retryBtn.exists()).toBe(true);
    expect(wrapper.findAll("button").filter((b) => b.text().includes("ownerTemplates.kinds."))).toHaveLength(0);

    // Retry re-fetches and the cards render.
    __resetTemplateCatalog();
    await retryBtn.trigger("click");
    await flushPromises();
    expect(wrapper.findAll("button").filter((b) => b.text().includes("ownerTemplates.kinds."))).toHaveLength(2);
  });

  it("asks for confirmation before applying, naming the template", async () => {
    const wrapper = mountGallery();
    await flushPromises();

    await burgerCard(wrapper).trigger("click");
    await flushPromises();

    expect(galleryConfirmMock).toHaveBeenCalledTimes(1);
    expect(galleryConfirmMock).toHaveBeenCalledWith(
      expect.objectContaining({ title: "ownerTemplates.applyConfirmTitle" }),
    );
    expect(api.post).toHaveBeenCalledWith("/owner/apply-template/", {
      template: "burger",
      with_sample_content: true,
    });
  });

  it("does not POST or emit when the apply confirm is declined", async () => {
    galleryConfirmMock.mockResolvedValueOnce(false);
    const wrapper = mountGallery();
    await flushPromises();

    await burgerCard(wrapper).trigger("click");
    await flushPromises();

    expect(api.post).not.toHaveBeenCalled();
    expect(wrapper.emitted("applied")).toBeUndefined();
  });

  it("apply failure shows the translated generic message, never the raw backend detail", async () => {
    api.post.mockRejectedValueOnce({ response: { data: { detail: "Template exploded" } } });
    const wrapper = mountGallery();
    await flushPromises();

    await burgerCard(wrapper).trigger("click");
    await flushPromises();

    expect(showMock).toHaveBeenCalledWith("ownerTemplates.applyFailed", "error");
    expect(showMock.mock.calls.flat().join(" ")).not.toContain("Template exploded");
  });

  it("A3-35: a backend-only kind renders through t() (key passthrough, no raw label)", async () => {
    __resetTemplateCatalog();
    api.get.mockResolvedValue({
      data: {
        templates: [
          {
            key: "patisserie_fine",
            business_type: "bakery",
            theme: { primary_color: "#111111", secondary_color: "#222222" },
            categories: ["X"],
            dish_count: 2,
          },
        ],
      },
    });
    const wrapper = mountGallery();
    await flushPromises();

    const cards = wrapper.findAll("button").filter((b) => b.text().includes("ownerTemplates.kinds."));
    expect(cards).toHaveLength(1);
    expect(cards[0].text()).toContain("ownerTemplates.kinds.patisserie_fine");
  });
});
