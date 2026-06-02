import { ref } from "vue";

import api from "../lib/api";

/**
 * Shared internal staff chat (one channel per restaurant).
 *
 * Module-level singleton so the owner layout (which owns the WebSocket) and the
 * chat panel share one message list + unread count. New messages arrive in real
 * time via the owner socket (`chat.message`); a load() on mount seeds history and
 * keeps things working if the socket is unavailable.
 */
const messages = ref([]);
const unread = ref(0);
const isOpen = ref(false);

export function useStaffChat() {
  const appendMessage = (msg) => {
    if (!msg || !msg.id) return;
    if (messages.value.some((m) => m.id === msg.id)) return; // dedupe (sender also gets the broadcast)
    messages.value = [...messages.value, msg];
    if (!isOpen.value) unread.value += 1;
  };

  const load = async () => {
    try {
      const { data } = await api.get("/owner/chat/");
      messages.value = Array.isArray(data.results) ? data.results : [];
    } catch {
      /* keep whatever we have */
    }
  };

  const send = async (body) => {
    const text = String(body || "").trim();
    if (!text) return false;
    try {
      const { data } = await api.post("/owner/chat/", { body: text });
      appendMessage(data); // the socket echo is deduped by id
      return true;
    } catch {
      return false;
    }
  };

  const handleRealtime = (event, payload) => {
    if (event === "chat.message") appendMessage(payload);
  };

  const open = () => {
    isOpen.value = true;
    unread.value = 0;
  };
  const close = () => {
    isOpen.value = false;
  };

  return { messages, unread, isOpen, load, send, handleRealtime, open, close };
}
