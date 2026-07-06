import { defineStore } from "pinia";
import api from "../lib/api";
import { newIdempotencyKey } from "../lib/idempotency";

// ── Constants ────────────────────────────────────────────────────────────────
const QUEUE_STORAGE_KEY = "kepoli.waiterQueue.v1";
const QUEUE_MAX_SIZE = 50;         // drop oldest if the queue grows beyond this
const FLUSH_BASE_DELAY_MS = 1000;  // 1s → 2s → 4s → 8s → 16s (max)
const FLUSH_MAX_DELAY_MS = 16000;

// HTTP status codes that are permanent (don't retry; drop + toast)
const PERMANENT_4XX = new Set([400, 403, 404, 409, 422]);

// ── Status graph helpers (for nextStatusFor) ─────────────────────────────────
const LINEAR_NEXT = {
  pending: "confirmed",
  confirmed: "preparing",
  preparing: "ready",
};

// Next status is fulfillment-type aware:
//  - pickup:  ready → completed (picked up)
//  - delivery: ready → out_for_delivery → completed (delivered)
//  - dine-in: ready (unpaid) is finished by the Settle action, not a plain
//             advance, so return null; a prepaid dine-in ready → completed.
function nextStatusFor(order) {
  if (!order) return null;
  const s = order.status;
  if (s in LINEAR_NEXT) return LINEAR_NEXT[s];
  if (s === "ready") {
    if (order.fulfillment_type === "delivery") return "out_for_delivery";
    if (order.fulfillment_type === "table" && order.payment_status !== "paid") return null;
    return "completed";
  }
  if (s === "out_for_delivery") return "completed";
  return null;
}

// ── localStorage helpers (guard parse + quota) ───────────────────────────────
function _loadQueue() {
  if (typeof window === "undefined" || typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(QUEUE_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const MAX_AGE_MS = 8 * 60 * 60 * 1000;
    const now = Date.now();
    return parsed.filter(
      (e) =>
        e &&
        typeof e.orderId !== "undefined" &&
        typeof e.newStatus === "string" &&
        typeof e.idempotency_key === "string" &&
        (typeof e.queuedAt !== "number" || now - e.queuedAt < MAX_AGE_MS)
    );
  } catch (err) {
    console.warn("[waiterQueue] Failed to load queue from localStorage:", err);
    return [];
  }
}

function _saveQueue(queue) {
  if (typeof window === "undefined" || typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(QUEUE_STORAGE_KEY, JSON.stringify(queue));
  } catch (err) {
    // QuotaExceededError — trim queue and retry once
    console.warn("[waiterQueue] localStorage quota exceeded; trimming queue.", err);
    try {
      const trimmed = queue.slice(-Math.floor(QUEUE_MAX_SIZE / 2));
      localStorage.setItem(QUEUE_STORAGE_KEY, JSON.stringify(trimmed));
    } catch {
      /* give up gracefully */
    }
  }
}

// ── Store ────────────────────────────────────────────────────────────────────
export const useWaiterStore = defineStore("waiter", {
  state: () => ({
    orders: [],
    recentOrders: [],       // recently finished orders (for the waiter's history view)
    recentLoading: false,
    loading: false,
    error: null,
    lastSyncAt: null,          // ISO string of last successful full fetch
    offlineQueue: _loadQueue(), // persisted across refreshes via localStorage
    isSyncing: false,
    isOnline: typeof navigator !== "undefined" ? navigator.onLine : true,
    updatingOrderIds: new Set(),
    lastMarkPaidError: null,   // { detail, code, collected, total } from the last failed markPaid() call
    shiftSummary: null,        // { orders_handled, total_revenue, currency, average_prep_time_minutes, since, period_hours }
    shiftSummaryLoading: false,
    shiftSummaryError: null,
    // Exponential-backoff state (not persisted — resets on page load is fine)
    _flushDelay: FLUSH_BASE_DELAY_MS,
    _flushTimer: null,
    // Optional callbacks set by the page (WaiterPage.vue) so the store can
    // surface permanent errors as toasts without coupling to the UI layer.
    // Shape: { onPermError: (entry, err) => void, onConflict: (entry) => void }
    _flushCallbacks: null,
  }),

  getters: {
    activeOrders: (state) => state.orders,

    pendingCount: (state) => state.orders.filter((o) => o.status === "pending").length,

    byStatus: (state) => {
      const groups = { pending: [], confirmed: [], preparing: [], ready: [] };
      for (const o of state.orders) {
        if (groups[o.status]) groups[o.status].push(o);
      }
      return groups;
    },

    queueLength: (state) => state.offlineQueue.length,

    nextStatus: () => (order) => nextStatusFor(order),

    unpaidOrders: (state) => state.orders.filter((o) => o.payment_status !== "paid"),
  },

  actions: {
    // -------------------------------------------------------
    // Connectivity tracking — call from the layout once
    // -------------------------------------------------------
    setupConnectivityListeners() {
      if (typeof window === "undefined") return;
      window.addEventListener("online", this._onOnline);
      window.addEventListener("offline", this._onOffline);
      // Resume flushing on init (in case we're already online with a persisted queue)
      if (this.isOnline && this.offlineQueue.length) {
        const cbs = this._flushCallbacks || {};
        this.flushQueue({ onPermError: cbs.onPermError, onConflict: cbs.onConflict });
      }
    },

    teardownConnectivityListeners() {
      if (typeof window === "undefined") return;
      window.removeEventListener("online", this._onOnline);
      window.removeEventListener("offline", this._onOffline);
      if (this._flushTimer) {
        clearTimeout(this._flushTimer);
        this._flushTimer = null;
      }
    },

    _onOnline() {
      this.isOnline = true;
      this._flushDelay = FLUSH_BASE_DELAY_MS; // reset backoff on reconnect
      const cbs = this._flushCallbacks || {};
      this.flushQueue({ onPermError: cbs.onPermError, onConflict: cbs.onConflict });
    },

    // Register UI-layer callbacks so the store can surface errors as toasts.
    // Call once from WaiterPage.vue (or any consumer) after store init.
    setFlushCallbacks({ onPermError = null, onConflict = null } = {}) {
      this._flushCallbacks = { onPermError, onConflict };
    },

    _onOffline() {
      this.isOnline = false;
    },

    // -------------------------------------------------------
    // Persist queue to localStorage (call after every mutation)
    // -------------------------------------------------------
    _persistQueue() {
      _saveQueue(this.offlineQueue);
    },

    // -------------------------------------------------------
    // Fetch active orders
    // -------------------------------------------------------
    async fetchOrders({ silent = false } = {}) {
      if (!silent) this.loading = true;
      this.error = null;
      try {
        const res = await api.get("/staff/orders/");
        this.orders = Array.isArray(res.data?.results) ? res.data.results : [];
        this.lastSyncAt = new Date().toISOString();
        return this.orders;
      } catch {
        if (!silent) this.error = "Failed to load orders.";
      } finally {
        if (!silent) this.loading = false;
      }
    },

    // -------------------------------------------------------
    // Recently finished orders (last 24h) — the waiter's history view
    // -------------------------------------------------------
    async fetchRecent() {
      this.recentLoading = true;
      try {
        const res = await api.get("/staff/orders/", { params: { recent: 1 } });
        this.recentOrders = Array.isArray(res.data?.results) ? res.data.results : [];
        return this.recentOrders;
      } catch {
        /* keep last */
      } finally {
        this.recentLoading = false;
      }
    },

    // -------------------------------------------------------
    // Update order status — optimistic, offline-safe
    // -------------------------------------------------------
    async advanceStatus(orderId) {
      const order = this.orders.find((o) => o.id === orderId);
      if (!order) return;

      const next = nextStatusFor(order);
      if (!next) return;

      const prev = order.status;
      // Optimistic update
      order.status = next;
      this.updatingOrderIds = new Set([...this.updatingOrderIds, orderId]);

      if (!this.isOnline) {
        this._enqueue(orderId, next);
        this.updatingOrderIds = new Set([...this.updatingOrderIds].filter((id) => id !== orderId));
        return;
      }

      let success = false;
      try {
        const entry = this.offlineQueue.find((e) => e.orderId === orderId && e.newStatus === next);
        const idemKey = entry?.idempotency_key || newIdempotencyKey();
        await api.patch(`/owner/orders/${orderId}/status/`, {
          status: next,
          idempotency_key: idemKey,
        });
        // On success, remove from active list if completed
        if (next === "completed") {
          this.orders = this.orders.filter((o) => o.id !== orderId);
        }
        success = true;
      } catch {
        // Revert optimistic update and queue for retry
        order.status = prev;
        this._enqueue(orderId, next);
      } finally {
        this.updatingOrderIds = new Set([...this.updatingOrderIds].filter((id) => id !== orderId));
      }
      return success;
    },

    // -------------------------------------------------------
    // Offline queue management
    // -------------------------------------------------------
    _enqueue(orderId, newStatus) {
      // Replace any existing queued update for the same order (newest intent wins)
      const existing = this.offlineQueue.find((e) => e.orderId === orderId);
      const idempotency_key = existing?.idempotency_key || newIdempotencyKey();

      this.offlineQueue = [
        ...this.offlineQueue.filter((e) => e.orderId !== orderId),
        { orderId, newStatus, queuedAt: Date.now(), idempotency_key },
      ];

      // Cap queue size — drop oldest entries if overflow
      if (this.offlineQueue.length > QUEUE_MAX_SIZE) {
        const dropped = this.offlineQueue.splice(0, this.offlineQueue.length - QUEUE_MAX_SIZE);
        console.warn(
          `[waiterQueue] Queue exceeded ${QUEUE_MAX_SIZE} entries; dropped ${dropped.length} oldest ops:`,
          dropped.map((e) => `order=${e.orderId} status=${e.newStatus}`)
        );
      }

      this._persistQueue();
    },

    // -------------------------------------------------------
    // Shift summary
    // -------------------------------------------------------
    async fetchShiftSummary(since = null) {
      this.shiftSummaryLoading = true;
      this.shiftSummaryError = null;
      try {
        const params = since ? { since } : {};
        const res = await api.get("/staff/shift-summary/", { params });
        this.shiftSummary = res.data;
        return res.data;
      } catch {
        this.shiftSummaryError = "Failed to load shift summary.";
      } finally {
        this.shiftSummaryLoading = false;
      }
    },

    // -------------------------------------------------------
    // Settle / mark paid — record cash/card collected. On a READY
    // dine-in order this completes it too (settle & close).
    // Accepts an optional idempotency_key (minted by the caller at button-press
    // time and cleared on confirmed success so the next settle gets a fresh key).
    // -------------------------------------------------------
    // Returns the response payload on success, or null on failure. On failure,
    // the backend `code` (e.g. "payment_short") and detail are stashed on
    // this.lastMarkPaidError so the caller can surface a specific toast —
    // existing callers that only check truthiness of the return value are
    // unaffected.
    async markPaid(orderId, idempotency_key = null) {
      const order = this.orders.find((o) => o.id === orderId);
      if (!order) return null;
      this.updatingOrderIds = new Set([...this.updatingOrderIds, orderId]);
      this.lastMarkPaidError = null;
      try {
        const body = { complete: order.status === "ready" };
        if (idempotency_key) body.idempotency_key = idempotency_key;
        const res = await api.post(`/owner/orders/${orderId}/mark-paid/`, body);
        order.payment_status = res.data.payment_status;
        if (res.data.completed) {
          // Settled & closed — drop from the active list.
          this.orders = this.orders.filter((o) => o.id !== orderId);
        }
        return res.data; // { payment_status, completed, status, ... }
      } catch (err) {
        this.lastMarkPaidError = err?.response?.data ?? null;
        return null;
      } finally {
        this.updatingOrderIds = new Set([...this.updatingOrderIds].filter((id) => id !== orderId));
      }
    },

    // -------------------------------------------------------
    // Partial / full payment via the new payments ledger endpoint.
    // Returns { data, errorCode } — errorCode is the 409 `code` string or null.
    // intentKey: caller-provided idempotency key (minted when the chooser opens so
    // that retries of the same settle attempt reuse the same key and cannot
    // double-record). Falls back to per-call generation when not provided.
    // -------------------------------------------------------
    async postPayment(orderId, method, amount, intentKey = null) {
      this.updatingOrderIds = new Set([...this.updatingOrderIds, orderId]);
      try {
        const body = { method };
        if (amount !== null && amount !== undefined) body.amount = amount;
        // Use caller-supplied key (one-per-settle-intent) when available; otherwise
        // generate a fresh key per call as before.
        body.idempotency_key = intentKey || newIdempotencyKey();
        const res = await api.post(`/staff/orders/${orderId}/payments/`, body);
        // Patch the in-memory order with the updated fields from the response.
        const order = this.orders.find((o) => o.id === orderId);
        if (order && res.data) {
          order.payment_status = res.data.payment_status ?? order.payment_status;
          order.amount_paid = res.data.amount_paid;
          order.outstanding = res.data.outstanding;
          if (res.data.payments) order.payments = res.data.payments;
          if (res.data.completed) {
            this.orders = this.orders.filter((o) => o.id !== orderId);
          }
        }
        return { data: res.data, errorCode: null };
      } catch (err) {
        const code = err?.response?.data?.code ?? null;
        return { data: null, errorCode: code };
      } finally {
        this.updatingOrderIds = new Set([...this.updatingOrderIds].filter((id) => id !== orderId));
      }
    },

    // -------------------------------------------------------
    // Auto-dirty on settle-and-close (Wave 4 — TouchBistro table-turn parity).
    //
    // After a dine-in order settles & closes (drops out of `this.orders`), if no
    // other ACTIVE order remains for the same table_label, PATCH the table to
    // 'dirty' so the floor view tracks the turn without a manual tap. Reuses the
    // existing StaffTableStatusView endpoint (PATCH /staff/tables/<id>/status/).
    //
    // BEHAVIOR-PRESERVING: this is a no-op unless the caller passes both
    //   enabled === true   (owner default; overridable) AND
    //   tableId            (the table is tracked in the table-state feature).
    // Tenants not using the table-state feature have no tableId for the label,
    // so nothing happens and today's behavior is preserved.
    //
    // Returns true only when it actually PATCHed the table to dirty.
    // Never throws — a failed auto-transition must not break the settle flow.
    // -------------------------------------------------------
    async autoDirtyTableIfEmpty(order, { tableId = null, enabled = true } = {}) {
      if (!enabled || !tableId) return false;
      if (!order || order.fulfillment_type !== "table" || !order.table_label) return false;

      const key = order.table_label.trim().toLowerCase();
      // Any remaining active dine-in order for the SAME table keeps it occupied.
      const stillBusy = this.orders.some(
        (o) =>
          o.fulfillment_type === "table" &&
          o.table_label &&
          o.table_label.trim().toLowerCase() === key
      );
      if (stillBusy) return false;

      try {
        await api.patch(`/staff/tables/${tableId}/status/`, { status: "dirty" });
        return true;
      } catch {
        // Best-effort only — the order is already settled; swallow the error.
        return false;
      }
    },

    // -------------------------------------------------------
    // Rate the customer — only the server who handled the order
    // (the backend enforces this via handled_by).
    // -------------------------------------------------------
    async rateCustomer(orderId, score, note = "") {
      await api.post(`/owner/orders/${orderId}/customer-rating/`, { score, note });
      const order = this.orders.find((o) => o.id === orderId);
      if (order) order.my_customer_rating = { score, note };
    },

    // -------------------------------------------------------
    // Item-level kitchen readiness — tick a single line item ready (optimistic).
    // -------------------------------------------------------
    async toggleItemReady(orderId, itemId, ready) {
      const order = this.orders.find((o) => o.id === orderId);
      const item = order?.items?.find((it) => it.id === itemId);
      if (item) item.is_ready = ready; // optimistic
      try {
        await api.patch(`/staff/order-items/${itemId}/ready/`, { ready });
        return true;
      } catch {
        if (item) item.is_ready = !ready; // revert on failure
        return false;
      }
    },

    // -------------------------------------------------------
    // Bulk-ready — mark ALL items on an order ready in one call.
    // Route: POST /api/staff/orders/<id>/items/ready-all/
    // Optimistic: flip every non-voided item to is_ready=true; revert on failure.
    // -------------------------------------------------------
    async bulkItemsReady(orderId) {
      const order = this.orders.find((o) => o.id === orderId);
      if (!order) return false;
      // Optimistic — save previous states so we can revert
      const prev = (order.items || []).map((it) => ({ id: it.id, was: it.is_ready }));
      for (const it of order.items || []) {
        if (!it.is_voided) it.is_ready = true;
      }
      try {
        await api.post(`/staff/orders/${orderId}/items/ready-all/`);
        return true;
      } catch {
        // Revert optimistic changes
        for (const p of prev) {
          const it = order.items?.find((i) => i.id === p.id);
          if (it) it.is_ready = p.was;
        }
        return false;
      }
    },

    // -------------------------------------------------------
    // Flush the offline queue with exponential backoff + error classification.
    //
    // Error classification:
    //   permanent 4xx (400/403/404/409/422) → drop op + call onPermError(entry, err)
    //   409 specifically → also refetch orders (self-heal on conflict)
    //   transient (network/5xx/429) → re-queue + schedule retry with backoff
    //
    // Callers may pass callbacks:
    //   onPermError(entry, err) — called when an op is permanently dropped
    //   onConflict(entry)       — called on 409 (before refetch)
    // -------------------------------------------------------
    async flushQueue({ onPermError = null, onConflict = null } = {}) {
      if (this.isSyncing || !this.offlineQueue.length) return;
      this.isSyncing = true;

      const toFlush = [...this.offlineQueue];
      this.offlineQueue = [];
      this._persistQueue();

      let hadTransient = false;

      try {
        for (const entry of toFlush) {
          try {
            await api.patch(`/owner/orders/${entry.orderId}/status/`, {
              status: entry.newStatus,
              idempotency_key: entry.idempotency_key,
            });
            // Success — update in-memory order
            if (entry.newStatus === "completed") {
              this.orders = this.orders.filter((o) => o.id !== entry.orderId);
            } else {
              const order = this.orders.find((o) => o.id === entry.orderId);
              if (order) order.status = entry.newStatus;
            }
          } catch (err) {
            const status = err?.response?.status;
            const isPermanent = status && PERMANENT_4XX.has(status);

            if (isPermanent) {
              // Permanent error — drop this op; notify caller to show a toast
              console.warn(
                `[waiterQueue] Permanently dropping queued op (HTTP ${status}):`,
                `order=${entry.orderId} status=${entry.newStatus}`
              );
              if (status === 409) {
                // Conflict: another device already advanced — refetch to self-heal
                if (onConflict) onConflict(entry);
                this.fetchOrders({ silent: true }).catch(() => {});
              }
              if (onPermError) onPermError(entry, err);
              // Do NOT re-queue
            } else {
              // Transient error — re-queue with original idempotency key preserved
              this.offlineQueue.push(entry);
              hadTransient = true;
            }
          }
        }
      } finally {
        this._persistQueue();
        this.isSyncing = false;

        // Schedule a retry with exponential backoff if there are transient failures
        if (hadTransient && this.offlineQueue.length && this.isOnline) {
          const delay = this._flushDelay;
          this._flushDelay = Math.min(this._flushDelay * 2, FLUSH_MAX_DELAY_MS);
          if (this._flushTimer) clearTimeout(this._flushTimer);
          this._flushTimer = setTimeout(() => {
            this._flushTimer = null;
            this.flushQueue({ onPermError, onConflict });
          }, delay);
        } else if (!hadTransient) {
          // All succeeded or permanently dropped — reset backoff
          this._flushDelay = FLUSH_BASE_DELAY_MS;
        }
      }
    },
  },
});
