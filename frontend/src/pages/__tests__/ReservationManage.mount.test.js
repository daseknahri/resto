/**
 * Mount smoke test for ReservationManage.vue (~296 lines) — the customer's
 * manage-a-booking page: they arrive via a tokenised link (`/r/manage/:token`),
 * the page validates+loads the reservation and lets them view / cancel it.
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined access, a bad import) was never
 * caught by a test" (this same coverage pass already caught a real WaiterPage TDZ).
 * Mounting the page runs its real setup() + onMounted for real, so any such crash
 * fails CI here instead of in production.
 *
 * HOW THIS PAGE GETS ITS IDENTITY: a REQUIRED prop `token`
 * (`defineProps({ token: { type: String, required: true } })`), NOT a route param —
 * onMounted(load) fires `api.get(`/reservations/manage/${props.token}/`)`. So we
 * mount with `props: { token }`. Grep-confirmed: the SFC imports NOTHING from
 * 'vue-router' (no useRouter, no useRoute, no RouterLink) and the template has no
 * RouterLink — so there is no router to mock and no vi.hoisted stub to hoist.
 *
 * Pattern-faithful to pages/__tests__/OrderStatus.mount.test.js (customer page with
 * a required prop identifier + URL-routed api mock) and ReservationPage.mount.test.js:
 *   - shallowMount (the SFC has NO child components; only native elements + the
 *     built-in <Transition>, which we pass-through-stub for determinism)
 *   - real pinia (the page uses no store, but keep parity with the recipe)
 *   - a URL-routed mocked lib/api (default { data: {} })
 *   - useI18n mocked → deterministic keys; the SFC destructures `{ t, currentLocale }`
 *     and `formatWhen()` reads `currentLocale.value` inside Intl.DateTimeFormat, so
 *     the mock MUST return both.
 *
 * The page has NO intervals / observers / WebSocket / localStorage at mount — the
 * whole setup is: three refs + one reactive() + onMounted(load) (a single GET).
 * afterEach still unmounts for hygiene + parity with the other smoke tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// The SFC does `const { t, currentLocale } = useI18n();`. `t` echoes the key;
// currentLocale is a plain { value } object (formatWhen reads currentLocale.value
// and passes it to new Intl.DateTimeFormat(locale, …) — "en" is valid in node's ICU).
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock. onMounted fires GET /reservations/manage/<token>/, and the
// cancel action (user click only, never at mount) POSTs .../cancel/. Default:
// everything resolves empty ({ data: {} }). NOTE: res.data === {} does NOT reject,
// so load()'s catch never runs → notFound stays false and the page renders its
// (empty) MAIN card, not the not-found state. Tests set _routes to drive a loaded
// reservation.
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

import ReservationManage from "../ReservationManage.vue";

// shallowMount needs no component stubs (the SFC imports none). The template's only
// built-in is <Transition> (in the cancel flow); pass it through so its active
// slotted child (the cancel button) renders synchronously for the loaded case.
const mountPage = (token = "tok_abc123") =>
  shallowMount(ReservationManage, {
    props: { token },
    global: {
      stubs: {
        Transition: { template: "<slot />" },
      },
    },
  });

describe("ReservationManage — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // The page touches no localStorage/store, but clear + reset for parity with the
    // recipe so nothing bleeds between tests.
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

  // ── (1) default mount: token present, empty fetch ({ data: {} }) ────────────
  // The core guard: setup() (refs + reactive) and the async onMounted (load() →
  // GET → _apply({}) → loading=false) must run and render the empty main card
  // without throwing. { data: {} } → _apply({}) zeroes every field, so the header
  // falls back to t('reservationManage.title') and the non-cancellable notice shows.
  it("mounts with the required token prop and an empty fetch without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage("tok_abc123");
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // Always-rendered own-template anchors in the main card (no v-if): the kicker
    // and the title fallback (data.restaurant is "" → t('reservationManage.title')).
    expect(wrapper.text()).toContain("reservationManage.kicker");
    expect(wrapper.text()).toContain("reservationManage.title");
  });

  // ── (2) a loaded, cancellable reservation ───────────────────────────────────
  // Route a realistic booking payload → _apply() fills restaurant / booked_for /
  // party_size and flips can_cancel true. This drives the loaded own-template
  // paths that only render with a real reservation: the restaurant name in the
  // header + detail row, formatWhen(booked_for) (Intl.DateTimeFormat), the
  // party-size plural branch, and the cancel-flow button.
  it("mounts a loaded, cancellable reservation (restaurant + party size + cancel flow) without a crash", async () => {
    _routes = {
      "/reservations/manage/": {
        data: {
          restaurant: "Le Gourmet",
          name: "Sara",
          booked_for: new Date(Date.now() + 24 * 60 * 60_000).toISOString(),
          party_size: 4,
          status: "confirmed",
          cancelled: false,
          is_past: false,
          can_cancel: true,
        },
      },
    };

    expect(() => {
      wrapper = mountPage("tok_loaded");
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // Restaurant name flowed into the header + detail row (proves the loaded
    // payload rendered, not a stub).
    expect(wrapper.text()).toContain("Le Gourmet");
    // Party size + plural label (party_size 4 → the t('reservationManage.people')
    // branch) — proves party_size ran through its template row.
    expect(wrapper.text()).toContain("reservationManage.people");
    // Cancel-flow button renders only on the !cancelled && can_cancel path.
    expect(wrapper.text()).toContain("reservationManage.cancelButton");
  });
});
