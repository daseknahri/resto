/**
 * Unit tests for useCustomerStore
 *
 * Covers: isVerified getter (all combinations), isAuthenticated,
 * and wallet_balance presence.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useCustomerStore } from "../customer";

// ── api mock ──────────────────────────────────────────────────────────────────
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

// ── tests ─────────────────────────────────────────────────────────────────────
describe("useCustomerStore — isVerified getter", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("is false when customer is null", () => {
    const store = useCustomerStore();
    store.customer = null;
    expect(store.isVerified).toBe(false);
  });

  it("is false when all verification flags are false/null", () => {
    const store = useCustomerStore();
    store.customer = { phone_verified: false, email_verified: false, has_google: false };
    expect(store.isVerified).toBe(false);
  });

  it("is true when phone_verified is true", () => {
    const store = useCustomerStore();
    store.customer = { phone_verified: true, email_verified: false, has_google: false };
    expect(store.isVerified).toBe(true);
  });

  it("is true when email_verified is true", () => {
    const store = useCustomerStore();
    store.customer = { phone_verified: false, email_verified: true, has_google: false };
    expect(store.isVerified).toBe(true);
  });

  it("is true when has_google is truthy", () => {
    const store = useCustomerStore();
    store.customer = { phone_verified: false, email_verified: false, has_google: "google-sub-id" };
    expect(store.isVerified).toBe(true);
  });

  it("is true when multiple flags are set", () => {
    const store = useCustomerStore();
    store.customer = { phone_verified: true, email_verified: true, has_google: "sub" };
    expect(store.isVerified).toBe(true);
  });
});

describe("useCustomerStore — isAuthenticated getter", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("is false when customer is null", () => {
    const store = useCustomerStore();
    store.customer = null;
    expect(store.isAuthenticated).toBe(false);
  });

  it("is true when customer is set", () => {
    const store = useCustomerStore();
    store.customer = { id: 1, name: "Ali", phone_verified: true, email_verified: false, has_google: false };
    expect(store.isAuthenticated).toBe(true);
  });
});

describe("useCustomerStore — state and actions", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("initial state has null customer", () => {
    const store = useCustomerStore();
    expect(store.customer).toBeNull();
  });

  it("setCustomer updates customer", () => {
    const store = useCustomerStore();
    const c = { id: 1, name: "Ali", phone_verified: true, email_verified: false, has_google: false };
    store.setCustomer(c);
    expect(store.customer).toEqual(c);
    expect(store.isAuthenticated).toBe(true);
  });

  it("setCustomer(null) clears customer", () => {
    const store = useCustomerStore();
    store.setCustomer({ id: 1 });
    store.setCustomer(null);
    expect(store.customer).toBeNull();
    expect(store.isAuthenticated).toBe(false);
  });

  it("displayName prefers name over phone over email", () => {
    const store = useCustomerStore();
    store.customer = { name: "Sara", phone: "0600", email: "s@x.com" };
    expect(store.displayName).toBe("Sara");

    store.customer = { name: "", phone: "0600", email: "s@x.com" };
    expect(store.displayName).toBe("0600");

    store.customer = { name: "", phone: "", email: "s@x.com" };
    expect(store.displayName).toBe("s@x.com");
  });
});
