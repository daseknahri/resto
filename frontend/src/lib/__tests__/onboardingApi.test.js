/**
 * CRITICAL regression: profileApi.save() does a PUT (full profile update), so a
 * PARTIAL payload must stay partial — sanitizeProfilePayload must NOT inject empty
 * "" / {} values for keys the caller didn't send. It previously did, so a partial
 * save (OwnerProfile.saveOrderHandling / saveSchedule, StepPublish.saveDirectory —
 * each sending only 2-7 fields) wiped the logo, hero, social/map links, all
 * translations, and the weekly schedule on the live storefront.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../api", () => ({
  default: {
    put: vi.fn(() => Promise.resolve({ data: {} })),
    get: vi.fn(() => Promise.resolve({ data: {} })),
  },
  extractApiErrorMessage: (err, fallback = "") => fallback,
}));
vi.mock("../slug", () => ({ slugify: (s) => String(s || "") }));
vi.mock("../staleCache", () => ({ bustCache: vi.fn() }));
vi.mock("../../i18n/translate", () => ({ translate: (k) => k }));

import api from "../api";
import { profileApi } from "../onboardingApi";

const WIPEABLE = [
  "logo_url", "hero_url",
  "facebook_url", "instagram_url", "tiktok_url", "google_maps_url", "reservation_url",
  "tagline_i18n", "description_i18n", "address_i18n", "business_hours_i18n",
  "business_hours_schedule",
];

describe("profileApi.save — partial saves must not wipe absent fields", () => {
  beforeEach(() => {
    api.put.mockClear();
  });

  it("does NOT inject empty logo/hero/social/i18n/schedule for a partial (order-handling) save", async () => {
    await profileApi.save({ auto_accept_orders: true, default_prep_minutes: 20 });
    const sent = api.put.mock.calls[0][1];

    // The fields the caller sent survive.
    expect(sent.auto_accept_orders).toBe(true);
    expect(sent.default_prep_minutes).toBe(20);

    // Absent keys must NOT be present at all — injecting "" / {} + PUT would erase them.
    for (const key of WIPEABLE) {
      expect(key in sent, `${key} must not be injected into a partial save`).toBe(false);
    }
  });

  it("does NOT inject brand/hours fields for a partial (directory opt-in) save", async () => {
    await profileApi.save({
      directory_opt_in: true, cuisine_type: "cafe", city: "Casablanca",
      lat: 33.5, lng: -7.6, price_tier: 2, tags: ["wifi"],
    });
    const sent = api.put.mock.calls[0][1];
    expect(sent.directory_opt_in).toBe(true);
    expect(sent.city).toBe("Casablanca");
    for (const key of WIPEABLE) {
      expect(key in sent, `${key} must not be injected into a partial save`).toBe(false);
    }
  });

  it("still normalizes keys the caller DID send (full-profile save path is unchanged)", async () => {
    await profileApi.save({
      logo_url: "example.com/logo.png",
      tagline_i18n: { EN: " Hello " },
      business_hours_schedule: null,
    });
    const sent = api.put.mock.calls[0][1];
    expect(sent.logo_url).toBe("https://example.com/logo.png"); // normalizeOptionalUrl adds scheme
    expect(sent.tagline_i18n).toEqual({ en: "Hello" });          // normalizeI18nMap lowercases + trims
    expect(sent.business_hours_schedule).toEqual({});            // present but invalid → {}
  });
});
