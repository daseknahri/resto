import { defineStore } from "pinia";

const clampQty = (value) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 1) return 1;
  if (parsed > 99) return 99;
  return Math.floor(parsed);
};

const normalizeOptionIds = (value) =>
  Array.isArray(value)
    ? [...new Set(value.map((v) => Number(v)).filter((v) => Number.isInteger(v) && v > 0))].sort((a, b) => a - b)
    : [];

const normalizedLineKey = (item) => {
  if (typeof item?.key === "string" && item.key.trim()) return item.key.trim();
  const slug = (item?.slug || "").trim() || "item";
  const optionSig = normalizeOptionIds(item?.option_ids).join(",");
  const noteSig = typeof item?.note === "string" ? item.note.trim().toLowerCase() : "";
  return `${slug}::${optionSig}::${noteSig}`;
};

const normalizeCartItem = (item) => ({
  key: normalizedLineKey(item),
  slug: String(item?.slug || "").trim(),
  name: String(item?.name || "").trim() || "Item",
  price: Number(item?.price || 0),
  currency: String(item?.currency || "USD").trim().toUpperCase() || "USD",
  qty: clampQty(item?.qty ?? 1),
  note: typeof item?.note === "string" ? item.note.trim() : "",
  option_ids: normalizeOptionIds(item?.option_ids),
  option_labels: Array.isArray(item?.option_labels) ? item.option_labels.map((x) => String(x)).filter(Boolean) : [],
});

const loadStoredCartItems = () => {
  if (typeof window === "undefined" || typeof localStorage === "undefined") return [];
  try {
    const raw = JSON.parse(localStorage.getItem(cartStorageKey()) || "[]");
    if (!Array.isArray(raw)) return [];
    return raw.map(normalizeCartItem).filter((item) => item.slug);
  } catch {
    return [];
  }
};

const tableLabelStorageKey = () =>
  typeof window === "undefined" ? "cart:table" : `cart:table:${window.location.hostname}`;
const tableSlugStorageKey = () =>
  typeof window === "undefined" ? "cart:table-slug" : `cart:table-slug:${window.location.hostname}`;
const customerNameStorageKey = () =>
  typeof window === "undefined" ? "cart:customer-name" : `cart:customer-name:${window.location.hostname}`;
const customerPhoneStorageKey = () =>
  typeof window === "undefined" ? "cart:customer-phone" : `cart:customer-phone:${window.location.hostname}`;

const cartStorageKey = () => (typeof window === "undefined" ? "cart" : `cart:${window.location.hostname}`);

const sanitizeTableLabel = (value) =>
  String(value || "")
    .replace(/[^\w\s\-#]/g, "")
    .trim()
    .slice(0, 40);
const sanitizeTableSlug = (value) =>
  String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, "")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 55);

const sanitizeCustomerName = (value) =>
  String(value || "")
    .replace(/[^A-Za-z0-9\s\-'.]/g, "")
    .trim()
    .slice(0, 80);

const sanitizeCustomerPhone = (value) =>
  String(value || "")
    .replace(/[^0-9+\-\s()]/g, "")
    .trim()
    .slice(0, 30);

const loadStoredTableLabel = () => {
  if (typeof window === "undefined" || typeof localStorage === "undefined") return "";
  try {
    return sanitizeTableLabel(localStorage.getItem(tableLabelStorageKey()) || "");
  } catch {
    return "";
  }
};
const loadStoredTableSlug = () => {
  if (typeof window === "undefined" || typeof localStorage === "undefined") return "";
  try {
    return sanitizeTableSlug(localStorage.getItem(tableSlugStorageKey()) || "");
  } catch {
    return "";
  }
};

const loadStoredCustomerName = () => {
  if (typeof window === "undefined" || typeof localStorage === "undefined") return "";
  try {
    return sanitizeCustomerName(localStorage.getItem(customerNameStorageKey()) || "");
  } catch {
    return "";
  }
};

const loadStoredCustomerPhone = () => {
  if (typeof window === "undefined" || typeof localStorage === "undefined") return "";
  try {
    return sanitizeCustomerPhone(localStorage.getItem(customerPhoneStorageKey()) || "");
  } catch {
    return "";
  }
};

export const useCartStore = defineStore("cart", {
  state: () => ({
    items: loadStoredCartItems(),
    tableLabel: loadStoredTableLabel(),
    tableSlug: loadStoredTableSlug(),
    customerName: loadStoredCustomerName(),
    customerPhone: loadStoredCustomerPhone(),
    canCheckout: false,
    canWhatsapp: false,
  }),
  getters: {
    total(state) {
      return state.items.reduce((sum, item) => sum + item.price * item.qty, 0);
    },
    count(state) {
      return state.items.reduce((sum, item) => sum + item.qty, 0);
    },
  },
  actions: {
    setCanCheckout(value) {
      this.canCheckout = value;
    },
    setCanWhatsapp(value) {
      this.canWhatsapp = value;
    },
    persist() {
      localStorage.setItem(cartStorageKey(), JSON.stringify(this.items));
    },
    persistTableLabel() {
      const normalized = sanitizeTableLabel(this.tableLabel);
      this.tableLabel = normalized;
      localStorage.setItem(tableLabelStorageKey(), normalized);
    },
    persistTableSlug() {
      const normalized = sanitizeTableSlug(this.tableSlug);
      this.tableSlug = normalized;
      localStorage.setItem(tableSlugStorageKey(), normalized);
    },
    setTableLabel(value) {
      this.tableLabel = sanitizeTableLabel(value);
      this.tableSlug = "";
      this.persistTableLabel();
      this.persistTableSlug();
    },
    setTableSlug(value) {
      this.tableSlug = sanitizeTableSlug(value);
      this.persistTableSlug();
    },
    setTableContext(label, slug = "") {
      this.tableLabel = sanitizeTableLabel(label);
      this.tableSlug = sanitizeTableSlug(slug);
      this.persistTableLabel();
      this.persistTableSlug();
    },
    clearTableLabel() {
      this.tableLabel = "";
      this.tableSlug = "";
      this.persistTableLabel();
      this.persistTableSlug();
    },
    clearTableContext() {
      this.tableLabel = "";
      this.tableSlug = "";
      this.persistTableLabel();
      this.persistTableSlug();
    },
    persistCustomer() {
      this.customerName = sanitizeCustomerName(this.customerName);
      this.customerPhone = sanitizeCustomerPhone(this.customerPhone);
      localStorage.setItem(customerNameStorageKey(), this.customerName);
      localStorage.setItem(customerPhoneStorageKey(), this.customerPhone);
    },
    setCustomerName(value) {
      this.customerName = sanitizeCustomerName(value);
      this.persistCustomer();
    },
    setCustomerPhone(value) {
      this.customerPhone = sanitizeCustomerPhone(value);
      this.persistCustomer();
    },
    clearCustomer() {
      this.customerName = "";
      this.customerPhone = "";
      this.persistCustomer();
    },
    add(item) {
      const normalized = normalizeCartItem(item);
      if (!normalized.slug) return;
      const existing = this.items.find((i) => i.key === normalized.key);
      if (existing) {
        existing.qty = clampQty(existing.qty + normalized.qty);
        if (normalized.note) existing.note = normalized.note;
        if (normalized.option_ids.length) existing.option_ids = normalized.option_ids;
        if (normalized.option_labels.length) existing.option_labels = normalized.option_labels;
        existing.price = normalized.price;
        existing.currency = normalized.currency;
      } else {
        this.items.push(normalized);
      }
      this.persist();
    },
    setQty(lineKey, qty) {
      const existing = this.items.find((i) => i.key === lineKey);
      if (!existing) return;
      existing.qty = clampQty(qty);
      this.persist();
    },
    increment(lineKey) {
      const existing = this.items.find((i) => i.key === lineKey);
      if (!existing) return;
      existing.qty = clampQty(existing.qty + 1);
      this.persist();
    },
    decrement(lineKey) {
      const existing = this.items.find((i) => i.key === lineKey);
      if (!existing) return;
      if (existing.qty <= 1) {
        this.remove(lineKey);
        return;
      }
      existing.qty = clampQty(existing.qty - 1);
      this.persist();
    },
    remove(lineKey) {
      this.items = this.items.filter((i) => i.key !== lineKey);
      this.persist();
    },
    clear() {
      this.items = [];
      this.persist();
    },
  },
});
