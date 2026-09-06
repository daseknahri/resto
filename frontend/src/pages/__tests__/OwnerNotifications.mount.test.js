/**
 * Mount smoke test for OwnerNotifications.vue (the owner outbound-notifications
 * log page, ~227 lines — push / SMS / email / WhatsApp send records + a summary
 * stat bar + channel/status filters).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined access, an invalid Intl option
 * combo, an unguarded browser API) was never caught by a test". OwnerNotifications
 * runs a real onMounted(fetchLog) that GETs /owner/notifications/ and then renders
 * a list v-for with per-row helpers (channelLabel / statusLabel + their class maps
 * and fmtTime, which calls Date#toLocaleString with { dateStyle, timeStyle }).
 * Mounting runs all of that for real, so a crash in setup() or the initial render
 * fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerReservations.mount.test.js (the closest
 * template: a no-vue-router owner page with a URL-routed api mock + real pinia):
 *   - shallowMount (the page imports no child components — only inline SVG — so
 *     there is nothing heavy to stub; shallowMount is used for parity with the
 *     other owner-page smoke tests)
 *   - real pinia (setActivePinia) for parity, though this page uses no store
 *   - useI18n mocked to exactly { t, currentLocale } — the page's real destructure.
 *     currentLocale must expose `.value` because fmtTime reads currentLocale.value.
 *   - lib/api mocked (default export) — onMounted fires GET /owner/notifications/.
 *
 * NOT mocked: the page imports NOTHING from 'vue-router' (verified via grep), so
 * vue-router is not mocked and no vi.hoisted RouterLink stub is needed. There is no
 * poll / interval / observer / WebSocket / staleCache / scrollIntoView touched at
 * mount, so afterEach unmount is pure hygiene. localStorage.clear() is kept in
 * beforeEach by convention even though this page reads no cache.
 *
 * Intl note: fmtTime uses toLocaleString(locale, { dateStyle:'short',
 * timeStyle:'short' }) — a VALID combination (the throwing combo is dateStyle/
 * timeStyle together with timeZoneName), so it does not throw at mount.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    // t returns the key verbatim (params, when present, are appended so the raw
    // key path is still asserted-on). currentLocale exposes `.value` because
    // fmtTime reads currentLocale.value as the toLocaleString locale arg.
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: onMounted fires GET /owner/notifications/. Default:
// everything resolves { data: {} } so the empty-log path renders (results is
// undefined → rows=[], summary={}). Tests set _routes to drive the loaded path.
// _routes/_match are plain (not vi.hoisted): they are only read lazily inside the
// vi.fn callback when api.get is actually invoked at mount — never during the
// hoisted factory's own evaluation — so there is no TDZ.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import OwnerNotifications from "../OwnerNotifications.vue";

const mountPage = () => shallowMount(OwnerNotifications);

// A realistic notification row with the fields the page's own template + helpers
// read: id (v-for key), channel/status (badge label + class maps), created_at
// (fmtTime), event / recipient / reference / detail / error (raw text spans).
const notification = (overrides = {}) => ({
  id: 1,
  channel: "push",
  status: "sent",
  event: "order.confirmed",
  recipient: "+212600112233",
  reference: "A100",
  detail: "Order confirmed push",
  error: "",
  created_at: "2026-09-05T12:00:00Z",
  ...overrides,
});

describe("OwnerNotifications — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // Kept by convention (the OwnerHome/OwnerReservations smoke tests clear a
    // staleCache-backed localStorage here); this page reads no cache, so it is
    // purely defensive against cross-test browser-storage leakage.
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

  // ── (1) empty / default mount ──────────────────────────────────────────────
  // The core guard: onMounted(fetchLog) → GET /owner/notifications/ resolves
  // { data: {} } → rows=[], summary={} → the header + summary stat bar + empty
  // state must render without a setup() crash.
  it("mounts with an empty log (no notifications) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (always rendered, outside every v-if) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerNotifications.title");
    expect(wrapper.text()).toContain("ownerNotifications.kicker");
    // Empty results → the empty-state block renders.
    expect(wrapper.text()).toContain("ownerNotifications.empty");
  });

  // ── (2) loaded state with a realistic notifications payload ────────────────
  // Drives the list v-for + every per-row helper (channelLabel/channelClass,
  // statusLabel/statusClass, fmtTime over created_at) and the raw event/recipient/
  // reference/detail spans — the own-template paths that only run with a non-empty
  // results array. The second row exercises the failed-status + error branch.
  it("mounts with a loaded notifications payload without a crash", async () => {
    _routes = {
      "/owner/notifications/": {
        data: {
          results: [
            notification(),
            notification({
              id: 2,
              channel: "email",
              status: "failed",
              event: "receipt.email",
              recipient: "guest@example.com",
              error: "SMTP 550 mailbox unavailable",
            }),
          ],
          summary: { sent: 12, failed: 3, skipped: 1 },
        },
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerNotifications.title");
    // The v-for rendered the loaded rows — raw event/recipient text (rendered
    // directly, not via the mocked t) proves the loaded list path ran clean.
    expect(wrapper.text()).toContain("order.confirmed");
    expect(wrapper.text()).toContain("guest@example.com");
  });
});
