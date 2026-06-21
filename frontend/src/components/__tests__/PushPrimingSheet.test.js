/**
 * Unit tests for PushPrimingSheet — the push-permission soft-ask.
 *
 * Locks in the gating contract: the sheet only opens when push is supported,
 * permission is still 'default', the deployment has push enabled, and the user
 * hasn't recently dismissed it. On accept it calls subscribe() (the real OS
 * prompt); on dismiss it persists a cooldown flag so it won't nag again.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { ref } from "vue";
import { mount, flushPromises } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

// Controllable push-composable mock shared across the suite.
const pushState = {
  supported: true,
  permission: ref("default"),
  subscribe: vi.fn(() => Promise.resolve()),
  checkEnabled: vi.fn(() => Promise.resolve(true)),
};
vi.mock("../../composables/useCustomerPush", () => ({
  useCustomerPush: () => pushState,
}));

import PushPrimingSheet from "../PushPrimingSheet.vue";

const DISMISS_KEY = "push_prime_dismissed_at";

function mountSheet() {
  return mount(PushPrimingSheet, {
    attachTo: document.body,
    // Stub Transition to a plain passthrough so leave-animations don't keep the
    // dialog in the DOM after dismissal during synchronous test flushes.
    global: {
      stubs: {
        Teleport: true,
        Transition: { template: "<div><slot /></div>" },
      },
    },
  });
}

describe("PushPrimingSheet", () => {
  beforeEach(() => {
    localStorage.clear();
    pushState.supported = true;
    pushState.permission.value = "default";
    pushState.subscribe.mockReset().mockResolvedValue(undefined);
    pushState.checkEnabled.mockReset().mockResolvedValue(true);
  });

  it("does not render itself on mount (parent-triggered only)", async () => {
    const w = mountSheet();
    await flushPromises();
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("opens on maybeShow when supported + default + enabled + not dismissed", async () => {
    const w = mountSheet();
    await w.vm.maybeShow();
    await flushPromises();
    expect(pushState.checkEnabled).toHaveBeenCalled();
    expect(w.find('[role="dialog"]').exists()).toBe(true);
  });

  it("stays closed when permission is not 'default'", async () => {
    pushState.permission.value = "granted";
    const w = mountSheet();
    await w.vm.maybeShow();
    await flushPromises();
    expect(pushState.checkEnabled).not.toHaveBeenCalled();
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("stays closed when push is not supported", async () => {
    pushState.supported = false;
    const w = mountSheet();
    await w.vm.maybeShow();
    await flushPromises();
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("stays closed when the deployment has push disabled", async () => {
    pushState.checkEnabled.mockResolvedValue(false);
    const w = mountSheet();
    await w.vm.maybeShow();
    await flushPromises();
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("stays closed when recently dismissed", async () => {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    const w = mountSheet();
    await w.vm.maybeShow();
    await flushPromises();
    expect(pushState.checkEnabled).not.toHaveBeenCalled();
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("re-shows after the dismissal cooldown has elapsed", async () => {
    // 31 days ago — beyond the 30-day cooldown.
    localStorage.setItem(DISMISS_KEY, String(Date.now() - 31 * 24 * 60 * 60 * 1000));
    const w = mountSheet();
    await w.vm.maybeShow();
    await flushPromises();
    expect(w.find('[role="dialog"]').exists()).toBe(true);
  });

  it("accept → calls subscribe() and persists the cooldown flag", async () => {
    const w = mountSheet();
    await w.vm.maybeShow();
    await flushPromises();
    const buttons = w.findAll("button");
    await buttons[0].trigger("click"); // "Notify me"
    await flushPromises();
    expect(pushState.subscribe).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem(DISMISS_KEY)).toBeTruthy();
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });

  it("dismiss → does not subscribe and persists the cooldown flag", async () => {
    const w = mountSheet();
    await w.vm.maybeShow();
    await flushPromises();
    const buttons = w.findAll("button");
    await buttons[1].trigger("click"); // "Not now"
    await flushPromises();
    expect(pushState.subscribe).not.toHaveBeenCalled();
    expect(localStorage.getItem(DISMISS_KEY)).toBeTruthy();
    expect(w.find('[role="dialog"]').exists()).toBe(false);
  });
});
