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
    // Replace an existing cart line (identified by oldKey) with a fully
    // re-customized line. Used by the "edit a cart line in place" flow: the
    // QuickAddSheet re-opens seeded with the line's current options/qty/note,
    // and on save we swap the old line for the new one. If the edited line's
    // computed key collides with another existing line (same slug+options+note),
    // the quantities merge — exactly like add() — so editing never produces two
    // identical lines. The replacement preserves the line's position when the
    // key is unchanged; otherwise it lands where add() would put it.
    replaceLine(oldKey, newItem) {
      const normalized = normalizeCartItem(newItem);
      if (!normalized.slug) return;
      const oldIndex = this.items.findIndex((i) => i.key === oldKey);
      if (oldIndex === -1) {
        // Old line vanished (e.g. cleared in another tab) — fall back to add().
        this.add(newItem);
        return;
      }
      // Does the edited line collide with a DIFFERENT existing line?
      const collisionIndex = this.items.findIndex(
        (i, idx) => idx !== oldIndex && i.key === normalized.key,
      );
      if (collisionIndex !== -1) {
        // Merge qty into the colliding line, drop the old line.
        const target = this.items[collisionIndex];
        target.qty = clampQty(target.qty + normalized.qty);
        target.note = normalized.note;
        target.option_ids = normalized.option_ids;
        target.option_labels = normalized.option_labels;
        target.price = normalized.price;
        target.currency = normalized.currency;
        this.items.splice(oldIndex, 1);
      } else {
        // No collision — replace in place, keeping the line's position.
        this.items.splice(oldIndex, 1, normalized);
      }
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
    // ── Express checkout (remember last fulfillment + address + payment) ────────
    // Opt-in, per-host, localStorage-only. When the customer enables express
    // checkout, the last successful order's fulfillment type, delivery address,
    // and payment choice are remembered and pre-applied on the next cart mount
    // so a repeat order is near-1-tap (always fully overridable in the form).
    //
    // BEHAVIOR-PRESERVING: this is DEFAULT OFF. loadExpressCheckout() returns
    // null unless the customer has explicitly turned the toggle on, so an
    // existing customer who never opts in sees exactly today's behavior.
    expressCheckoutStorageKey() {
      return typeof window === "undefined"
        ? "cart:express"
        : `cart:express:${window.location.hostname}`;
    },
    // Read the persisted preference + remembered context.
    // Returns { enabled, fulfillment_type, delivery_address, delivery_lat,
    // delivery_lng, payment_method } or null when storage is empty/unreadable.
    // NOTE: this does NOT gate on `enabled` — callers decide. `enabled` is the
    // source of truth for the toggle's checked state; the apply path checks it.
    readExpressCheckout() {
      try {
        const raw = localStorage.getItem(this.expressCheckoutStorageKey());
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object") return null;
        const ft = String(parsed.fulfillment_type || "");
        const pm = String(parsed.payment_method || "");
        // Guard against Number(null) === 0 — a stored null coord must stay null.
        const num = (v) => (v === null || v === undefined || v === "" ? null
          : Number.isFinite(Number(v)) ? Number(v) : null);
        return {
          enabled: parsed.enabled === true,
          fulfillment_type: ft === "delivery" || ft === "pickup" ? ft : "",
          delivery_address: String(parsed.delivery_address || ""),
          delivery_lat: num(parsed.delivery_lat),
          delivery_lng: num(parsed.delivery_lng),
          payment_method: pm === "wallet" || pm === "cash" ? pm : "",
        };
      } catch {
        return null;
      }
    },
    // Returns the remembered context ONLY when express checkout is enabled,
    // otherwise null. Cart.vue calls this on mount to decide whether to
    // pre-apply — null means "do nothing, preserve today's behavior".
    loadExpressCheckout() {
      const data = this.readExpressCheckout();
      if (!data || !data.enabled) return null;
      return data;
    },
    // Whether the customer has opted into express checkout (toggle state).
    // Returns true when:
    //   (a) the customer explicitly opted in (enabled === true in express store), OR
    //   (b) the customer is returning and has saved fulfillment context in either
    //       the express store or the reorder/fulfillment store — auto-enable so a
    //       repeat order is near-1-tap by default.
    // Returns false only for a true first-ever visitor (no saved context anywhere)
    // so their form stays blank, preserving existing behavior.
    isExpressCheckoutEnabled() {
      const data = this.readExpressCheckout();
      if (data?.enabled === true) return true; // explicit opt-in
      // Check whether there is any saved fulfillment context to auto-apply.
      const hasSavedExpressContext = Boolean(data?.fulfillment_type);
      const hasFulfillmentContext = Boolean(this.loadFulfillmentContext()?.fulfillment_type);
      return hasSavedExpressContext || hasFulfillmentContext;
    },
    // Flip the opt-in toggle, preserving any already-remembered context.
    setExpressCheckoutEnabled(enabled) {
      try {
        const existing = this.readExpressCheckout() || {};
        localStorage.setItem(
          this.expressCheckoutStorageKey(),
          JSON.stringify({
            enabled: enabled === true,
            fulfillment_type: String(existing.fulfillment_type || ""),
            delivery_address: String(existing.delivery_address || ""),
            delivery_lat: existing.delivery_lat === null || existing.delivery_lat === undefined ? null : Number(existing.delivery_lat),
            delivery_lng: existing.delivery_lng === null || existing.delivery_lng === undefined ? null : Number(existing.delivery_lng),
            payment_method: String(existing.payment_method || ""),
          }),
        );
      } catch { /* best-effort */ }
    },
    // Remember the just-placed order's context. Only writes the fulfillment/
    // address/payment fields when express checkout is enabled; if disabled this
    // is a no-op so a non-opted-in customer never accumulates remembered state.
    persistExpressCheckout({ fulfillment_type, delivery_address, delivery_lat, delivery_lng, payment_method }) {
      try {
        const existing = this.readExpressCheckout();
        if (!existing || !existing.enabled) return; // opt-in only
        const ft = String(fulfillment_type || "");
        const pm = String(payment_method || "");
        localStorage.setItem(
          this.expressCheckoutStorageKey(),
          JSON.stringify({
            enabled: true,
            fulfillment_type: ft === "delivery" || ft === "pickup" ? ft : "",
            delivery_address: ft === "delivery" ? String(delivery_address || "") : "",
            delivery_lat: ft === "delivery" && Number.isFinite(Number(delivery_lat)) ? Number(delivery_lat) : null,
            delivery_lng: ft === "delivery" && Number.isFinite(Number(delivery_lng)) ? Number(delivery_lng) : null,
            payment_method: pm === "wallet" || pm === "cash" ? pm : "",
          }),
        );
      } catch { /* best-effort */ }
    },
    // ── Availability-safe reorder (unified code path) ──────────────────────────
    // Given a past order's lines, re-resolve each against the CURRENT menu via
    // POST /api/reorder-resolve/ and add only the still-available lines at their
    // current price (dropping stale options). This is the single source of truth
    // for reorder — both Menu.vue and OrderStatus.vue call it through useReorder.
    //
    // `lines` is an array of past order items in any of the shapes the app stores
    // them (recentOrders entries, server-history items, OrderStatus items):
    //   { slug | dish_slug, name | dish_name, qty, note, option_ids[] | options[] }
    //
    // Returns { added, skipped, priceChanged, ok } so the caller can toast.
    // Network/availability failures degrade gracefully (returns ok:false, adds nothing).
    async reorderFromOrder(lines, apiClient) {
      const normalizedLines = (Array.isArray(lines) ? lines : [])
        .map((raw) => {
          const slug = String(raw?.slug || raw?.dish_slug || "").trim();
          if (!slug) return null;
          // option_ids may be a flat array, or derived from an options snapshot [{id,...}]
          let optionIds = Array.isArray(raw?.option_ids) ? raw.option_ids : [];
          if (!optionIds.length && Array.isArray(raw?.options)) {
            optionIds = raw.options.map((o) => o?.id).filter((v) => v != null);
          }
          // Original snapshot unit price (recentOrders uses `price`, server/OrderStatus
          // history uses `unit_price`) — used only to detect a price change vs. today.
          const origPriceRaw = raw?.price ?? raw?.unit_price;
          const origPrice = Number(origPriceRaw);
          return {
            slug,
            name: String(raw?.name || raw?.dish_name || "").trim(),
            qty: clampQty(raw?.qty ?? 1),
            note: typeof raw?.note === "string" ? raw.note : "",
            orig_price: Number.isFinite(origPrice) ? origPrice : null,
            option_ids: normalizeOptionIds(optionIds),
            // Keep the original option labels so an available line keeps readable
            // option text even though the server only returns price + validity.
            option_labels: Array.isArray(raw?.option_labels)
              ? raw.option_labels
              : (Array.isArray(raw?.options) ? raw.options.map((o) => o?.name).filter(Boolean) : []),
          };
        })
        .filter(Boolean);

      if (!normalizedLines.length) {
        return { added: 0, skipped: [], priceChanged: false, ok: true };
      }

      let resolvedMap = {};
      let anyOptionsDropped = false;
      try {
        const payload = {
          items: normalizedLines.map((l) => ({ slug: l.slug, option_ids: l.option_ids })),
        };
        const { data } = await apiClient.post("/reorder-resolve/", payload);
        anyOptionsDropped = Boolean(data?.any_options_dropped);
        // Build a slug→resolution map. If the same slug appears twice, the
        // resolution is identical (availability + base price are per-dish), so a
        // last-wins map is correct; option validity is recomputed per line below.
        for (const r of Array.isArray(data?.items) ? data.items : []) {
          if (r?.slug) resolvedMap[r.slug] = r;
        }
      } catch {
        // Resolver unreachable — fail safe: add nothing rather than adding stale items.
        return { added: 0, skipped: [], priceChanged: false, ok: false };
      }

      let added = 0;
      let priceChanged = false;
      const skipped = [];
      for (const line of normalizedLines) {
        const res = resolvedMap[line.slug];
        if (!res || !res.available) {
          skipped.push(line.name || line.slug);
          continue;
        }
        const currentPrice = Number(res.current_price);
        const validOptionIds = Array.isArray(res.current_option_ids) ? res.current_option_ids : line.option_ids;
        if (Number.isFinite(currentPrice)) {
          this.add({
            slug: line.slug,
            name: line.name || res.name || line.slug,
            price: currentPrice,
            currency: res.currency || "MAD",
            qty: line.qty,
            note: line.note,
            option_ids: validOptionIds,
            option_labels: line.option_labels,
          });
          added += 1;
          // Detect a price drift vs. the order snapshot (ignores option-only deltas
          // since orig_price already included the original options' price_delta).
          if (line.orig_price != null && Math.abs(line.orig_price - currentPrice) > 0.001) {
            priceChanged = true;
          }
        } else {
          skipped.push(line.name || line.slug);
        }
      }
      if (anyOptionsDropped) priceChanged = true;
      return { added, skipped, priceChanged, ok: true };
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
