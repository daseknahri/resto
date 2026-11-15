/**
 * Mount tests for onboarding/StepBrand.vue — Run 8 G4b cluster G
 * (A3-10 brand part, A3-11, A3-40, A3-41).
 *
 * Harness pattern follows tests/onboarding/Wizard.mount.test.js (S1-F block):
 * real pinia stores, mocked useI18n (identity-t, so keys are assertable by
 * substring) / useTranslate / onboardingApi, mount (not shallowMount) because
 * every gap lives in this component's own template/script.
 *
 * Mock notes:
 * - useI18n returns localeOptions here (S1-F's mock did not, and the language
 *   <select> then renders no options) — A3-40 drives that select.
 * - lib/businessHours and i18n/config are REAL (S1-F mounted StepBrand with
 *   them unmocked); only the network-facing modules are stubbed.
 * - profileApi.get has NO default implementation: each test seeds it with
 *   mockResolvedValue before mount (clearAllMocks does not remove an
 *   implementation set by a previous test, so every test sets its own).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { nextTick } from "vue";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    localeOptions: [
      { code: "en", label: "English" },
      { code: "fr", label: "French" },
      { code: "ar", label: "Arabic" },
    ],
  }),
}));

vi.mock("../../composables/useTranslate", () => ({
  useTranslate: () => ({
    translating: {},
    translateError: { value: "" },
    translateField: vi.fn(() => Promise.resolve(null)),
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

import StepBrand from "../StepBrand.vue";
import { profileApi } from "../../lib/onboardingApi";
import { useTenantStore } from "../../stores/tenant";

const BRAND_PROFILE = {
  tagline: "Our place",
  tagline_i18n: {},
  description: "",
  description_i18n: {},
  address: "",
  address_i18n: {},
  business_hours_schedule: {
    mon: { enabled: true, open: "18:00", close: "02:00" },
  },
  language: "en",
  timezone: "",
  lat: null,
  lng: null,
};

const findSaveButton = (wrapper) =>
  wrapper.findAll("button").find((b) => b.text().includes("common.saveAndNext"));

// The lat/lng inputs live inside <label>s whose text is the mocked t() key.
const coordInput = (wrapper, key) =>
  wrapper
    .findAll("label")
    .find((l) => l.text().includes(key))
    .find("input");

const languageSelect = (wrapper) =>
  wrapper
    .findAll("label")
    .find((l) => l.text().includes("stepBrand.defaultLanguage"))
    .find("select");

describe("StepBrand — G4b-G (A3-10, A3-11, A3-40, A3-41)", () => {
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

  const mountBrand = async (profile = BRAND_PROFILE) => {
    profileApi.get.mockResolvedValue({ ...profile });
    wrapper = mount(StepBrand, { props: { standalone: false } });
    await flushPromises();
    await nextTick();
    expect(findSaveButton(wrapper).attributes("disabled")).toBeUndefined();
    return wrapper;
  };

  const clickSave = async () => {
    await findSaveButton(wrapper).trigger("click");
    await flushPromises();
    await nextTick();
  };

  // ── A3-10: aria-describedby is conditional on the error being present ─────
  it("A3-10: phone has no aria-describedby until a phone error exists, then it points at the live error", async () => {
    await mountBrand();
    const phoneInput = wrapper
      .findAll("label")
      .find((l) => l.text().includes("stepBrand.phone"))
      .find("input");
    expect(phoneInput.attributes("aria-describedby")).toBeUndefined();

    profileApi.save.mockRejectedValueOnce({
      fieldErrors: { phone: "stepBrand.phoneBad" },
      message: "stepBrand.toastFailed",
    });
    await clickSave();

    expect(profileApi.save).toHaveBeenCalledTimes(1);
    expect(phoneInput.attributes("aria-describedby")).toBe("step-brand-phone-error");
    expect(wrapper.find("#step-brand-phone-error").text()).toBe("stepBrand.phoneBad");
  });

  // ── A3-11: lat/lng validation + inline error ─────────────────────────────
  it("A3-11: latitude 200 is rejected with an inline error and never saves", async () => {
    await mountBrand();
    await coordInput(wrapper, "stepBrand.latitude").setValue("200");
    await nextTick();
    await clickSave();

    expect(profileApi.save).not.toHaveBeenCalled();
    expect(wrapper.find("#step-brand-lat-error").text()).toBe("stepBrand.latRange");
    expect(coordInput(wrapper, "stepBrand.latitude").attributes("aria-describedby")).toBe(
      "step-brand-lat-error"
    );
  });

  it("A3-11: longitude 200 is rejected with an inline error and never saves", async () => {
    await mountBrand();
    await coordInput(wrapper, "stepBrand.longitude").setValue("200");
    await nextTick();
    await clickSave();

    expect(profileApi.save).not.toHaveBeenCalled();
    expect(wrapper.find("#step-brand-lng-error").text()).toBe("stepBrand.lngRange");
  });

  it("A3-11: coordinates 0, 0 are rejected (the server would silently null them)", async () => {
    await mountBrand();
    await coordInput(wrapper, "stepBrand.latitude").setValue("0");
    await coordInput(wrapper, "stepBrand.longitude").setValue("0");
    await nextTick();
    await clickSave();

    expect(profileApi.save).not.toHaveBeenCalled();
    expect(wrapper.find("#step-brand-lat-error").text()).toBe("stepBrand.latLngZero");
  });

  it("A3-11: a lone latitude with no longitude is rejected", async () => {
    await mountBrand();
    await coordInput(wrapper, "stepBrand.latitude").setValue("33.5");
    await nextTick();
    await clickSave();

    expect(profileApi.save).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("stepBrand.latLngPair");
  });

  it("A3-11: valid coordinates save with the typed values", async () => {
    await mountBrand();
    await coordInput(wrapper, "stepBrand.latitude").setValue("33.5731");
    await coordInput(wrapper, "stepBrand.longitude").setValue("-7.5898");
    await nextTick();
    await clickSave();

    expect(profileApi.save).toHaveBeenCalledTimes(1);
    const payload = profileApi.save.mock.calls[0][0];
    expect(payload.lat).toBeCloseTo(33.5731);
    expect(payload.lng).toBeCloseTo(-7.5898);
  });

  // ── A3-41: free-text IANA timezone ────────────────────────────────────────
  it("A3-41: an invalid timezone is rejected with an inline error and never saves", async () => {
    await mountBrand();
    const tzInput = wrapper.find('input[list="step-brand-timezone-list"]');
    expect(tzInput.exists()).toBe(true);
    await tzInput.setValue("Mars/Olympus");
    await nextTick();
    await clickSave();

    expect(profileApi.save).not.toHaveBeenCalled();
    expect(wrapper.find("#step-brand-timezone-error").text()).toBe("stepBrand.timezoneInvalid");
  });

  it("A3-41: a valid IANA zone outside the curated 10 saves, and the curated zones stay as suggestions", async () => {
    await mountBrand();
    const options = wrapper.findAll("#step-brand-timezone-list option");
    expect(options.some((o) => o.attributes("value") === "Africa/Casablanca")).toBe(true);

    const tzInput = wrapper.find('input[list="step-brand-timezone-list"]');
    await tzInput.setValue("America/Toronto");
    await nextTick();
    await clickSave();

    expect(profileApi.save).toHaveBeenCalledTimes(1);
    expect(profileApi.save.mock.calls[0][0].timezone).toBe("America/Toronto");
  });

  // ── A3-40: language switch migrates the base text ────────────────────────
  it("A3-40: switching en -> fr moves the old base text into the en map entry", async () => {
    await mountBrand({
      ...BRAND_PROFILE,
      tagline: "Our place",
      description: "Desc",
    });
    await languageSelect(wrapper).setValue("fr");
    await nextTick();

    expect(wrapper.text()).toContain("stepBrand.languageChangedMoved");
    await clickSave();

    expect(profileApi.save).toHaveBeenCalledTimes(1);
    const payload = profileApi.save.mock.calls[0][0];
    expect(payload.language).toBe("fr");
    expect(payload.tagline).toBe("");
    expect(payload.tagline_i18n).toEqual({ en: "Our place" });
    expect(payload.description).toBe("");
    expect(payload.description_i18n).toEqual({ en: "Desc" });
  });

  it("A3-40: switching to a locale that already has a translation promotes it to the base", async () => {
    await mountBrand({
      ...BRAND_PROFILE,
      tagline: "Hello",
      tagline_i18n: { fr: "Bonjour" },
    });
    await languageSelect(wrapper).setValue("fr");
    await nextTick();
    await clickSave();

    expect(profileApi.save).toHaveBeenCalledTimes(1);
    const payload = profileApi.save.mock.calls[0][0];
    expect(payload.tagline).toBe("Bonjour");
    expect(payload.tagline_i18n).toEqual({ en: "Hello" });
  });
});
