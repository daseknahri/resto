/**
 * Unit tests for useCurrencyStore
 *
 * Covers currency selection/persistence, MAD->display conversion, the derived
 * selectedRate/selectedSymbol getters, price formatting (incl. the Intl
 * fallback path), and fetchRates (merge-over-fallbacks, stale-selection reset,
 * failure resilience, and the loading re-entrancy guard).
 *
 * Mock-based, so it runs under CI's vitest without a network or backend.
 *
 * Trap (see currency.js): `selected` is read from localStorage AT STORE
 * CREATION. Tests that need a pre-selected code set localStorage BEFORE calling
 * useCurrencyStore(); beforeEach clears it. jsdom (vite.config test env)
 * provides localStorage. The store hits the GLOBAL fetch (not lib/api), so we
 * stub it with vi.stubGlobal and unstub in afterEach.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useCurrencyStore } from "../currency";

const okJson = (payload) => ({ ok: true, json: () => Promise.resolve(payload) });

let fetchMock;

beforeEach(() => {
  localStorage.clear();
  setActivePinia(createPinia());
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  // fetchRates() console.warns on failure — keep the test output clean.
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("useCurrencyStore — initialization", () => {
  it("reads the selected code from localStorage at store creation", () => {
    localStorage.setItem("pref_currency", "EUR");
    const store = useCurrencyStore();
    expect(store.selected).toBe("EUR");
  });

  it("defaults to MAD when nothing is stored", () => {
    const store = useCurrencyStore();
    expect(store.selected).toBe("MAD");
  });
});

describe("useCurrencyStore — setCode", () => {
  it("ignores an unknown code (no state change, nothing persisted)", () => {
    const store = useCurrencyStore();
    store.setCode("XXX");
    expect(store.selected).toBe("MAD");
    expect(localStorage.getItem("pref_currency")).toBeNull();
  });

  it("sets and persists a known code to localStorage", () => {
    const store = useCurrencyStore();
    store.setCode("EUR");
    expect(store.selected).toBe("EUR");
    expect(localStorage.getItem("pref_currency")).toBe("EUR");
  });
});

describe("useCurrencyStore — convert", () => {
  it("returns the MAD amount unchanged when MAD is selected", () => {
    const store = useCurrencyStore();
    expect(store.selected).toBe("MAD");
    expect(store.convert(100)).toBe(100);
  });

  it("divides by mad_per_unit for a non-base currency (EUR 10.9 -> 1)", () => {
    const store = useCurrencyStore();
    store.selected = "EUR"; // mad_per_unit 10.9
    expect(store.convert(10.9)).toBe(1);
  });

  it("coerces a numeric string via Number(...) and converts it", () => {
    const store = useCurrencyStore();
    store.selected = "EUR";
    expect(store.convert("21.8")).toBe(2);
  });

  it("coerces garbage input to 0 (Number(...) || 0)", () => {
    const store = useCurrencyStore();
    store.selected = "EUR";
    expect(store.convert("not-a-number")).toBe(0);
    expect(store.convert(undefined)).toBe(0);
  });

  it("returns the amount unchanged for a missing or zero-rate currency", () => {
    const store = useCurrencyStore();
    // Missing: selected code not present in rates at all.
    store.selected = "GBP";
    expect(store.convert(50)).toBe(50);
    // Zero rate: present but mad_per_unit is falsy (0).
    store.rates = {
      ...store.rates,
      ZER: { code: "ZER", name: "Zero", symbol: "Z", mad_per_unit: 0 },
    };
    store.selected = "ZER";
    expect(store.convert(50)).toBe(50);
  });
});

describe("useCurrencyStore — selectedRate & selectedSymbol", () => {
  it("reflect the currently selected code", () => {
    const store = useCurrencyStore();
    store.selected = "EUR";
    expect(store.selectedRate.code).toBe("EUR");
    expect(store.selectedSymbol).toBe("€");
  });

  it("fall back to the MAD rate and its symbol when the selected code is absent", () => {
    const store = useCurrencyStore();
    store.selected = "ZZZ"; // not in rates
    expect(store.selectedRate.code).toBe("MAD");
    // MAD fallback symbol is "د.م." — compare against the source of truth
    // rather than re-typing the RTL literal.
    expect(store.selectedSymbol).toBe(store.rates.MAD.symbol);
  });
});

describe("useCurrencyStore — available", () => {
  it("returns the list of rate objects", () => {
    const store = useCurrencyStore();
    expect(Array.isArray(store.available)).toBe(true);
    expect(store.available).toHaveLength(4);
    const codes = store.available.map((r) => r.code);
    expect(codes).toEqual(expect.arrayContaining(["MAD", "EUR", "SAR", "AED"]));
  });
});

describe("useCurrencyStore — formatPrice", () => {
  it("renders a 2-decimal currency string for MAD (en locale)", () => {
    const store = useCurrencyStore();
    // en/MAD -> "MAD 12.50"; assert the digits, not the symbol placement.
    expect(store.formatPrice(12.5, "en")).toContain("12.50");
  });

  it("renders a 2-decimal string for a converted currency (en locale)", () => {
    const store = useCurrencyStore();
    store.selected = "EUR"; // convert(10.9) -> 1
    expect(store.formatPrice(10.9, "en")).toContain("1.00");
  });

  it("uses the `${symbol}${converted.toFixed(2)}` fallback when Intl rejects the code", () => {
    const store = useCurrencyStore();
    // A 6-letter code is not a well-formed ISO-4217 currency, so
    // Intl.NumberFormat throws RangeError and the catch branch runs.
    store.rates = {
      ...store.rates,
      BADCUR: { code: "BADCUR", name: "Bad", symbol: "@", mad_per_unit: 2 },
    };
    store.selected = "BADCUR";
    // convert(10) -> 10 / 2 = 5 -> "@5.00"
    expect(store.formatPrice(10, "en")).toBe("@5.00");
  });
});

describe("useCurrencyStore — fetchRates", () => {
  it("merges API rates over the fallbacks, keeps every fallback selectable, sets hydrated", async () => {
    fetchMock.mockResolvedValueOnce(
      okJson([
        { code: "MAD", name: "Dirham", symbol: "د.م.", mad_per_unit: 1 },
        { code: "EUR", name: "Euro", symbol: "€", mad_per_unit: 11.5 }, // overrides fallback 10.9
        { code: "USD", name: "Dollar", symbol: "$", mad_per_unit: 9.8 }, // new currency
      ])
    );
    const store = useCurrencyStore();
    expect(store.hydrated).toBe(false);

    await store.fetchRates();

    expect(store.hydrated).toBe(true);
    expect(store.loading).toBe(false);
    expect(store.rates.EUR.mad_per_unit).toBe(11.5); // API overrode fallback
    expect(store.rates.USD).toBeTruthy(); // new currency added
    // Fallback currencies absent from the API payload remain selectable.
    expect(store.rates.SAR).toBeTruthy();
    expect(store.rates.AED).toBeTruthy();
    // A still-valid selection is left alone.
    expect(store.selected).toBe("MAD");
  });

  it("resets the selection to MAD (and persists) when the stored code is absent after the merge", async () => {
    localStorage.setItem("pref_currency", "USD"); // stale: not a fallback currency
    const store = useCurrencyStore();
    expect(store.selected).toBe("USD"); // picked up from storage at creation

    // API returns only MAD, so after merge rates = fallbacks (MAD/EUR/SAR/AED); no USD.
    fetchMock.mockResolvedValueOnce(
      okJson([{ code: "MAD", name: "Dirham", symbol: "د.م.", mad_per_unit: 1 }])
    );

    await store.fetchRates();

    expect(store.selected).toBe("MAD");
    expect(localStorage.getItem("pref_currency")).toBe("MAD");
  });

  it("keeps the fallback rates and sets hydrated when the response is not ok (no throw)", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 500 });
    const store = useCurrencyStore();

    await expect(store.fetchRates()).resolves.toBeUndefined();

    expect(store.hydrated).toBe(true);
    expect(store.loading).toBe(false);
    expect(store.rates.EUR.mad_per_unit).toBe(10.9); // untouched fallback
    expect(Object.keys(store.rates).sort()).toEqual(["AED", "EUR", "MAD", "SAR"]);
  });

  it("keeps the fallback rates and sets hydrated when fetch rejects (no throw)", async () => {
    fetchMock.mockRejectedValueOnce(new Error("network down"));
    const store = useCurrencyStore();

    await expect(store.fetchRates()).resolves.toBeUndefined();

    expect(store.hydrated).toBe(true);
    expect(store.loading).toBe(false);
    expect(store.rates.EUR.mad_per_unit).toBe(10.9);
  });

  it("returns immediately without fetching when a call is already loading (re-entrancy guard)", async () => {
    const store = useCurrencyStore();
    store.loading = true; // simulate an in-flight call

    await store.fetchRates();

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
