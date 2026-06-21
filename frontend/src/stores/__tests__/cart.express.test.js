/**
 * Unit tests for the cart store's express-checkout persistence
 * (remember last fulfillment + address + payment).
 *
 * The feature is OPT-IN and DEFAULT OFF: until the customer flips the toggle,
 * loadExpressCheckout() returns null and persistExpressCheckout() is a no-op,
 * so an existing customer sees exactly today's behavior. These tests pin both
 * the default-preserving guard and the opt-in round-trip.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useCartStore } from "../cart";

describe("cart express checkout — remember last fulfillment + address + payment", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  // ── Default-preserving guard ──────────────────────────────────────────────
  it("is OFF by default — no remembered state, load is null (preserves today's behavior)", () => {
    const cart = useCartStore();
    expect(cart.isExpressCheckoutEnabled()).toBe(false);
    expect(cart.loadExpressCheckout()).toBeNull();
  });

  it("persistExpressCheckout is a no-op while disabled — never accumulates state", () => {
    const cart = useCartStore();
    cart.persistExpressCheckout({
      fulfillment_type: "delivery",
      delivery_address: "1 Main St",
      delivery_lat: 33.5,
      delivery_lng: -7.6,
      payment_method: "cash",
    });
    // Still nothing remembered, because the customer never opted in.
    expect(cart.loadExpressCheckout()).toBeNull();
    expect(cart.readExpressCheckout()?.enabled ?? false).toBe(false);
  });

  // ── Opt-in round-trip ─────────────────────────────────────────────────────
  it("once enabled, remembers a delivery order's fulfillment + address + payment", () => {
    const cart = useCartStore();
    cart.setExpressCheckoutEnabled(true);
    expect(cart.isExpressCheckoutEnabled()).toBe(true);
    // Enabled but nothing placed yet → no fulfillment context to apply.
    expect(cart.loadExpressCheckout()).toEqual({
      enabled: true,
      fulfillment_type: "",
      delivery_address: "",
      delivery_lat: null,
      delivery_lng: null,
      payment_method: "",
    });

    cart.persistExpressCheckout({
      fulfillment_type: "delivery",
      delivery_address: "1 Main St",
      delivery_lat: 33.5731,
      delivery_lng: -7.5898,
      payment_method: "cash",
    });

    const ctx = cart.loadExpressCheckout();
    expect(ctx).toEqual({
      enabled: true,
      fulfillment_type: "delivery",
      delivery_address: "1 Main St",
      delivery_lat: 33.5731,
      delivery_lng: -7.5898,
      payment_method: "cash",
    });
  });

  it("drops delivery address/coords when the remembered order was pickup", () => {
    const cart = useCartStore();
    cart.setExpressCheckoutEnabled(true);
    cart.persistExpressCheckout({
      fulfillment_type: "pickup",
      delivery_address: "should be ignored",
      delivery_lat: 1,
      delivery_lng: 2,
      payment_method: "wallet",
    });
    const ctx = cart.loadExpressCheckout();
    expect(ctx.fulfillment_type).toBe("pickup");
    expect(ctx.delivery_address).toBe("");
    expect(ctx.delivery_lat).toBeNull();
    expect(ctx.delivery_lng).toBeNull();
    expect(ctx.payment_method).toBe("wallet");
  });

  it("sanitizes unknown fulfillment / payment values", () => {
    const cart = useCartStore();
    cart.setExpressCheckoutEnabled(true);
    cart.persistExpressCheckout({
      fulfillment_type: "teleport",
      delivery_address: "",
      delivery_lat: null,
      delivery_lng: null,
      payment_method: "bitcoin",
    });
    const ctx = cart.loadExpressCheckout();
    expect(ctx.fulfillment_type).toBe("");
    expect(ctx.payment_method).toBe("");
  });

  it("toggling OFF stops applying but preserves the stored context for re-enable", () => {
    const cart = useCartStore();
    cart.setExpressCheckoutEnabled(true);
    cart.persistExpressCheckout({
      fulfillment_type: "delivery",
      delivery_address: "1 Main St",
      delivery_lat: 33.5,
      delivery_lng: -7.6,
      payment_method: "wallet",
    });
    expect(cart.loadExpressCheckout()).not.toBeNull();

    cart.setExpressCheckoutEnabled(false);
    // Apply path now returns null (preserves today's behavior)…
    expect(cart.loadExpressCheckout()).toBeNull();
    // …but the remembered context survives for when they re-enable.
    expect(cart.readExpressCheckout()).toMatchObject({
      enabled: false,
      fulfillment_type: "delivery",
      delivery_address: "1 Main St",
      payment_method: "wallet",
    });

    cart.setExpressCheckoutEnabled(true);
    expect(cart.loadExpressCheckout()).toMatchObject({
      fulfillment_type: "delivery",
      delivery_address: "1 Main St",
      payment_method: "wallet",
    });
  });

  it("is per-host (storage key includes the hostname)", () => {
    const cart = useCartStore();
    expect(cart.expressCheckoutStorageKey()).toBe(`cart:express:${window.location.hostname}`);
  });

  it("survives corrupt localStorage without throwing", () => {
    localStorage.setItem(`cart:express:${window.location.hostname}`, "{not json");
    const cart = useCartStore();
    expect(cart.readExpressCheckout()).toBeNull();
    expect(cart.loadExpressCheckout()).toBeNull();
    expect(cart.isExpressCheckoutEnabled()).toBe(false);
  });
});
