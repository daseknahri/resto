import { ref } from "vue";
import api from "../lib/api";
import { useCustomerStore } from "../stores/customer";

// Shared saved-delivery-address CRUD (/customer/addresses/) for the two checkout surfaces —
// Cart.vue (tenant storefront) and MarketplaceMenuPage.vue (marketplace). Owns the list, the
// GET/POST/DELETE calls, and the "save this address after ordering" form flags. Page-specific
// behavior stays in the page: applying an address into that page's form shape, the delete
// confirm/toast, and auto-selecting the most recent address (the marketplace does this; the cart
// doesn't).
export function useSavedAddresses() {
  const customerStore = useCustomerStore();
  const savedAddresses = ref([]);
  const saveAddressAfterOrder = ref(false);
  const saveAddressLabel = ref("");

  // GET the customer's saved addresses (no-op for guests). Silent on failure — the picker
  // degrades to manual entry. Returns the list so a caller can auto-select the first.
  const loadSavedAddresses = async () => {
    if (!customerStore.isAuthenticated) return savedAddresses.value;
    try {
      const res = await api.get("/customer/addresses/");
      savedAddresses.value = Array.isArray(res.data) ? res.data : [];
    } catch {
      // silent
    }
    return savedAddresses.value;
  };

  // DELETE one saved address and drop it from the list. Raw — the caller adds confirm/toast/
  // clear-applied as its UI needs.
  const removeSavedAddress = async (id) => {
    await api.delete(`/customer/addresses/${id}/`);
    savedAddresses.value = savedAddresses.value.filter((a) => a.id !== id);
  };

  // POST a new saved address (best-effort, after a delivery order); prepend so it's the most
  // recent (auto-selected next time), capped at 10. Returns the saved row (or null).
  const persistSavedAddress = async (payload) => {
    const res = await api.post("/customer/addresses/", payload);
    const saved = res?.data ?? null;
    if (saved) savedAddresses.value = [saved, ...savedAddresses.value].slice(0, 10);
    return saved;
  };

  return {
    savedAddresses,
    saveAddressAfterOrder,
    saveAddressLabel,
    loadSavedAddresses,
    removeSavedAddress,
    persistSavedAddress,
  };
}
