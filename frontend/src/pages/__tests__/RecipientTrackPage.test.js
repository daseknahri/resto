/**
 * Unit tests for RecipientTrackPage — the public, no-auth recipient package tracker.
 *
 * Locks in: token-keyed GET on mount; status→label mapping; intro with/without
 * recipient name; handover code shown only while live; 404 → not-found state;
 * courier card rendered only once a courier is assigned.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));

const getMock = vi.fn();
vi.mock("../../lib/api", () => ({
  default: { get: (...a) => getMock(...a) },
}));

vi.mock("../../lib/mapTiles", () => ({ addTileLayer: vi.fn() }));

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { token: "tok_abc123" } }),
}));

import RecipientTrackPage from "../RecipientTrackPage.vue";

function payload(overrides = {}) {
  return {
    kind: "package",
    status: "searching",
    recipient_name: "Jane",
    pickup_address: "Pickup St",
    dropoff_address: "Drop Ave",
    dropoff_lat: 33.55,
    dropoff_lng: -7.65,
    courier: null,
    driver_lat: null,
    driver_lng: null,
    eta_minutes: null,
    delivery_code: "654321",
    ...overrides,
  };
}

describe("RecipientTrackPage", () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it("fetches the public track endpoint with the URL token on mount", async () => {
    getMock.mockResolvedValue({ data: payload() });
    mount(RecipientTrackPage);
    await flushPromises();
    expect(getMock).toHaveBeenCalledWith("/track/tok_abc123/");
  });

  it("shows the searching status, recipient-named intro, and the handover code while live", async () => {
    getMock.mockResolvedValue({ data: payload({ status: "searching" }) });
    const w = mount(RecipientTrackPage);
    await flushPromises();
    expect(w.text()).toContain("recipientTrack.statusSearching");
    // intro carries the recipient name through the interpolation
    expect(w.text()).toContain("recipientTrack.intro");
    expect(w.text()).toContain("Jane");
    // code visible
    expect(w.text()).toContain("654321");
    expect(w.text()).toContain("recipientTrack.codeTitle");
    // no courier assigned yet → no courier card label
    expect(w.text()).not.toContain("recipientTrack.courierLabel");
  });

  it("renders the courier card + in-progress label when a courier is assigned", async () => {
    getMock.mockResolvedValue({
      data: payload({
        status: "in_progress",
        courier: { first_name: "Karim", vehicle: "Yamaha" },
        eta_minutes: 6,
      }),
    });
    const w = mount(RecipientTrackPage);
    await flushPromises();
    expect(w.text()).toContain("recipientTrack.statusInProgress");
    expect(w.text()).toContain("recipientTrack.courierLabel");
    expect(w.text()).toContain("Karim");
    expect(w.text()).toContain("Yamaha");
    // ETA shown while live
    expect(w.text()).toContain("recipientTrack.etaMinutes");
  });

  it("uses the no-name intro and hides the code once delivered", async () => {
    getMock.mockResolvedValue({
      data: payload({
        status: "completed",
        recipient_name: "",
        delivery_code: undefined,
        courier: { first_name: "Karim", vehicle: "" },
      }),
    });
    const w = mount(RecipientTrackPage);
    await flushPromises();
    expect(w.text()).toContain("recipientTrack.statusCompleted");
    expect(w.text()).toContain("recipientTrack.introNoName");
    expect(w.text()).not.toContain("recipientTrack.codeTitle");
  });

  it("shows the not-found state on a 404", async () => {
    getMock.mockRejectedValue({ response: { status: 404 } });
    const w = mount(RecipientTrackPage);
    await flushPromises();
    expect(w.text()).toContain("recipientTrack.notFound");
  });
});
