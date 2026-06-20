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
  currency: String(item?.currency || "MAD").trim().toUpperCase() || "MAD",
  qty: clampQty(item?.qty ?? 1),
  note: typeof item?.note === "string" ? item.note.trim() : "",
  option_ids: normalizeOptionIds(item?.option_ids),
  option_labels: Array.isArray(item?.option_labels) ? item.option_labels.map((x) => String(x)).filter(Boolean) : [],
  // "HH:MM" end-of-window if this line was priced during a happy hour, null otherwise.
  // Used at checkout to detect stale happy-hour prices after the window closes.
  happy_hour_ends_at: typeof item?.happy_hour_ends_at === "string" ? item.happy_hour_ends_at : null,
  // "HH:MM" start-of-window — stored so the stale-price guard can distinguish
  // overnight windows (starts_at > ends_at) from normal windows (starts_at < ends_at).
  happy_hour_starts_at: typeof item?.happy_hour_starts_at === "string" ? item.happy_hour_starts_at : null,
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
const recentOrdersStorageKey = () => (typeof window === "undefined" ? "cart:recent-orders" : `cart:recent-orders:${window.location.hostname}`);

const loadRecentOrders = () => {
  if (typeof window === "undefined" || typeof localStorage === "undefined") return [];
  try {
    const raw = JSON.parse(localStorage.getItem(recentOrdersStorageKey()) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
};

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
    recentOrders: loadRecentOrders(),
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
    // Restore fulfillment context from a previous order (used by reorder flow).
    // Consumers (Cart.vue) read fulfillment_type / delivery* from their own refs;
    // this stores it in localStorage so Cart.vue can re-hydrate on mount.
    persistFulfillmentContext({ fulfillment_type, delivery_address, delivery_lat, delivery_lng }) {
      try {
        const key = typeof window === "undefined" ? "cart:fulfillment" : `cart:fulfillment:${window.location.hostname}`;
        localStorage.setItem(key, JSON.stringify({
          fulfillment_type: String(fulfillment_type || ""),
          delivery_address: String(delivery_address || ""),
          delivery_lat: Number.isFinite(Number(delivery_lat)) ? Number(delivery_lat) : null,
          delivery_lng: Number.isFinite(Number(delivery_lng)) ? Number(delivery_lng) : null,
        }));
      } catch { /* best-effort */ }
    },
    loadFulfillmentContext() {
      try {
        const key = typeof window === "undefined" ? "cart:fulfillment" : `cart:fulfillment:${window.location.hostname}`;
        const raw = localStorage.getItem(key);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object") return null;
        return {
          fulfillment_type: String(parsed.fulfillment_type || ""),
          delivery_address: String(parsed.delivery_address || ""),
          delivery_lat: Number.isFinite(Number(parsed.delivery_lat)) ? Number(parsed.delivery_lat) : null,
          delivery_lng: Number.isFinite(Number(parsed.delivery_lng)) ? Number(parsed.delivery_lng) : null,
        };
      } catch { return null; }
    },
    // Save a completed order to the recent-orders list (max 5, deduplicated by order_number).
    // Call this BEFORE clearing the cart, passing the API response + current cart items.
    pushRecentOrder({ order_number, total, currency, created_at, items, fulfillment_type, delivery_address, delivery_lat, delivery_lng }) {
      const entry = {
        order_number: String(order_number || ""),
        total: Number(total || 0),
        currency: String(currency || "MAD"),
        created_at: created_at || new Date().toISOString(),
        fulfillment_type: typeof fulfillment_type === "string" ? fulfillment_type : "",
        delivery_address: typeof delivery_address === "string" ? delivery_address.trim() : "",
        delivery_lat: Number.isFinite(Number(delivery_lat)) ? Number(delivery_lat) : null,
        delivery_lng: Number.isFinite(Number(delivery_lng)) ? Number(delivery_lng) : null,
        items: Array.isArray(items)
          ? items.map((item) => ({
              key: item.key || `${item.slug}::`,
              slug: String(item.slug || ""),
              name: String(item.name || ""),
              price: Number(item.price || 0),
              currency: String(item.currency || currency || "MAD"),
              qty: Number(item.qty || 1),
              note: String(item.note || ""),
              option_ids: Array.isArray(item.option_ids) ? item.option_ids : [],
              option_labels: Array.isArray(item.option_labels) ? item.option_labels : [],
            }))
          : [],
      };
      // Remove duplicate if same order was already saved, then prepend
      this.recentOrders = [entry, ...this.recentOrders.filter((r) => r.order_number !== entry.order_number)].slice(0, 5);
      try {
        localStorage.setItem(recentOrdersStorageKey(), JSON.stringify(this.recentOrders));
      } catch { /* storage full — ignore */ }
    },
  },
});
