/**
 * Currency store
 * ==============
 * Fetches exchange rates from /api/currency-rates/ (base: MAD).
 * Lets the customer pick a display currency; converts prices on the fly.
 *
 * All prices in the system are stored in MAD.
 * To display in another currency: display = mad_amount / mad_per_unit
 */
import { computed, ref } from "vue";
import { defineStore } from "pinia";

const STORAGE_KEY = "pref_currency";
const BASE_CODE = "MAD";

/** Fallback rates used before the API responds (or if it fails). */
const FALLBACK_RATES = [
  { code: "MAD", name: "Dirham", symbol: "د.م.", mad_per_unit: 1 },
  { code: "EUR", name: "Euro",   symbol: "€",    mad_per_unit: 10.9 },
  { code: "SAR", name: "Riyal",  symbol: "﷼",    mad_per_unit: 2.61 },
  { code: "AED", name: "Dirham (UAE)", symbol: "د.إ", mad_per_unit: 2.67 },
];

export const useCurrencyStore = defineStore("currency", () => {
  /** ISO 4217 code of the currently selected display currency */
  const selected = ref(localStorage.getItem(STORAGE_KEY) || BASE_CODE);

  /** Map of code → { code, name, symbol, mad_per_unit } */
  const rates = ref(
    Object.fromEntries(FALLBACK_RATES.map((r) => [r.code, r]))
  );

  const loading = ref(false);
  const hydrated = ref(false);

  // ── Derived ───────────────────────────────────────────────────────────────

  /** Ordered list of available currencies for the selector UI */
  const available = computed(() => Object.values(rates.value));

  const selectedRate = computed(() => rates.value[selected.value] ?? rates.value[BASE_CODE]);

  const selectedSymbol = computed(() => selectedRate.value?.symbol ?? "د.م.");

  // ── Actions ───────────────────────────────────────────────────────────────

  function setCode(code) {
    if (!rates.value[code]) return;
    selected.value = code;
    localStorage.setItem(STORAGE_KEY, code);
  }

  /**
   * Convert a MAD amount to the selected display currency.
   * Returns a plain number (not formatted).
   */
  function convert(madAmount) {
    const amount = Number(madAmount) || 0;
    if (selected.value === BASE_CODE) return amount;
    const rate = rates.value[selected.value];
    if (!rate || !rate.mad_per_unit) return amount;
    return amount / rate.mad_per_unit;
  }

  /**
   * Format a MAD price for display in the selected currency.
   * locale: BCP-47 locale string (e.g. "fr", "ar", "en")
   */
  function formatPrice(madAmount, locale = "en") {
    const converted = convert(madAmount);
    const code = selected.value;
    const isMAD = code === BASE_CODE;
    try {
      return new Intl.NumberFormat(locale, {
        style: "currency",
        currency: code,
        minimumFractionDigits: isMAD ? 0 : 2,
        maximumFractionDigits: isMAD ? 0 : 2,
      }).format(converted);
    } catch {
      // Intl.NumberFormat doesn't know some symbols — fall back gracefully
      const sym = selectedSymbol.value;
      return `${sym}${converted.toFixed(isMAD ? 0 : 2)}`;
    }
  }

  /** Fetch live rates from the backend. Safe to call multiple times. */
  async function fetchRates() {
    if (loading.value) return;
    loading.value = true;
    try {
      const res = await fetch("/api/currency-rates/");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const map = {};
      for (const item of data) {
        map[item.code] = item;
      }
      if (Object.keys(map).length) {
        rates.value = map;
      }
      // If the previously stored currency is no longer active, reset to MAD
      if (!rates.value[selected.value]) {
        selected.value = BASE_CODE;
        localStorage.setItem(STORAGE_KEY, BASE_CODE);
      }
      hydrated.value = true;
    } catch (err) {
      console.warn("[CurrencyStore] rate fetch failed, using fallback rates.", err);
      hydrated.value = true;
    } finally {
      loading.value = false;
    }
  }

  return {
    selected,
    rates,
    available,
    loading,
    hydrated,
    selectedRate,
    selectedSymbol,
    setCode,
    convert,
    formatPrice,
    fetchRates,
  };
});
