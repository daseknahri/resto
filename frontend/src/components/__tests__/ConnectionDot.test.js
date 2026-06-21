/**
 * Unit tests for ConnectionDot — the live-connection indicator on real-time
 * surfaces (order-status / ride tracking).
 *
 * Locks in: 'live' → green dot + "Live" label/aria; any non-live state
 * ('connecting'|'polling'|'idle') → amber dot + "Reconnecting" label/aria;
 * showLabel toggles the visible text without affecting the aria-label.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

// Deterministic i18n: known keys map to readable strings, others pass through.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) =>
      ({ "realtime.live": "Live", "realtime.reconnecting": "Reconnecting" }[k] ||
      k),
  }),
}));

import ConnectionDot from "../ConnectionDot.vue";

describe("ConnectionDot", () => {
  it("shows a green dot and Live aria-label when state is 'live'", () => {
    const w = mount(ConnectionDot, { props: { state: "live" } });
    expect(w.find('[role="status"]').attributes("aria-label")).toBe("Live");
    expect(w.html()).toContain("bg-emerald-400");
    // a ping ring is present only in the live state
    expect(w.html()).toContain("animate-ping");
  });

  it("shows an amber dot and Reconnecting aria-label when connecting", () => {
    const w = mount(ConnectionDot, { props: { state: "connecting" } });
    expect(w.find('[role="status"]').attributes("aria-label")).toBe(
      "Reconnecting",
    );
    expect(w.html()).toContain("bg-amber-400");
    expect(w.html()).not.toContain("animate-ping");
  });

  it.each(["polling", "idle", ""])(
    "treats non-live state %p as reconnecting",
    (state) => {
      const w = mount(ConnectionDot, { props: { state } });
      expect(w.find('[role="status"]').attributes("aria-label")).toBe(
        "Reconnecting",
      );
    },
  );

  it("defaults to a reconnecting state when no prop is supplied", () => {
    const w = mount(ConnectionDot);
    expect(w.find('[role="status"]').attributes("aria-label")).toBe(
      "Reconnecting",
    );
  });

  it("hides the text label by default and shows it with showLabel", () => {
    const hidden = mount(ConnectionDot, { props: { state: "live" } });
    expect(hidden.text()).not.toContain("Live");

    const shown = mount(ConnectionDot, {
      props: { state: "live", showLabel: true },
    });
    expect(shown.text()).toContain("Live");
  });
});
