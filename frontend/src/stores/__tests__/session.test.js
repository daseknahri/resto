/**
 * Unit tests for useSessionStore
 *
 * Covers: isTenantStaff, isTenantOwner, isPlatformAdmin, canEditTenantMenu,
 * isAuthenticated getters.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useSessionStore } from "../session";

vi.mock("../../lib/api", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));
vi.mock("../../i18n/translate", () => ({
  translate: (key) => key,
}));

describe("useSessionStore — role getters", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("isAuthenticated is false when user is null", () => {
    const store = useSessionStore();
    expect(store.isAuthenticated).toBe(false);
  });

  it("isAuthenticated is true when user is set", () => {
    const store = useSessionStore();
    store.user = { id: 1, role: "tenant_owner" };
    expect(store.isAuthenticated).toBe(true);
  });

  it("isTenantOwner is true for role tenant_owner", () => {
    const store = useSessionStore();
    store.user = { role: "tenant_owner" };
    expect(store.isTenantOwner).toBe(true);
    expect(store.isTenantStaff).toBe(false);
  });

  it("isTenantStaff is true for role tenant_staff", () => {
    const store = useSessionStore();
    store.user = { role: "tenant_staff" };
    expect(store.isTenantStaff).toBe(true);
    expect(store.isTenantOwner).toBe(false);
  });

  it("isTenantStaff and isTenantOwner are false when user is null", () => {
    const store = useSessionStore();
    expect(store.isTenantStaff).toBe(false);
    expect(store.isTenantOwner).toBe(false);
  });

  it("isPlatformAdmin requires is_platform_admin === true (matches backend admin gating)", () => {
    const store = useSessionStore();
    store.user = { is_platform_admin: true };
    expect(store.isPlatformAdmin).toBe(true);

    // A Django staff/superuser without the PLATFORM_SUPERADMIN role must NOT pass —
    // the backend admin endpoints reject them, so the guard must too.
    store.user = { can_access_admin_console: true, is_platform_admin: false };
    expect(store.isPlatformAdmin).toBe(false);
  });

  it("canEditTenantMenu requires can_edit_tenant_menu === true", () => {
    const store = useSessionStore();
    store.user = { can_edit_tenant_menu: true };
    expect(store.canEditTenantMenu).toBe(true);

    store.user = { can_edit_tenant_menu: false };
    expect(store.canEditTenantMenu).toBe(false);
  });

  it("clear() resets user to null", () => {
    const store = useSessionStore();
    store.user = { id: 1 };
    store.clear();
    expect(store.user).toBeNull();
    expect(store.isAuthenticated).toBe(false);
  });
});
