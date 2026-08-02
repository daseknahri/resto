import { describe, it, expect, vi, beforeEach } from "vitest";

// vi.mock factories are hoisted above module scope, so their referenced values must come from
// vi.hoisted (not plain top-level consts) — else "Cannot access X before initialization".
const { mockApi, state } = vi.hoisted(() => ({
  mockApi: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
  state: { authed: true },
}));
vi.mock("../../lib/api", () => ({ default: mockApi }));
vi.mock("../../stores/customer", () => ({
  useCustomerStore: () => ({ get isAuthenticated() { return state.authed; } }),
}));

import { useSavedAddresses } from "../useSavedAddresses";

describe("useSavedAddresses", () => {
  beforeEach(() => {
    mockApi.get.mockReset();
    mockApi.post.mockReset();
    mockApi.delete.mockReset();
    state.authed = true;
  });

  it("loadSavedAddresses is a no-op for guests (no API call)", async () => {
    state.authed = false;
    const { loadSavedAddresses, savedAddresses } = useSavedAddresses();
    const list = await loadSavedAddresses();
    expect(mockApi.get).not.toHaveBeenCalled();
    expect(list).toEqual([]);
    expect(savedAddresses.value).toEqual([]);
  });

  it("loadSavedAddresses fetches + sets the list for a signed-in customer", async () => {
    mockApi.get.mockResolvedValue({ data: [{ id: 1, address: "A" }] });
    const { loadSavedAddresses, savedAddresses } = useSavedAddresses();
    await loadSavedAddresses();
    expect(mockApi.get).toHaveBeenCalledWith("/customer/addresses/");
    expect(savedAddresses.value).toEqual([{ id: 1, address: "A" }]);
  });

  it("loadSavedAddresses swallows API errors (degrades to manual entry)", async () => {
    mockApi.get.mockRejectedValue(new Error("boom"));
    const { loadSavedAddresses, savedAddresses } = useSavedAddresses();
    await expect(loadSavedAddresses()).resolves.toEqual([]);
    expect(savedAddresses.value).toEqual([]);
  });

  it("removeSavedAddress DELETEs and drops it from the list", async () => {
    mockApi.get.mockResolvedValue({ data: [{ id: 1 }, { id: 2 }] });
    mockApi.delete.mockResolvedValue({});
    const c = useSavedAddresses();
    await c.loadSavedAddresses();
    await c.removeSavedAddress(1);
    expect(mockApi.delete).toHaveBeenCalledWith("/customer/addresses/1/");
    expect(c.savedAddresses.value).toEqual([{ id: 2 }]);
  });

  it("persistSavedAddress POSTs and prepends the saved row (most-recent first)", async () => {
    mockApi.get.mockResolvedValue({ data: [{ id: 1 }] });
    mockApi.post.mockResolvedValue({ data: { id: 9, address: "New" } });
    const c = useSavedAddresses();
    await c.loadSavedAddresses();
    const saved = await c.persistSavedAddress({ address: "New" });
    expect(mockApi.post).toHaveBeenCalledWith("/customer/addresses/", { address: "New" });
    expect(saved).toEqual({ id: 9, address: "New" });
    expect(c.savedAddresses.value[0]).toEqual({ id: 9, address: "New" });
    expect(c.savedAddresses.value).toHaveLength(2);
  });
});
