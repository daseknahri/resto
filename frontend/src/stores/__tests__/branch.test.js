/**
 * Unit tests for useBranchStore — the storefront location picker state
 * (Phase 3 multi-branch, D3).
 *
 * Contract under test:
 *  - load() fetches GET /branches/ once and restores the persisted
 *    selection when it is still valid, else the default branch;
 *  - hasChoice is true only with 2+ branches (single-branch tenants
 *    never see a picker);
 *  - select() ignores unknown slugs and persists valid ones;
 *  - a failed fetch leaves checkout untouched (empty list, no throw) —
 *    the backend defaults the order's branch in that case.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useBranchStore } from "../branch";

vi.mock("../../lib/api", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}));
import api from "../../lib/api";

const BRANCHES = [
  { id: 1, slug: "main", name: "Main Outlet", address: "1 Main St", is_default: true },
  { id: 2, slug: "annex", name: "Annex", address: "9 Annex Rd", is_default: false },
];

describe("useBranchStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("loads branches and selects the default by default", async () => {
    api.get.mockResolvedValueOnce({ data: { branches: BRANCHES } });
    const store = useBranchStore();
    await store.load();
    expect(api.get).toHaveBeenCalledWith("/branches/");
    expect(store.branches).toHaveLength(2);
    expect(store.hasChoice).toBe(true);
    expect(store.selectedSlug).toBe("main");
    expect(store.selectedBranch.name).toBe("Main Outlet");
  });

  it("restores a persisted selection when still valid", async () => {
    window.localStorage.setItem(
      `rostoy.branch.${window.location.hostname}`,
      "annex",
    );
    api.get.mockResolvedValueOnce({ data: { branches: BRANCHES } });
    const store = useBranchStore();
    await store.load();
    expect(store.selectedSlug).toBe("annex");
  });

  it("falls back to the default when the persisted slug is gone", async () => {
    window.localStorage.setItem(
      `rostoy.branch.${window.location.hostname}`,
      "demolished",
    );
    api.get.mockResolvedValueOnce({ data: { branches: BRANCHES } });
    const store = useBranchStore();
    await store.load();
    expect(store.selectedSlug).toBe("main");
  });

  it("hasChoice is false for a single-branch tenant", async () => {
    api.get.mockResolvedValueOnce({ data: { branches: [BRANCHES[0]] } });
    const store = useBranchStore();
    await store.load();
    expect(store.hasChoice).toBe(false);
    expect(store.selectedSlug).toBe("main");
  });

  it("select() persists valid slugs and ignores unknown ones", async () => {
    api.get.mockResolvedValueOnce({ data: { branches: BRANCHES } });
    const store = useBranchStore();
    await store.load();
    store.select("annex");
    expect(store.selectedSlug).toBe("annex");
    expect(
      window.localStorage.getItem(`rostoy.branch.${window.location.hostname}`),
    ).toBe("annex");
    store.select("nope");
    expect(store.selectedSlug).toBe("annex");
  });

  it("a failed fetch leaves an empty list and does not throw", async () => {
    api.get.mockRejectedValueOnce(new Error("network down"));
    const store = useBranchStore();
    await store.load();
    expect(store.branches).toEqual([]);
    expect(store.hasChoice).toBe(false);
    expect(store.selectedSlug).toBe("");
  });

  it("load() is idempotent — a second call does not refetch", async () => {
    api.get.mockResolvedValueOnce({ data: { branches: BRANCHES } });
    const store = useBranchStore();
    await store.load();
    await store.load();
    expect(api.get).toHaveBeenCalledTimes(1);
  });
});
