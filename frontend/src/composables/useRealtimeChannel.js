import { ref } from "vue";

/**
 * Generic auto-reconnecting WebSocket client.
 *
 * `buildPath()` returns the full ws(s):// URL (or "" to skip connecting).
 * `onEvent(event, payload)` fires for each `{event, payload}` frame received.
 *
 * Entirely optional: server frames are the only thing trusted; if the socket
 * can't connect (WS infra absent, proxy without upgrade, offline) it gives up
 * after a few tries and the caller's existing polling carries the experience.
 */
export function useRealtimeChannel(buildPath, onEvent) {
  let socket = null;
  let closedByUs = false;
  let reconnectTimer = null;
  let attempts = 0;
  const connected = ref(false);

  const scheduleReconnect = () => {
    if (closedByUs) return;
    clearTimeout(reconnectTimer);
    attempts += 1;
    if (attempts > 6) return; // ~1 min of tries, then rely on polling
    const delay = Math.min(30000, 1000 * 2 ** attempts) + Math.random() * 500;
    reconnectTimer = setTimeout(connect, delay);
  };

  function connect() {
    if (typeof window === "undefined" || !("WebSocket" in window)) return;
    if (socket) return; // already connected/connecting
    const url = buildPath();
    if (!url) return;
    closedByUs = false;
    let ws;
    try {
      ws = new WebSocket(url);
    } catch {
      scheduleReconnect();
      return;
    }
    socket = ws;
    ws.onopen = () => {
      connected.value = true;
      attempts = 0;
    };
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data && data.event) onEvent?.(data.event, data.payload || {});
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onclose = () => {
      connected.value = false;
      socket = null;
      if (!closedByUs) scheduleReconnect();
    };
    ws.onerror = () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };
  }

  function disconnect() {
    closedByUs = true;
    clearTimeout(reconnectTimer);
    if (socket) {
      try {
        socket.close();
      } catch {
        /* ignore */
      }
      socket = null;
    }
    connected.value = false;
  }

  return { connect, disconnect, connected };
}
