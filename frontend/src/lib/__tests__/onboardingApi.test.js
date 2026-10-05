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
    post: vi.fn(() => Promise.resolve({ data: { id: 101, slug: "new" } })),
  },
  extractApiErrorMessage: (err, fallback = "") => fallback,
}));
vi.mock("../slug", () => ({ slugify: (s) => String(s || "") }));
vi.mock("../staleCache", () => ({ bustCache: vi.fn() }));
vi.mock("../../i18n/translate", () => ({ translate: (k) => k }));

import api from "../api";
import { categoryApi, dishApi, profileApi } from "../onboardingApi";

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

/**
 * CRITICAL: stock_qty is a LIVE counter (every order decrements it server-side) and
 * dishApi.upsert does a full PUT. The wizard editor holds the value it loaded, so echoing
 * it on every re-save would reset stock that orders depleted since. It may only be sent on
 * create, or when the owner changed it this session (differs from the known baseline).
 */
describe("dishApi.upsert — stock_qty only when the owner changed it (or on create)", () => {
  const existing = { id: 7, name: "Tagine", category: 3, price: 50, stock_qty: 10 };

  beforeEach(() => {
    api.put.mockClear();
    api.post.mockClear();
  });

  it("does NOT send stock_qty on a re-save where the owner left stock untouched", async () => {
    await dishApi.upsert(existing, { baselineStockQty: 10 });
    const sent = api.put.mock.calls[0][1];
    expect("stock_qty" in sent).toBe(false);
    expect("is_available" in sent).toBe(false);
    expect(sent.name).toBe("Tagine"); // the rest of the dish still saves
  });

  it("fails safe on an update with no known baseline — stock_qty is not sent", async () => {
    await dishApi.upsert(existing);
    expect("stock_qty" in api.put.mock.calls[0][1]).toBe(false);
  });

  it("sends stock_qty when the owner changed it, and re-enables a restocked dish", async () => {
    await dishApi.upsert({ ...existing, stock_qty: 25 }, { baselineStockQty: 10 });
    const sent = api.put.mock.calls[0][1];
    expect(sent.stock_qty).toBe(25);
    expect(sent.is_available).toBe(true);
  });

  it("sends a change to unlimited (null) without forcing availability", async () => {
    await dishApi.upsert({ ...existing, stock_qty: null }, { baselineStockQty: 10 });
    const sent = api.put.mock.calls[0][1];
    expect(sent.stock_qty).toBeNull();
    expect("is_available" in sent).toBe(false);
  });

  it("sends a change to 0 without marking the dish available", async () => {
    await dishApi.upsert({ ...existing, stock_qty: 0 }, { baselineStockQty: 10 });
    const sent = api.put.mock.calls[0][1];
    expect(sent.stock_qty).toBe(0);
    expect("is_available" in sent).toBe(false);
  });

  it("treats an unlimited baseline and an unlimited value as unchanged", async () => {
    await dishApi.upsert({ ...existing, stock_qty: null }, { baselineStockQty: null });
    expect("stock_qty" in api.put.mock.calls[0][1]).toBe(false);
  });

  it("always sends stock_qty when creating a dish", async () => {
    await dishApi.upsert({ name: "Harira", category: 3, price: 20, stock_qty: 5 });
    expect(api.put).not.toHaveBeenCalled();
    expect(api.post.mock.calls[0][1].stock_qty).toBe(5);
  });

  it("creates with unlimited stock (null) when the stock field is blank", async () => {
    await dishApi.upsert({ name: "Harira", category: 3, price: 20, stock_qty: "" });
    expect(api.post.mock.calls[0][1].stock_qty).toBeNull();
  });
});

describe("dishApi.upsert — availability_schedule is sent", () => {
  beforeEach(() => {
    api.put.mockClear();
  });

  it("sends the wizard's schedule (days lowercased, times trimmed)", async () => {
    await dishApi.upsert(
      { id: 7, name: "Brunch", category: 3, price: 50, availability_schedule: { days: ["SAT", "sun"], time_start: " 09:00", time_end: "12:00 " } },
      { baselineStockQty: null }
    );
    expect(api.put.mock.calls[0][1].availability_schedule).toEqual({
      days: ["sat", "sun"],
      time_start: "09:00",
      time_end: "12:00",
    });
  });

  it("sends null (always available) when the restriction is off", async () => {
    await dishApi.upsert({ id: 7, name: "Brunch", category: 3, price: 50, availability_schedule: null });
    const sent = api.put.mock.calls[0][1];
    expect("availability_schedule" in sent).toBe(true);
    expect(sent.availability_schedule).toBeNull();
  });
});

describe("categoryApi.upsert — prep station is sent", () => {
  beforeEach(() => {
    api.put.mockClear();
  });

  it("sends the trimmed station", async () => {
    await categoryApi.upsert({ id: 4, name: "Grill", super_category: 1, station: "  grill " });
    expect(api.put.mock.calls[0][1].station).toBe("grill");
  });

  it("caps the station at 40 chars and defaults to blank", async () => {
    await categoryApi.upsert({ id: 4, name: "Grill", super_category: 1, station: "x".repeat(50) });
    expect(api.put.mock.calls[0][1].station).toBe("x".repeat(40));
    await categoryApi.upsert({ id: 5, name: "Drinks", super_category: 1 });
    expect(api.put.mock.calls[1][1].station).toBe("");
  });
});
