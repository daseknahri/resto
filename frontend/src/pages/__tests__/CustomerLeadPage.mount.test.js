/**
 * Mount smoke test for CustomerLeadPage.vue (~552 lines) — the customer-facing
 * storefront landing + lead-capture ("contact me") page.
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, unguarded browser API)
 * was never caught by a test". shallowMount runs the page's real setup() + first
 * render, so any such crash fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/Home.mount.test.js and
 * pages/__tests__/SuperAppHub.mount.test.js:
 *   - shallowMount (auto-stubs the AppIcon child) so the page's OWN setup() runs
 *   - real pinia (setActivePinia(createPinia())) so the lead/customer/tenant/toast
 *     stores are real. Case 2 seeds tenant.meta directly — resolvedMeta is a getter
 *     over state.meta — to drive the storefront panels off a real profile payload.
 *   - useI18n mocked to return deterministic keys (the page destructures { currentLocale, t })
 *
 * API BOUNDARY: the page has no direct lib/api import — it goes through the lead
 * Pinia store. But lib/api IS hit at MOUNT via lib/analytics.trackEvent: onMounted
 * fires trackEvent("customer_info_view", ...) and isPublicDemoHost("localhost") is
 * false in jsdom, so trackEvent does NOT early-return → it calls
 * api.post("/analytics/events/"). The lead store (and the customer/tenant/toast
 * stores) also import lib/api. So lib/api is mocked with a default { data: {} } to
 * keep the mount hermetic and off the network.
 *
 * NOT mocked: the page does NOT import from vue-router — <RouterLink> is a template
 * global, covered by a plain global stub (no vi.hoisted / no vue-router mock needed).
 * lib/businessHours, lib/escape (safeExternalUrl) and lib/runtimeHost are left REAL;
 * they are fully defensive and jsdom-safe, so running them exercises real setup.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// Hit at mount via lib/analytics.trackEvent (api.post) and imported by the lead /
// customer / tenant / toast stores. Default everything to empty so nothing hits
// the network.
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import { useTenantStore } from "../../stores/tenant";
import CustomerLeadPage from "../CustomerLeadPage.vue";

const mountPage = () =>
  shallowMount(CustomerLeadPage, {
    global: {
      stubs: {
        // Pass-through so slot content (CTA labels, quick-action labels) renders —
        // RouterLink is a template global here (the page does not import it).
        RouterLink: { name: "RouterLink", props: ["to"], template: "<a><slot /></a>" },
        // The contact modal is <Teleport to="body"> (v-if false at mount); stub it
        // so nothing teleports out of the wrapper during the render.
        Teleport: { template: "<slot />" },
      },
    },
  });

describe("CustomerLeadPage — mount smoke", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    sessionStorage.clear(); // lib/analytics.getSessionId() reads sessionStorage
    vi.clearAllMocks();
  });

  // ── (1) default / guest render (no tenant meta) ─────────────────────────────
  // The whole point of the guard: setup() must not throw. The hero + the always-on
  // "Send a message" card render even with no profile (tenantName / description
  // fall back), so their own-template keys prove the first render completed.
  it("mounts without a setup() crash and renders the storefront landing", async () => {
    let wrapper;
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);

    const text = wrapper.text();
    // "Send a message" card title — always rendered (own namespace, verbatim via the mocked t).
    expect(text).toContain("customerLeadPage.helpTitle");
    // Hero "Browse Menu" CTA — always rendered.
    expect(text).toContain("customerLayout.navMenu");
    // localhost is not a public-demo host → the platform demo banner branch is off.
    expect(text).not.toContain("home.heroTitle");
  });

  // ── (2) loaded storefront: a real tenant profile ────────────────────────────
  // Seed tenant.meta (resolvedMeta getter returns it) with a full profile so the
  // data-driven panels render: the business-hours panel runs the REAL
  // lib/businessHours over a weekly schedule, the quick-actions strip builds
  // phone/whatsapp/maps actions, and the external-reservation card renders. setup()
  // must still not throw with real data flowing through every computed.
  it("mounts a loaded tenant profile (business hours + quick actions + reservation)", async () => {
    const tenant = useTenantStore();
    tenant.meta = {
      name: "Chez Test",
      profile: {
        tagline: "Best tagine in town",
        description: "Traditional Moroccan cuisine.",
        address: "123 Rue Test, Casablanca",
        phone: "+212600000000",
        whatsapp: "+212600000001",
        google_maps_url: "https://maps.google.com/?q=chez-test",
        reservation_url: "https://booking.example.com/chez-test",
        instagram_url: "https://instagram.com/cheztest",
        business_hours_schedule: {
          mon: { enabled: true, open: "09:00", close: "22:00" },
          tue: { enabled: true, open: "09:00", close: "22:00" },
          wed: { enabled: true, open: "09:00", close: "22:00" },
          thu: { enabled: true, open: "09:00", close: "22:00" },
          fri: { enabled: true, open: "09:00", close: "23:00" },
          sat: { enabled: true, open: "10:00", close: "23:00" },
          sun: { enabled: false },
        },
      },
    };

    let wrapper;
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);

    const text = wrapper.text();
    // Business-hours panel rendered from the seeded schedule (real businessHours lib ran).
    expect(text).toContain("customerLeadPage.businessHours");
    // Phone quick action built from the seeded phone.
    expect(text).toContain("customerLeadPage.callNow");
    // External reservation card rendered from the seeded (https) reservation_url.
    expect(text).toContain("customerLeadPage.bookOnPlatform");
    // The always-on contact card still renders alongside the loaded panels.
    expect(text).toContain("customerLeadPage.helpTitle");
  });
});
