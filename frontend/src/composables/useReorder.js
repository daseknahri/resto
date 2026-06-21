// useReorder — the single, unified reorder spine for the customer apps.
//
// WHY: reorder was implemented three times (Menu.vue reorderItems, the Menu
// recent-orders list button, and OrderStatus.vue reorder) with subtly different,
// localStorage-sourced, NON-availability-safe logic. A daily reorder could silently
// add a sold-out or re-priced item that only failed at checkout.
//
// WHAT: every call site now funnels through `reorderFromOrder`, which:
//   1. re-resolves each past line against the CURRENT menu via the cart store's
//      `reorderFromOrder` action (POST /api/reorder-resolve/ — same availability +
//      pricing rules as checkout), dropping unavailable items and stale options and
//      refreshing prices, so the user lands in an already-valid cart;
//   2. restores the order's fulfillment context (delivery address / type / coords),
//      falling back to pickup when delivery is no longer offered;
//   3. surfaces one contextual toast (added / some-skipped / all-unavailable /
//      price-updated) instead of three ad-hoc messages.
//
// It is ALSO the place that makes reorder SERVER-history sourced: `hydrateServerHistory`
// pulls the signed-in customer's account-bound order history and merges it into
// cart.recentOrders, so "Order again" survives a device switch / cleared storage —
// not just the localStorage list written at checkout time.

import api from "../lib/api";
import { useCartStore } from "../stores/cart";
import { useToastStore } from "../stores/toast";
import { useI18n } from "./useI18n";

export function useReorder() {
  const cart = useCartStore();
  const toast = useToastStore();
  const { t } = useI18n();

  /**
   * Re-resolve a past order against the live menu and add the available lines.
   *
   * @param {object} order        A past order: { items[], fulfillment_type, delivery_* }.
   *                              Items may be recentOrders / server-history / OrderStatus shape.
   * @param {object} [opts]
   * @param {object} [opts.profile]          Restaurant profile (for delivery_enabled fallback).
   * @param {boolean} [opts.restoreFulfillment=true]
   * @returns {Promise<{added:number, skipped:string[], ok:boolean}>}
   */
  async function reorderFromOrder(order, opts = {}) {
    const { profile = null, restoreFulfillment = true } = opts;
    const items = order?.items;
    if (!Array.isArray(items) || !items.length) {
      toast.show(t("reorder.empty"), "info");
      return { added: 0, skipped: [], ok: true };
    }

    const result = await cart.reorderFromOrder(items, api);

    if (!result.ok) {
      // Resolver unreachable — nothing added; tell the user it could not be done.
      toast.show(t("reorder.allUnavailable"), "error");
      return { ...result, added: 0 };
    }

    if (result.added === 0) {
      toast.show(t("reorder.allUnavailable"), "error");
      return result;
    }

    // Restore fulfillment context from the order (delivery address/type/coords),
    // falling back to pickup if delivery is no longer available for this venue.
    if (restoreFulfillment) {
      const ft = order?.fulfillment_type || "";
      const deliveryEnabled = profile ? profile.delivery_enabled !== false : true;
      const resolvedFt = ft === "delivery" && !deliveryEnabled ? "pickup" : ft;
      if (resolvedFt) {
        cart.persistFulfillmentContext({
          fulfillment_type: resolvedFt,
          delivery_address: order?.delivery_address || "",
          delivery_lat: order?.delivery_lat ?? null,
          delivery_lng: order?.delivery_lng ?? null,
        });
      }
    }

    // One contextual toast. Skipped/price-changed take priority over the plain "added".
    if (result.skipped.length) {
      toast.show(t("reorder.someUnavailable", { names: result.skipped.join(", ") }), "warning");
    } else if (result.priceChanged) {
      toast.show(t("reorder.priceUpdated"), "info");
    } else {
      toast.show(t("reorder.added"), "success");
    }
    return result;
  }

  /**
   * Pull the signed-in customer's account-bound order history from the server and
   * merge it into cart.recentOrders, so reorder is server-sourced and survives a
   * device switch / cleared localStorage. Best-effort: silent on any failure (the
   * localStorage list remains the fallback).
   *
   * @returns {Promise<number>} number of server orders merged in.
   */
  async function hydrateServerHistory() {
    let orders = [];
    try {
      const { data } = await api.get("/customer/orders/");
      orders = Array.isArray(data?.orders) ? data.orders : [];
    } catch {
      return 0; // not signed in / public schema / network — keep localStorage list
    }
    if (!orders.length) return 0;

    // pushRecentOrder prepends (newest-first) and caps at 5. The endpoint returns
    // newest-first, so iterate OLDEST-first to land the true newest at the front.
    let merged = 0;
    for (const o of [...orders].reverse()) {
      const items = Array.isArray(o?.items) ? o.items : [];
      if (!items.length) continue;
      // Map the server order-item shape onto the recentOrders entry shape that the
      // reorder code path + Menu.vue UI already consume.
      cart.pushRecentOrder({
        order_number: o.order_number,
        total: o.total,
        currency: o.currency,
        created_at: o.created_at,
        fulfillment_type: o.fulfillment_type || "",
        delivery_address: o.delivery_address || "",
        delivery_lat: o.delivery_lat ?? null,
        delivery_lng: o.delivery_lng ?? null,
        items: items.map((it) => ({
          slug: it.dish_slug || it.slug || "",
          name: it.dish_name || it.name || "",
          price: Number(it.unit_price ?? it.price ?? 0),
          currency: it.currency || o.currency || "MAD",
          qty: Number(it.qty ?? 1),
          note: it.note || "",
          option_ids: Array.isArray(it.option_ids)
            ? it.option_ids
            : (Array.isArray(it.options) ? it.options.map((x) => x?.id).filter((v) => v != null) : []),
          option_labels: Array.isArray(it.option_labels)
            ? it.option_labels
            : (Array.isArray(it.options) ? it.options.map((x) => x?.name).filter(Boolean) : []),
        })),
      });
      merged += 1;
    }
    return merged;
  }

  return { reorderFromOrder, hydrateServerHistory };
}
