/**
 * Unit tests for useCustomerStore
 *
 * Covers: isVerified getter (all combinations), isAuthenticated,
 * and wallet_balance presence.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useCustomerStore } from "../customer";
import api from "../../lib/api";

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

describe("useCustomerStore — fetchCustomer (guarded vs forced refresh)", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    api.get.mockReset();
  });

  it("is a no-op once loaded — the stale-balance trap a forced refresh exists to fix", async () => {
    const store = useCustomerStore();
    store.setCustomer({ id: 1, wallet_balance: "100.00" });
    await store.fetchCustomer();
    expect(api.get).not.toHaveBeenCalled();
    expect(store.customer.wallet_balance).toBe("100.00");
  });

  it("fetchCustomer(true) re-reads the session even when already loaded (post-order / post-cancel sync)", async () => {
    const store = useCustomerStore();
    store.setCustomer({ id: 1, wallet_balance: "100.00" });
    api.get.mockResolvedValueOnce({ data: { customer: { id: 1, wallet_balance: "60.00" }, platform: null } });
    await store.fetchCustomer(true);
    expect(api.get).toHaveBeenCalledTimes(1);
    expect(store.customer.wallet_balance).toBe("60.00");
  });

  it("a transient failure on a FORCED refresh keeps the last known customer (no phantom sign-out)", async () => {
    const store = useCustomerStore();
    store.setCustomer({ id: 1, wallet_balance: "100.00" });
    api.get.mockRejectedValueOnce({ response: { status: 503 } });
    await store.fetchCustomer(true);
    expect(store.isAuthenticated).toBe(true);
    expect(store.customer.wallet_balance).toBe("100.00");
    expect(store.loading).toBe(false);
  });

  it("a network error (no response) on a forced refresh also keeps the customer", async () => {
    const store = useCustomerStore();
    store.setCustomer({ id: 1 });
    api.get.mockRejectedValueOnce(new Error("Network Error"));
    await store.fetchCustomer(true);
    expect(store.isAuthenticated).toBe(true);
  });

  it("an explicit 401 on a forced refresh clears the customer (the session really is gone)", async () => {
    const store = useCustomerStore();
    store.setCustomer({ id: 1 });
    api.get.mockRejectedValueOnce({ response: { status: 401 } });
    await store.fetchCustomer(true);
    expect(store.customer).toBeNull();
  });

  it("a failed FIRST load leaves the customer null and marks the store loaded", async () => {
    const store = useCustomerStore();
    api.get.mockRejectedValueOnce({ response: { status: 500 } });
    await store.fetchCustomer();
    expect(store.customer).toBeNull();
    expect(store.loaded).toBe(true);
  });
});
