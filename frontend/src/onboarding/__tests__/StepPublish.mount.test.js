/**
 * Mount tests for onboarding/StepPublish.vue — Rostoy Run 8, Surface 1,
 * cluster G4b-K1 (gaps A3-12, A3-31, A3-32, A3-33, A3-45, A3-46).
 *
 * WHY: all six gaps are silent-failure / wrong-value paths in the publish
 * step — directory 400s swallowed, COD fields never re-synced after save,
 * euro price tiers on a MAD platform, auto-confirm 0 coerced to 24, a
 * "Published" button that stays clickable, and readiness checks that pass
 * for every tenant from birth. Each test drives the real component (mount,
 * not shallow) through the UI the owner actually touches.
 *
 * Pattern-faithful to onboarding/__tests__/Wizard.mount.test.js (S1-H block)
 * and StepDishes.mount.test.js:
 *   - mount (real template: readiness list, publish/save buttons, directory
 *     section, COD + auto-confirm inputs, price-tier buttons)
 *   - real pinia (tenant store seeded via $patch; fetchMeta stubbed so a
 *     save never touches the network; toast store runs for real)
 *   - useI18n / useVocabulary / vue-router mocked; lib/onboardingApi +
 *     lib/menuVisibility + lib/analytics mocked with hoisted spies
 *   - FE lessons: setValue on inputs (awaits a tick) before clicking a
 *     :disabled-bound button, never wrapper.vm.<ref> + immediate click
 *
 * Destination in repo: frontend/src/onboarding/__tests__/StepPublish.mount.test.js
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { nextTick } from "vue";

// StepPublish destructures EXACTLY { t, formatDateTime } from useI18n(). The
// mocked `t` echoes its key verbatim (param-less) or as `key({...})` (with
// params), so the component's own template keys are assertable by substring.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatDateTime: (v) => String(v || ""),
  }),
}));

// StepPublish reads isShop / groupPlural / itemPlural in the template (ref
// auto-unwrapping) and groupSingular / itemSingular in script — real refs,
// like the S1-H Wizard block, or groupPlural.toLowerCase() crashes at mount.
vi.mock("../../composables/useVocabulary", async () => {
  const { ref } = await import("vue");
  return {
    useVocabulary: () => ({
      catalog: {},
      groupSingular: ref("category"),
      itemSingular: ref("dish"),
      isShop: ref(false),
      groupPlural: ref("Categories"),
      itemPlural: ref("Dishes"),
    }),
  };
});

// StepPublish renders RouterLink (preview / launch / landing) and the
// ClosureDates child; both are stubbed so mount stays hermetic.
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("../../lib/analytics", () => ({ trackEvent: vi.fn() }));
vi.mock("../../lib/menuVisibility", () => ({
  countCustomerVisible: () => ({ categories: 2, dishes: 5 }),
}));

// Defensive: the real tenant/toast stores import lib/api; keep any slipped
// store action hermetic.
vi.mock("../../lib/api", () => ({
  extractApiErrorMessage: (err, fallback = "") => fallback,
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// lib/onboardingApi: hoisted spies, re-programmed per test via profileData.
const profileGetMock = vi.hoisted(() => vi.fn());
const profileSaveMock = vi.hoisted(() => vi.fn());
vi.mock("../../lib/onboardingApi", () => ({
  profileApi: { get: profileGetMock, save: profileSaveMock },
  superCategoryApi: { list: vi.fn(() => Promise.resolve([])) },
  categoryApi: { list: vi.fn(() => Promise.resolve([])) },
  dishApi: { list: vi.fn(() => Promise.resolve([])) },
}));

import StepPublish from "../StepPublish.vue";
import { useTenantStore } from "../../stores/tenant";
import { useToastStore } from "../../stores/toast";

const profileData = (overrides = {}) => ({
  is_menu_published: false,
  published_at: null,
  tagline: "Great food, honest prices",
  phone: "+212600000000",
  whatsapp: "",
  logo_url: "",
  hero_url: "",
  primary_color: "#0F766E",
  secondary_color: "#F59E0B",
  is_open: true,
  cod_enabled: true,
  cod_min_paid_orders: 3,
  auto_confirm_reservations: true,
  auto_confirm_min_hours: 24,
  directory_opt_in: true,
  city: "Casablanca",
  lat: 33.5731,
  lng: -7.5898,
  price_tier: 2,
  tags: [],
  ...overrides,
});

describe("StepPublish — G4b-K1 (A3-12, A3-31, A3-32, A3-33, A3-45, A3-46)", () => {
  let wrapper;
  let profile;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    profile = profileData();
    profileGetMock.mockImplementation(() => Promise.resolve({ ...profile }));
    // saveProfile re-GETs then PUTs; the save echoes the payload so the
    // component's re-sync reads back exactly what the server stored.
    profileSaveMock.mockImplementation((payload) => Promise.resolve({ ...payload }));
    const tenant = useTenantStore();
    tenant.$patch({ meta: { slug: "demo", profile: { is_menu_published: false } } });
    tenant.fetchMeta = vi.fn(() => Promise.resolve());
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  const mountPublish = async () => {
    wrapper = mount(StepPublish, {
      props: { standalone: false },
      global: {
        stubs: {
          RouterLink: { template: "<slot />" },
          ClosureDates: true,
        },
      },
    });
    await flushPromises();
    await flushPromises();
    await nextTick();
    return wrapper;
  };

  const readinessItems = () =>
    wrapper.findAll("li.ui-readiness-item").map((li) => li.text());
  const publishButton = () =>
    wrapper
      .findAll("button")
      .find((b) => b.text().includes("stepPublish.publishMenu") || b.text().includes("stepPublish.republishMenu"));
  const saveStatusButton = () =>
    wrapper.findAll("button").find((b) => b.text().includes("stepPublish.saveStatus"));
  const directorySaveButton = () =>
    wrapper.findAll("button").find((b) => b.text().trim() === "common.save");

  // ── A3-46 — brand needs tagline AND contact; theme needs logo/hero ──────
  it("A3-46: tagline without any contact leaves the brand check missing and Publish disabled", async () => {
    profile = profileData({ phone: "", whatsapp: "" });
    await mountPublish();
    const items = readinessItems();
    expect(items[0]).toContain("stepPublish.missing");
    expect(wrapper.text()).toContain("stepPublish.publishBrandRequirement");
    expect(publishButton().attributes("disabled")).toBeDefined();
  });

  it("A3-46: contact without a tagline also leaves the brand check missing", async () => {
    profile = profileData({ tagline: "" });
    await mountPublish();
    expect(readinessItems()[0]).toContain("stepPublish.missing");
    expect(publishButton().attributes("disabled")).toBeDefined();
  });

  it("A3-46: tagline AND contact passes the brand check and enables Publish", async () => {
    await mountPublish();
    expect(readinessItems()[0]).toContain("stepPublish.ok");
    expect(publishButton().attributes("disabled")).toBeUndefined();
  });

  it("A3-46: colours alone (model defaults) no longer pass the theme check", async () => {
    // Fixture carries the default #0F766E / #F59E0B colours and no logo/hero.
    await mountPublish();
    expect(readinessItems()[3]).toContain("stepPublish.missing");
  });

  it("A3-46: a logo passes the theme check", async () => {
    profile = profileData({ logo_url: "https://example.com/logo.png" });
    await mountPublish();
    expect(readinessItems()[3]).toContain("stepPublish.ok");
  });

  // ── A3-33 — auto_confirm_min_hours 0 is a real value, not 24 ─────────────
  it("A3-33: a stored 0 loads as 0 (always auto-confirm), not 24", async () => {
    profile = profileData({ auto_confirm_min_hours: 0 });
    await mountPublish();
    expect(wrapper.find("#sp-auto-confirm-min-hours").element.value).toBe("0");
  });

  it("A3-33: saving a typed 0 sends 0 to the server and keeps showing 0", async () => {
    profile = profileData({ auto_confirm_min_hours: 24 });
    await mountPublish();
    await wrapper.find("#sp-auto-confirm-min-hours").setValue(0);
    await saveStatusButton().trigger("click");
    await flushPromises();
    await nextTick();
    expect(profileSaveMock).toHaveBeenCalledTimes(1);
    expect(profileSaveMock.mock.calls[0][0].auto_confirm_min_hours).toBe(0);
    expect(wrapper.find("#sp-auto-confirm-min-hours").element.value).toBe("0");
  });

  it("A3-33: a blank auto-confirm value still falls back to 24 on save", async () => {
    await mountPublish();
    await wrapper.find("#sp-auto-confirm-min-hours").setValue("");
    await saveStatusButton().trigger("click");
    await flushPromises();
    expect(profileSaveMock.mock.calls[0][0].auto_confirm_min_hours).toBe(24);
  });

  // ── A3-31 — saveStatus re-syncs cod_* after save ─────────────────────────
  it("A3-31: a typed cod_min_paid_orders of 0 is stored as 3 and the UI shows 3 after save", async () => {
    await mountPublish();
    await wrapper.find("#sp-cod-min-orders").setValue(0);
    await saveStatusButton().trigger("click");
    await flushPromises();
    await nextTick();
    expect(profileSaveMock.mock.calls[0][0].cod_min_paid_orders).toBe(3);
    expect(wrapper.find("#sp-cod-min-orders").element.value).toBe("3");
  });

  it("A3-31: cod_enabled is re-synced from the saved profile", async () => {
    await mountPublish();
    profileSaveMock.mockResolvedValueOnce({
      ...profileData(),
      cod_enabled: false,
      cod_min_paid_orders: 5,
    });
    await saveStatusButton().trigger("click");
    await flushPromises();
    await nextTick();
    expect(wrapper.find("#sp-cod-enabled").element.checked).toBe(false);
  });

  // ── A3-32 — price tiers are locale-neutral, not euros ────────────────────
  it("A3-32: price-tier buttons show dots (● / ●● / ●●●), never €", async () => {
    await mountPublish();
    expect(wrapper.text()).toContain("●●●");
    expect(wrapper.text()).not.toContain("€");
  });

  // ── A3-12 — directory save surfaces server field errors ─────────────────
  it("A3-12: a directory 400 shows the server city error inline, not just the generic toast", async () => {
    profile = profileData({ city: "" });
    await mountPublish();
    const err = new Error("City is required.");
    err.fieldErrors = { city: "City is required." };
    profileSaveMock.mockRejectedValueOnce(err);
    await directorySaveButton().trigger("click");
    await flushPromises();
    await nextTick();
    expect(wrapper.text()).toContain("City is required.");
    expect(useToastStore().message).toContain("City is required.");
  });

  // ── A3-45 — republish label + no double profile GET on mount ─────────────
  it("A3-45: an already-published menu labels the button Re-publish", async () => {
    profile = profileData({ is_menu_published: true });
    await mountPublish();
    expect(publishButton().text()).toContain("stepPublish.republishMenu");
    expect(publishButton().text()).not.toContain("stepPublish.published");
    // Re-publish stays possible after edits — the button is not disabled.
    expect(publishButton().attributes("disabled")).toBeUndefined();
  });

  it("A3-45: mount issues exactly one profile GET (load hands its profile to refreshChecks)", async () => {
    await mountPublish();
    expect(profileGetMock).toHaveBeenCalledTimes(1);
  });

  it("A3-45: the Refresh checks button still fetches a fresh profile", async () => {
    await mountPublish();
    expect(profileGetMock).toHaveBeenCalledTimes(1);
    const refreshBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("stepPublish.refreshChecks"));
    await refreshBtn.trigger("click");
    await flushPromises();
    expect(profileGetMock).toHaveBeenCalledTimes(2);
  });
});
