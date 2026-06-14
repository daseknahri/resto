/**
 * Unit test for SPA route-change focus management (WCAG 2.4.3).
 *
 * Verifies the afterEach guard returned by createMainContentFocusGuard:
 *   - is a no-op on the very first navigation (cold load), and
 *   - focuses #main-content on a subsequent client-side navigation.
 *
 * Note: jsdom focus testing can be flaky, so we assert against a spy on the
 * element's focus() rather than document.activeElement. The guard factory lives
 * in its own module (no router/store graph), so we drive it directly with the
 * START_LOCATION / route-like objects it receives from vue-router.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { nextTick } from "vue";
import { START_LOCATION } from "vue-router";
import { createMainContentFocusGuard } from "../focusGuard.js";

describe("createMainContentFocusGuard (WCAG 2.4.3 route-change focus)", () => {
  let main;

  beforeEach(() => {
    main = document.createElement("main");
    main.id = "main-content";
    main.setAttribute("tabindex", "-1");
    document.body.appendChild(main);
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.restoreAllMocks();
  });

  it("is a no-op on the initial navigation (from === START_LOCATION)", async () => {
    const guard = createMainContentFocusGuard();
    const spy = vi.spyOn(main, "focus");

    guard({ name: "home", path: "/" }, START_LOCATION);
    await nextTick();

    expect(spy).not.toHaveBeenCalled();
  });

  it("focuses #main-content on a non-initial navigation", async () => {
    const guard = createMainContentFocusGuard();
    const spy = vi.spyOn(main, "focus");

    guard({ name: "cart", path: "/cart" }, { name: "home", path: "/" });
    await nextTick();

    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith({ preventScroll: true });
  });

  it("does not steal focus from an open dialog", async () => {
    const dialog = document.createElement("div");
    dialog.setAttribute("role", "dialog");
    const btn = document.createElement("button");
    dialog.appendChild(btn);
    document.body.appendChild(dialog);
    btn.focus();

    const guard = createMainContentFocusGuard();
    const spy = vi.spyOn(main, "focus");

    guard({ name: "cart", path: "/cart" }, { name: "home", path: "/" });
    await nextTick();

    expect(spy).not.toHaveBeenCalled();
  });

  it("is a no-op when #main-content is absent (defensive)", async () => {
    document.body.innerHTML = "";
    const guard = createMainContentFocusGuard();

    // Should not throw even though there is no main region to focus.
    expect(() => guard({ name: "cart", path: "/cart" }, { name: "home", path: "/" })).not.toThrow();
    await nextTick();
  });
});
