/**
 * Unit tests for useOwnerTheme
 *
 * Covers: default scheme, persistence, attribute application/clearing, toggle,
 * invalid-input guarding, and the route-aware primeOwnerTheme pre-paint.
 *
 * The composable keeps a module-level singleton ref (so every owner component
 * shares one source of truth), so each test reloads the module fresh via
 * vi.resetModules() to get a clean initial read of localStorage.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

const ATTR = "data-owner-theme";
const KEY = "owner-theme";

const load = async () => {
  vi.resetModules();
  return import("../useOwnerTheme");
};

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute(ATTR);
});

describe("useOwnerTheme", () => {
  it("defaults to dark when nothing is stored", async () => {
    const { useOwnerTheme } = await load();
    expect(useOwnerTheme().theme.value).toBe("dark");
  });

  it("reads a previously stored scheme on load", async () => {
    localStorage.setItem(KEY, "light");
    const { useOwnerTheme } = await load();
    expect(useOwnerTheme().theme.value).toBe("light");
  });

  it("falls back to dark for an invalid stored value", async () => {
    localStorage.setItem(KEY, "neon");
    const { useOwnerTheme } = await load();
    expect(useOwnerTheme().theme.value).toBe("dark");
  });

  it("setTheme persists the choice and paints the html attribute", async () => {
    const { useOwnerTheme } = await load();
    const { theme, setTheme } = useOwnerTheme();
    setTheme("light");
    expect(theme.value).toBe("light");
    expect(localStorage.getItem(KEY)).toBe("light");
    expect(document.documentElement.getAttribute(ATTR)).toBe("light");
  });

  it("setTheme ignores invalid values", async () => {
    const { useOwnerTheme } = await load();
    const { theme, setTheme } = useOwnerTheme();
    setTheme("light");
    setTheme("rainbow");
    expect(theme.value).toBe("light");
  });

  it("toggleTheme flips between dark and light", async () => {
    const { useOwnerTheme } = await load();
    const { theme, toggleTheme } = useOwnerTheme();
    expect(theme.value).toBe("dark");
    toggleTheme();
    expect(theme.value).toBe("light");
    toggleTheme();
    expect(theme.value).toBe("dark");
  });

  it("activate paints the current scheme, deactivate strips the attribute", async () => {
    localStorage.setItem(KEY, "light");
    const { useOwnerTheme } = await load();
    const { activate, deactivate } = useOwnerTheme();
    activate();
    expect(document.documentElement.getAttribute(ATTR)).toBe("light");
    deactivate();
    expect(document.documentElement.hasAttribute(ATTR)).toBe(false);
  });

  it("primeOwnerTheme paints only on owner routes", async () => {
    localStorage.setItem(KEY, "light");
    const { primeOwnerTheme } = await load();

    primeOwnerTheme("/menu/burger");
    expect(document.documentElement.hasAttribute(ATTR)).toBe(false);

    primeOwnerTheme("/owner/orders");
    expect(document.documentElement.getAttribute(ATTR)).toBe("light");
  });

  it("primeOwnerTheme tolerates a missing/non-string path", async () => {
    const { primeOwnerTheme } = await load();
    expect(() => primeOwnerTheme()).not.toThrow();
    expect(() => primeOwnerTheme(undefined)).not.toThrow();
    expect(document.documentElement.hasAttribute(ATTR)).toBe(false);
  });
});
