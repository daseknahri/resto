import { defineStore } from "pinia";
import api from "../lib/api";

// Phase 3 multi-branch (decision D3) — the storefront location picker.
//
// A branch is the tenant's location/outlet: the vertical-general seam a
// restaurant, pharmacy or store tenant all share. The list comes from
// GET /api/branches/ (active branches only, Profile-fallback display
// fields). The chosen slug rides the place-order payload as `branch`;
// the backend's resolve_order_branch stamps the order with it (explicit
// slug wins, then the dine-in table's branch, then the tenant default),
// so checkout NEVER depends on this store succeeding — a failed fetch
// just leaves the picker hidden and the backend default in charge.
//
// Selection persists per tenant host (each tenant is its own host), so a
// returning customer keeps their outlet across visits.
const storageKey = () => {
  const host = typeof window !== "undefined" ? window.location.hostname : "";
  return `rostoy.branch.${host}`;
};

export const useBranchStore = defineStore("branch", {
  state: () => ({
    branches: [],
    selectedSlug: "",
    loading: false,
    loaded: false,
    error: null,
  }),

  getters: {
    // The picker renders only when there is a real choice to make.
    hasChoice: (s) => s.branches.length > 1,
    selectedBranch: (s) =>
      s.branches.find((b) => b.slug === s.selectedSlug) || null,
  },

  actions: {
    async load() {
      if (this.loading || this.loaded) return this.branches;
      this.loading = true;
      this.error = null;
      try {
        const res = await api.get("/branches/");
        this.branches = Array.isArray(res.data?.branches)
          ? res.data.branches
          : [];
        this._restoreSelection();
      } catch (err) {
        this.branches = [];
        this.error = err;
      } finally {
        this.loading = false;
        this.loaded = true;
      }
      return this.branches;
    },

    _restoreSelection() {
      let stored = "";
      try {
        stored = window.localStorage.getItem(storageKey()) || "";
      } catch {
        stored = "";
      }
      if (stored && this.branches.some((b) => b.slug === stored)) {
        this.selectedSlug = stored;
        return;
      }
      const dflt = this.branches.find((b) => b.is_default) || this.branches[0];
      this.selectedSlug = dflt ? dflt.slug : "";
    },

    select(slug) {
      if (!this.branches.some((b) => b.slug === slug)) return;
      this.selectedSlug = slug;
      try {
        window.localStorage.setItem(storageKey(), slug);
      } catch {
        // Private-mode / storage-disabled: selection still applies
        // for this session via state.
      }
    },
  },
});
