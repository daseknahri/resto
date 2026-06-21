/**
 * Unit tests for BusyModeControl — the owner busy-mode / order-throttling control.
 *
 * Locks in the time-based derivations and PATCH wiring that protect the
 * "ordering is never silently left off" invariant:
 *  - paused state is derived from orders_paused_until vs a frozen `now`, and a
 *    past timestamp auto-resumes (renders the normal state, not paused);
 *  - the busy-extra bump only counts while busy_extra_until is in the future;
 *  - the snooze presets PATCH a FUTURE orders_paused_until and "Until I resume"
 *    pauses far out; Resume-now PATCHes it back to null;
 *  - the +10/+20 chips PATCH busy_extra_minutes + a future busy_extra_until, and
 *    Clear zeroes them;
 *  - the compact variant renders a single topbar button.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Deterministic i18n: key + interpolation passthrough so we can assert on text.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, vars) => (vars ? `${k}:${Object.values(vars).join(",")}` : k),
  }),
}));

// Freeze the ticker so paused/extra derivations are deterministic.
const NOW = new Date("2026-06-21T12:00:00Z").getTime();
vi.mock("../../composables/useNowTicker", () => ({
  useNowTicker: () => ({ now: { value: NOW } }),
}));

const patchMock = vi.fn(() => Promise.resolve({ data: {} }));
vi.mock("../../lib/api", () => ({ default: { patch: (...a) => patchMock(...a) } }));
vi.mock("../../lib/staleCache", () => ({ bustCache: vi.fn() }));

import BusyModeControl from "../BusyModeControl.vue";
import { useTenantStore } from "../../stores/tenant";

const isoFromNow = (ms) => new Date(NOW + ms).toISOString();

function mountControl(profile = {}, props = {}) {
  const tenant = useTenantStore();
  tenant.meta = { profile: { ...profile } };
  // Stub Teleport so the busy-mode sheet renders inline (queryable in the wrapper).
  const w = mount(BusyModeControl, { props, global: { stubs: { teleport: true } } });
  return { w, tenant };
}

beforeEach(() => {
  setActivePinia(createPinia());
  patchMock.mockClear();
});

describe("BusyModeControl — derived live state", () => {
  it("renders the normal (accepting) state with no busy fields set", () => {
    const { w } = mountControl({});
    expect(w.text()).toContain("busyMode.normalStatus");
    expect(w.text()).not.toContain("busyMode.pausedStatus");
  });

  it("shows paused + a live countdown when orders_paused_until is in the future", () => {
    const { w } = mountControl({ orders_paused_until: isoFromNow(15 * 60_000) });
    expect(w.text()).toContain("busyMode.pausedStatus");
    // resumingIn interpolates the countdown label (15 min).
    expect(w.text()).toContain("busyMode.resumingIn");
    // Resume-now is offered while paused.
    expect(w.text()).toContain("busyMode.resumeNow");
  });

  it("auto-resumes: a PAST orders_paused_until renders normal, not paused", () => {
    const { w } = mountControl({ orders_paused_until: isoFromNow(-5 * 60_000) });
    expect(w.text()).not.toContain("busyMode.pausedStatus");
    expect(w.text()).toContain("busyMode.normalStatus");
  });

  it("treats the extra bump as active only while busy_extra_until is in the future", () => {
    const active = mountControl({ busy_extra_minutes: 20, busy_extra_until: isoFromNow(30 * 60_000) });
    expect(active.w.text()).toContain("busyMode.busyStatus");

    const expired = mountControl({ busy_extra_minutes: 20, busy_extra_until: isoFromNow(-1 * 60_000) });
    expect(expired.w.text()).toContain("busyMode.normalStatus");
    expect(expired.w.text()).not.toContain("busyMode.busyStatus");
  });
});

describe("BusyModeControl — mutations", () => {
  it("pause preset PATCHes a FUTURE orders_paused_until", async () => {
    const { w } = mountControl({});
    await w.find("button").trigger("click"); // open the sheet via Manage
    // Find the 15-min preset by its passthrough label.
    const presets = w.findAll("button").filter((b) => b.text() === "busyMode.preset15");
    expect(presets.length).toBe(1);
    await presets[0].trigger("click");
    expect(patchMock).toHaveBeenCalledTimes(1);
    const [url, body] = patchMock.mock.calls[0];
    expect(url).toBe("/profile/");
    expect(typeof body.orders_paused_until).toBe("string");
    expect(new Date(body.orders_paused_until).getTime()).toBeGreaterThan(Date.now());
  });

  it("'Until I resume' pauses far in the future", async () => {
    const { w } = mountControl({});
    await w.find("button").trigger("click");
    const manual = w.findAll("button").filter((b) => b.text() === "busyMode.presetManual");
    await manual[0].trigger("click");
    const body = patchMock.mock.calls[0][1];
    // > 12h out (we use 24h) so it never silently expires before the owner resumes.
    expect(new Date(body.orders_paused_until).getTime() - Date.now()).toBeGreaterThan(12 * 60 * 60_000);
  });

  it("Resume-now PATCHes orders_paused_until back to null", async () => {
    const { w } = mountControl({ orders_paused_until: isoFromNow(20 * 60_000) });
    const resume = w.findAll("button").filter((b) => b.text() === "busyMode.resumeNow");
    expect(resume.length).toBe(1);
    await resume[0].trigger("click");
    expect(patchMock).toHaveBeenCalledWith("/profile/", { orders_paused_until: null });
  });

  it("the +20 chip PATCHes busy_extra_minutes plus a future expiry", async () => {
    const { w } = mountControl({});
    await w.find("button").trigger("click");
    // Chip text is `+20 busyMode.minShort` under the passthrough mock.
    const chip = w.findAll("button").filter((b) => b.text().startsWith("+20"));
    expect(chip.length).toBe(1);
    await chip[0].trigger("click");
    const [, body] = patchMock.mock.calls[0];
    expect(body.busy_extra_minutes).toBe(20);
    expect(new Date(body.busy_extra_until).getTime()).toBeGreaterThan(Date.now());
  });

  it("Clear zeroes the busy-extra bump", async () => {
    const { w } = mountControl({ busy_extra_minutes: 10, busy_extra_until: isoFromNow(30 * 60_000) });
    // The inline clear chip is shown when not paused but extra is active.
    const clear = w.findAll("button").filter((b) => b.text() === "busyMode.clearExtra");
    expect(clear.length).toBeGreaterThanOrEqual(1);
    await clear[0].trigger("click");
    expect(patchMock).toHaveBeenCalledWith("/profile/", { busy_extra_minutes: 0, busy_extra_until: null });
  });
});

describe("BusyModeControl — compact variant", () => {
  it("renders a single topbar button", () => {
    const { w } = mountControl({}, { compact: true });
    const buttons = w.findAll("button");
    expect(buttons.length).toBe(1);
    expect(buttons[0].text()).toContain("busyMode.title");
  });

  it("compact button shows the resuming countdown while paused", () => {
    const { w } = mountControl({ orders_paused_until: isoFromNow(10 * 60_000) }, { compact: true });
    expect(w.text()).toContain("busyMode.resumingIn");
  });
});
