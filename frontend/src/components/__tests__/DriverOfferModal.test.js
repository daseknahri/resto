/**
 * Unit tests for DriverOfferModal — the full-screen exclusive-offer takeover.
 *
 * Locks in: renders only when an offer is present; the SVG countdown ring's
 * stroke-dashoffset shrinks as time runs out and the ring colour escalates
 * (emerald → amber → red); Accept/Pass emit with the offer id; the chime is
 * gated behind a one-time enable-sound tap (no sound until enabled).
 *
 * The modal renders into <body> via <Teleport>, so assertions query the document
 * (not the wrapper subtree) and each test unmounts to clear the body.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { mount } from "@vue/test-utils";

// Deterministic i18n: key + interpolation passthrough so we can assert on text.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, vars) => (vars ? `${k}:${Object.values(vars).join(",")}` : k),
  }),
}));

import DriverOfferModal from "../DriverOfferModal.vue";

const offer = {
  id: 42,
  driver_payout: "18.50",
  restaurant_name: "Chez Karim",
  delivery_address: "10 Rue X",
  distance_km: 3.2,
  distance_to_pickup_km: 1.1,
  items_count: 4,
  collect_cash: false,
  order_total: "60.00",
  offer_expires_at: "2026-06-21T12:00:30Z",
};

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

let wrapper = null;
const mountModal = (props = {}) => {
  wrapper = mount(DriverOfferModal, {
    props: { offer, secondsLeft: 20, totalSeconds: 30, fmtMoney: (v) => `$${v}`, ...props },
    attachTo: document.body,
  });
  return wrapper;
};

// Buttons live in the teleported dialog → find them in the document by text.
const findButton = (text) =>
  [...document.querySelectorAll('[role="dialog"] button')].find((b) =>
    b.textContent.includes(text),
  );
const progressRing = () => document.querySelectorAll('[role="dialog"] circle')[1];

beforeEach(() => {
  try { localStorage.clear(); } catch (e) { void e; }
});
afterEach(() => {
  if (wrapper) { wrapper.unmount(); wrapper = null; }
  document.body.innerHTML = "";
});

describe("DriverOfferModal", () => {
  it("renders nothing when offer is null", () => {
    mountModal({ offer: null });
    expect(document.querySelector('[role="dialog"]')).toBeNull();
  });

  it("renders the takeover with payout, pickup chip and address when an offer is present", () => {
    mountModal();
    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog.textContent).toContain("$18.50");
    expect(dialog.textContent).toContain("driver.toPickupKm:1.1");
    expect(dialog.textContent).toContain("10 Rue X");
  });

  it("ring is full (no offset) when the whole window remains", () => {
    mountModal({ secondsLeft: 30, totalSeconds: 30 });
    expect(Number(progressRing().getAttribute("stroke-dashoffset"))).toBeCloseTo(0, 3);
  });

  it("ring is ~half offset when half the window has elapsed", () => {
    mountModal({ secondsLeft: 15, totalSeconds: 30 });
    expect(Number(progressRing().getAttribute("stroke-dashoffset"))).toBeCloseTo(CIRCUMFERENCE / 2, 1);
  });

  it("ring colour is emerald with plenty of time", () => {
    mountModal({ secondsLeft: 20 });
    expect(progressRing().getAttribute("class")).toContain("text-emerald-400");
  });

  it("ring colour is amber when time is getting low", () => {
    mountModal({ secondsLeft: 8 });
    expect(progressRing().getAttribute("class")).toContain("text-amber-400");
  });

  it("ring colour is red when nearly expired", () => {
    mountModal({ secondsLeft: 3 });
    expect(progressRing().getAttribute("class")).toContain("text-red-400");
  });

  it("emits accept with the offer id when the primary button is tapped", () => {
    mountModal();
    findButton("driverOffer.accept").click();
    expect(wrapper.emitted("accept")).toBeTruthy();
    expect(wrapper.emitted("accept")[0]).toEqual([42]);
  });

  it("emits pass with the offer id when the pass button is tapped", () => {
    mountModal();
    findButton("driverOffer.pass").click();
    expect(wrapper.emitted("pass")).toBeTruthy();
    expect(wrapper.emitted("pass")[0]).toEqual([42]);
  });

  it("shows the enable-sound prompt until the driver enables it once", async () => {
    mountModal();
    const enableBtn = findButton("driverOffer.enableSound");
    expect(enableBtn).toBeTruthy();
    enableBtn.click();
    await wrapper.vm.$nextTick();
    expect(localStorage.getItem("kepoli.driver.offerSound")).toBe("1");
    // After enabling, the prompt is gone.
    expect(findButton("driverOffer.enableSound")).toBeUndefined();
  });

  it("fires a haptic buzz when a new offer takes over the screen", async () => {
    const vibrate = vi.fn();
    vi.stubGlobal("navigator", { ...navigator, vibrate });
    wrapper = mount(DriverOfferModal, {
      props: { offer: null, secondsLeft: 20, totalSeconds: 30, fmtMoney: (v) => v },
      attachTo: document.body,
    });
    await wrapper.setProps({ offer });
    expect(vibrate).toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
