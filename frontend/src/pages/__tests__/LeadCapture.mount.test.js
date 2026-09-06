/**
 * Mount smoke test for LeadCapture.vue (~326 lines) — the internal/owner-facing
 * lead-intake landing + form ("Start a new restaurant workspace"): a prospective
 * restaurant owner's details are captured and POSTed via the lead Pinia store.
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map / undefined-query access) was
 * never caught by a test". shallowMount runs the page's real setup() + first
 * render + onMounted, so any such crash fails CI here instead of in production.
 *
 * The page's UNIQUE mount-time logic is onMounted(applyPlanFromQuery): it reads
 * `route.query.plan` and pre-selects the plan. Reading `route.query.plan` when the
 * mocked route had no `query` object would throw the exact "cannot read properties
 * of undefined" setup-crash class — so both cases exercise it: case 1 with an empty
 * query, case 2 with ?plan=pro.
 *
 * API BOUNDARY: the page has NO direct lib/api import. It calls the lead Pinia
 * store (useLeadStore), but ONLY from submit() (a form-submit handler) — nothing
 * hits the network at mount (onMounted just applies the plan from the query). So
 * real pinia covers the store. lib/api is still mocked DEFENSIVELY: importing the
 * page transitively imports stores/lead, which imports lib/api at module load; the
 * mock guarantees nothing can reach the network.
 *
 * vue-router: the page imports ONLY { useRoute } and reads route.query.plan at
 * setup (onMounted + a watch), so useRoute is mocked with a vi.hoisted mutable
 * holder each test seeds before mount. useRouter is provided defensively (the page
 * never uses it). No <RouterLink> in the template → no RouterLink stub needed, and
 * the template has no child components, so plain shallowMount suffices.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    // The page destructures ONLY { t }. Return the key verbatim so own-template
    // headings assert deterministically.
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// Defensive: importing the page transitively imports stores/lead, which imports
// lib/api at module load. The page does NOT hit the network at mount, but keep it
// mocked so nothing (e.g. an accidental store action) ever can.
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// The page reads route.query.plan at setup (onMounted → applyPlanFromQuery, and a
// watch(() => route.query.plan, ...)). Expose a hoisted mutable the factory returns
// and each test seeds BEFORE mount. `query` is always an object (as real vue-router
// guarantees) so the undefined-query read cannot throw.
const routeState = vi.hoisted(() => ({ query: {}, params: {} }));
vi.mock("vue-router", () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import LeadCapture from "../LeadCapture.vue";

const mountPage = () => shallowMount(LeadCapture);

describe("LeadCapture — mount smoke", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    sessionStorage.clear(); // lib/analytics (pulled in by the lead store) reads sessionStorage
    routeState.query = {};
    routeState.params = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    routeState.query = {};
  });

  // ── (1) default render — empty route query ──────────────────────────────────
  // setup() must not throw and onMounted(applyPlanFromQuery) must survive an empty
  // route.query (the undefined-query read this guard exists to catch). With no
  // ?plan, the reactive form stays on its "basic" default, so the first stat tile's
  // value (selectedPlanLabel) reads "Basic".
  it("mounts without a setup() crash and renders the lead-intake form", async () => {
    let wrapper;
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);

    const text = wrapper.text();
    // Own-template hero heading + kicker (leadCapture.* — verbatim via the mocked t).
    expect(text).toContain("leadCapture.title");
    expect(text).toContain("leadCapture.kicker");
    // No ?plan → default plan; the first .ui-stat-value renders selectedPlanLabel.
    expect(wrapper.find(".ui-stat-value").text()).toBe("Basic");
    // A fresh mount is not in the submitted state (lead.success is false).
    expect(text).not.toContain("leadCapture.submittedOk");
  });

  // ── (2) deep-linked plan — ?plan=pro ────────────────────────────────────────
  // The page's real mount-time variation: onMounted(applyPlanFromQuery) reads
  // route.query.plan and pre-selects it. Seed ?plan=pro and assert the selected
  // plan label flipped to "Pro" — proving the query was read at setup (without
  // throwing) and selectedPlanLabel recomputed off it.
  it("applies ?plan=pro from the route query at mount", async () => {
    routeState.query = { plan: "pro" };

    let wrapper;
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);

    // selectedPlanLabel recomputed from the applied ?plan=pro.
    expect(wrapper.find(".ui-stat-value").text()).toBe("Pro");
    // Heading still renders in this variation.
    expect(wrapper.text()).toContain("leadCapture.title");
  });
});
