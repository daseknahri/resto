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

  // Handle a realtime frame. Returns true when it's a NEW call (so the caller can
  // play the alert sound / show a toast).
  const handleRealtime = (event, payload) => {
    const id = payload?.id;
    if (event === "waiter.call") {
      if (id && !pending.value.some((c) => c.id === id)) {
        pending.value = [
          ...pending.value,
          {
            id,
            table_label: payload.table_label || "",
            note: payload.note || "",
            status: "pending",
          },
        ];
        return true;
      }
      if (!id) load(); // unknown shape → resync
      return Boolean(id);
    }
    if (event === "waiter.call.ack") {
      if (id) pending.value = pending.value.filter((c) => c.id !== id);
      return false;
    }
    return false;
  };

  return { pending, load, acknowledge, handleRealtime };
}
