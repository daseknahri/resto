/**
 * Mount tests for onboarding/StepTheme.vue — Run 8 G4b cluster G
 * (A3-10 theme part, A3-28, A3-29).
 *
 * Harness pattern follows tests/onboarding/Wizard.mount.test.js (S1-F block):
 * real pinia stores, mocked useI18n (identity-t) / templateCatalog /
 * onboardingApi, mount (not shallowMount) because every gap lives in this
 * component's own template/script. TemplatePickerModal is stubbed; the
 * template-applied path is driven through the exposed onTemplateApplied()
 * (defineExpose), which is also how the picker invokes it in production.
 *
 * Mock notes:
 * - profileApi.get has NO default implementation: each test seeds it with
 *   mockResolvedValue before mount (clearAllMocks does not remove an
 *   implementation set by a previous test, so every test sets its own).
 * - A3-29 drives the queue through the Remove-logo button (clearLogo), not
 *   through a file upload, so no File/ DataTransfer fixture is needed.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { nextTick } from "vue";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

vi.mock("../../lib/api", () => ({
  extractApiErrorMessage: (err, fallback = "") => fallback,
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

vi.mock("../../lib/onboardingApi", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    profileApi: {
      get: vi.fn(),
      save: vi.fn(() => Promise.resolve({})),
    },
    uploadApi: {
      image: vi.fn(() => Promise.resolve({ url: "" })),
      removeImage: vi.fn(() => Promise.resolve({})),
    },
  };
});

vi.mock("../../lib/templateCatalog", () => ({
  fetchTemplateSummaries: () => Promise.resolve([]),
}));

import StepTheme from "../StepTheme.vue";
import { profileApi, uploadApi } from "../../lib/onboardingApi";
import { useTenantStore } from "../../stores/tenant";
import { useThemeStore } from "../../stores/theme";

const THEME_PROFILE = {
  primary_color: "#123456",
  secondary_color: "#654321",
  logo_url: "",
  hero_url: "",
};

const findSaveButton = (wrapper) =>
  wrapper.findAll("button").find((b) => b.text().includes("common.saveAndNext"));

describe("StepTheme — G4b-G (A3-10, A3-28, A3-29)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    useTenantStore().$patch({ meta: { slug: "demo", profile: { is_menu_published: false } } });
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  const mountTheme = async (profile = THEME_PROFILE) => {
    profileApi.get.mockResolvedValue({ ...profile });
    wrapper = mount(StepTheme, {
      props: { standalone: false },
      global: { stubs: { TemplatePickerModal: true } },
    });
    await flushPromises();
    await nextTick();
    expect(findSaveButton(wrapper).attributes("disabled")).toBeUndefined();
    return wrapper;
  };

  const primaryColorInput = () => wrapper.findAll('input[type="color"]')[0];

  // ── A3-10: aria-describedby is conditional on the error being present ─────
  it("A3-10: primary colour has no aria-describedby until a colour error exists, then it points at the live error", async () => {
    await mountTheme();
    expect(primaryColorInput().attributes("aria-describedby")).toBeUndefined();

    profileApi.save.mockRejectedValueOnce({
      fieldErrors: { primary_color: "bad colour" },
      message: "stepTheme.toastSaveFailed",
    });
    await findSaveButton(wrapper).trigger("click");
    await flushPromises();
    await nextTick();

    expect(profileApi.save).toHaveBeenCalledTimes(1);
    expect(primaryColorInput().attributes("aria-describedby")).toBe("step-theme-primary-error");
    expect(wrapper.find("#step-theme-primary-error").text()).toBe("bad colour");
  });

  // ── A3-28: template apply must not overwrite unsaved edits ───────────────
  it("A3-28: applying a template with unsaved colour edits keeps the edits and does not reload", async () => {
    await mountTheme();
    await primaryColorInput().setValue("#111111");
    await nextTick();

    await wrapper.vm.onTemplateApplied();
    await flushPromises();

    // No second profile GET: load() was skipped while the form is dirty.
    expect(profileApi.get).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("stepTheme.templateAppliedKeptEdits");
    expect(primaryColorInput().element.value).toBe("#111111");
  });

  it("A3-28: applying a template with no unsaved edits reloads the theme from the server", async () => {
    await mountTheme();
    await wrapper.vm.onTemplateApplied();
    await flushPromises();

    expect(profileApi.get).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).not.toContain("stepTheme.templateAppliedKeptEdits");
    expect(useThemeStore().primary).toBe("#123456");
  });

  it("A3-28: saving after an edit refreshes the dirty baseline, so a later template apply reloads", async () => {
    await mountTheme();
    await primaryColorInput().setValue("#111111");
    await nextTick();
    await findSaveButton(wrapper).trigger("click");
    await flushPromises();
    await nextTick();
    expect(profileApi.save).toHaveBeenCalledTimes(1);

    await wrapper.vm.onTemplateApplied();
    await flushPromises();

    expect(profileApi.get).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).not.toContain("stepTheme.templateAppliedKeptEdits");
  });

  // ── A3-29: pending cleanup flushes on unmount ─────────────────────────────
  it("A3-29: removing the logo then leaving without saving deletes the orphaned file on unmount", async () => {
    await mountTheme({ ...THEME_PROFILE, logo_url: "https://example.com/uploads/old-logo.png" });
    const removeBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("stepTheme.removeLogo"));
    expect(removeBtn.exists()).toBe(true);
    await removeBtn.trigger("click");
    await flushPromises();
    // Still queued, not yet deleted: the save path has not run.
    expect(uploadApi.removeImage).not.toHaveBeenCalled();

    wrapper.unmount();
    wrapper = undefined;
    await flushPromises();

    expect(uploadApi.removeImage).toHaveBeenCalledTimes(1);
    expect(uploadApi.removeImage).toHaveBeenCalledWith("https://example.com/uploads/old-logo.png");
  });

  it("A3-29: unmounting with nothing queued deletes nothing", async () => {
    await mountTheme();
    wrapper.unmount();
    wrapper = undefined;
    await flushPromises();

    expect(uploadApi.removeImage).not.toHaveBeenCalled();
  });
});
