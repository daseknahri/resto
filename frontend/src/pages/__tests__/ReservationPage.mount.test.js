/**
 * Mount smoke test for ReservationPage.vue (~653 lines) — the customer-facing
 * table-reservation booking page (name/phone/party-size/date/time → submit lead).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined map access, bad import) was never
 * caught by a test" (this same pass already caught a real WaiterPage TDZ). Mounting
 * the page runs its real setup() so any such crash fails CI here instead of in prod.
 *
 * HOW THIS PAGE GETS ITS RESTAURANT IDENTITY: no route param, no prop, no
 * vue-router at all (grep-confirmed: the SFC imports nothing from 'vue-router' and
 * the template has no RouterLink). It reads the subdomain-scoped tenant store —
 * `useTenantStore().resolvedMeta`, whose first branch just returns `state.meta`.
 * So the loaded case sets `tenant.meta` directly; nothing to mock on the router.
 *
 * Pattern-faithful to pages/__tests__/MarketplaceMenuPage.mount.test.js +
 * SuperAppHub.mount.test.js + OwnerHome.mount.test.js:
 *   - shallowMount (auto-stubs the one child component, AppIcon)
 *   - real pinia (tenant / lead / customer / cart / toast stores run for real) +
 *     a URL-routed mocked lib/api
 *   - useI18n mocked → deterministic keys (the SFC destructures `{ t }` ONLY)
 *
 * The page fires NO api call at mount: onMounted only fetches availability when a
 * date is already set, and `form.date` starts "". So the default `{ data: {} }`
 * mock is untouched at mount — it exists only to keep the real stores off the
 * network. There are no intervals/timers on this page (only three form watchers,
 * auto-torn-down); afterEach still unmounts for hygiene + parity with the others.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// The SFC does: `const { t } = useI18n();` — only `t`. Return key verbatim.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// URL-routed api mock (default { data: {} }). Nothing is fetched at mount; this
// only guarantees the real tenant/lead stores never touch the network. Per-test
// _routes can drive a fetched payload if the test opts into one.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import { useTenantStore } from "../../stores/tenant";
import ReservationPage from "../ReservationPage.vue";

// shallowMount auto-stubs AppIcon (the only child); the page has no
// RouterLink/Transition/Teleport, so no manual stubs are needed.
const mountPage = () => shallowMount(ReservationPage);

describe("ReservationPage — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // No page code calls tenant.fetchMeta() (the only staleCache/localStorage
    // user), but clear storage anyway so nothing bleeds between tests.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default mount: no tenant meta, empty form → loading/empty path ──────
  // The core guard: setup() (the async onMounted pre-fill, the availability +
  // waitlist + validation closures, todayDateStr IIFE, and the three watchers)
  // must run and render with empty data without throwing.
  it("mounts without a setup() crash (no meta, empty form)", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Always-rendered, meta-independent own-template text — the crash anchor.
    expect(wrapper.text()).toContain("reservationPage.title");
    expect(wrapper.text()).toContain("reservationPage.bookingSummary");
    // Submit CTA present on the default (!lead.fullyBooked) path.
    expect(wrapper.text()).toContain("reservationPage.submitReservation");
  });

  // ── (2) loaded tenant meta: contact + external-booking sections render ──────
  // resolvedMeta returns state.meta (first getter branch), so setting tenant.meta
  // BEFORE mount drives the meta-derived computeds (capacityEnabled / phoneHref /
  // whatsappHref / reservationUrl) — the own-template paths that render only for a
  // loaded restaurant profile (a genuine loaded state, not a stubbed child).
  it("mounts a loaded restaurant (phone / whatsapp / reservation_url) and renders the contact + booking sections", async () => {
    const tenant = useTenantStore();
    tenant.meta = {
      name: "Chez Test",
      slug: "chez-test",
      profile: {
        phone: "+212600000000",
        whatsapp: "+212600000000",
        reservation_url: "https://book.example.com/chez-test",
        max_covers_per_slot: 20,
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Contact-support CTAs render only when the loaded profile has phone/whatsapp.
    expect(wrapper.text()).toContain("reservationPage.callNow");
    expect(wrapper.text()).toContain("reservationPage.whatsappMessage");
    // External-booking block renders only when the loaded profile has reservation_url.
    expect(wrapper.text()).toContain("reservationPage.bookDirectly");
  });
});
