import { ref } from "vue";

import api from "../lib/api";

/**
 * Pending waiter calls for the owner workspace.
 *
 * Module-level singleton so the layout (which owns the WebSocket + the alert
 * banner) shares one list. Real-time events update it instantly; a load() on
 * mount and a refetch on any unexpected event keep it correct if a socket frame
 * is missed. Fully degrades to the mount load if WS isn't connected.
 */
const pending = ref([]);

export function useWaiterCalls() {
  const load = async () => {
    try {
      const { data } = await api.get("/owner/waiter-calls/");
      pending.value = Array.isArray(data.results) ? data.results : [];
    } catch {
      /* keep whatever we have */
    }
  };

  const acknowledge = async (id) => {
    const snapshot = pending.value;
    pending.value = pending.value.filter((c) => c.id !== id); // optimistic
    try {
      await api.post(`/owner/waiter-calls/${id}/acknowledge/`);
    } catch {
      pending.value = snapshot; // restore on failure
    }
  };

  // Handle a realtime frame. Async — resolves true when a NEW call became visible
  // to THIS user (so the caller can play the alert sound / show a toast).
  //
  // For new calls we resync through load() rather than trusting the payload, so
  // the server's hard section routing decides what this user sees: a non-section
  // waiter never gets the call (or its alert), the responsible waiter does.
  const handleRealtime = async (event, payload) => {
    const id = payload?.id;
    if (event === "waiter.call.ack") {
      if (id) pending.value = pending.value.filter((c) => c.id !== id);
      return false;
    }
    if (event === "waiter.call") {
      const before = new Set(pending.value.map((c) => c.id));
      await load(); // authoritative + section-filtered
      return pending.value.some((c) => !before.has(c.id));
    }
    return false;
  };

  return { pending, load, acknowledge, handleRealtime };
}
