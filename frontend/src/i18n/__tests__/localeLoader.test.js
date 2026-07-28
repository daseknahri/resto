/**
 * Tests for the lazy locale loader (RISK FE-3 residual — the module was untested).
 *
 * The three catalog chunks (messages-en/fr/ar) are dynamically imported, so they're
 * mocked with tiny fixtures. Each test re-imports localeLoader after vi.resetModules()
 * so the module-level `catalog` / `loading` singletons start fresh (isolation).
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

// Shared mutable state referenced inside the (hoisted) vi.mock factories — lets the
// retry/dedup tests make the FR chunk fail on demand and count how often it loads.
const h = vi.hoisted(() => ({ frFail: false, frCalls: 0 }));

vi.mock("../messages-en.js", () => ({
  default: { greeting: "Hello", nested: { a: "A", b: "B" }, list: ["x"] },
}));
vi.mock("../messages-fr.js", () => ({
  get default() {
    h.frCalls += 1;
    if (h.frFail) throw new Error("chunk load failed");
    return { greeting: "Bonjour" };
  },
}));
vi.mock("../messages-ar.js", () => ({
  // "bad" is a corrupted translation (strips to empty) → must be dropped by the merge.
  default: { greeting: "مرحبا", nested: { a: "أ" }, bad: "???" },
}));

async function freshLoader() {
  vi.resetModules();
  return import("../localeLoader.js");
}

beforeEach(() => {
  h.frFail = false;
  h.frCalls = 0;
});

describe("localeLoader.ensureLocale", () => {
  it("loads EN into the catalog", async () => {
    const { ensureLocale, catalog } = await freshLoader();
    expect(catalog.en).toBeUndefined();
    await ensureLocale("en");
    expect(catalog.en.greeting).toBe("Hello");
  });

  it("loads FR into the catalog", async () => {
    const { ensureLocale, catalog } = await freshLoader();
    await ensureLocale("fr");
    expect(catalog.fr.greeting).toBe("Bonjour");
  });

  it("builds AR as EN base + AR overrides, dropping corrupted values", async () => {
    const { ensureLocale, catalog } = await freshLoader();
    await ensureLocale("ar");
    // Overridden by AR:
    expect(catalog.ar.greeting).toBe("مرحبا");
    expect(catalog.ar.nested.a).toBe("أ");
    // Inherited from the EN base (not present in AR):
    expect(catalog.ar.nested.b).toBe("B");
    expect(catalog.ar.list).toEqual(["x"]);
    // Corrupted AR value is dropped, not merged:
    expect(catalog.ar.bad).toBeUndefined();
    // Loading AR also loads EN (needed as the clone base):
    expect(catalog.en.greeting).toBe("Hello");
  });

  it("is a no-op for an unknown locale", async () => {
    const { ensureLocale, catalog } = await freshLoader();
    await expect(ensureLocale("xx")).resolves.toBeUndefined();
    expect(catalog.xx).toBeUndefined();
  });

  it("dedupes concurrent loads of the same locale (loads the chunk once)", async () => {
    const { ensureLocale, catalog } = await freshLoader();
    await Promise.all([ensureLocale("fr"), ensureLocale("fr")]);
    expect(catalog.fr.greeting).toBe("Bonjour");
    expect(h.frCalls).toBe(1);
  });

  it("evicts the in-flight entry on failure so a later call retries", async () => {
    const { ensureLocale, catalog } = await freshLoader();
    h.frFail = true;
    await expect(ensureLocale("fr")).rejects.toThrow("chunk load failed");
    expect(catalog.fr).toBeUndefined();
    // A retry after the (transient) failure clears — the chunk is fetched again.
    h.frFail = false;
    await ensureLocale("fr");
    expect(catalog.fr.greeting).toBe("Bonjour");
    expect(h.frCalls).toBe(2); // failed attempt + successful retry (not a replayed reject)
  });
});

describe("localeLoader.getMessages", () => {
  it("returns the requested locale's catalog when loaded", async () => {
    const { ensureLocale, getMessages } = await freshLoader();
    await ensureLocale("fr");
    expect(getMessages("fr").greeting).toBe("Bonjour");
  });

  it("falls back to EN (DEFAULT_LOCALE) for a locale that isn't loaded", async () => {
    const { ensureLocale, getMessages } = await freshLoader();
    await ensureLocale("en");
    expect(getMessages("fr").greeting).toBe("Hello"); // fr not loaded → EN fallback
    expect(getMessages("xx").greeting).toBe("Hello"); // unknown → EN fallback
  });
});
