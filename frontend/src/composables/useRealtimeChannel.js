import { computed, ref } from "vue";

/**
 * Generic auto-reconnecting WebSocket client.
 *
 * `buildPath()` returns the full ws(s):// URL (or "" to skip connecting).
 * `onEvent(event, payload)` fires for each `{event, payload}` frame received.
 *
 * Reconnects forever with exponential backoff capped at 30 s + up to 500 ms
 * jitter. Callers can observe `connectionState`
 * ('live'|'connecting'|'polling'|'idle') to show a UI indicator. Falls back to
 * 'polling' only if the URL builder returns "" (WS explicitly disabled) — never
 * gives up on transient failures. 'idle' = we deliberately disconnected (e.g.
 * KeepAlive deactivate); a fresh connect() resets the backoff.
 */
export function useRealtimeChannel(buildPath, onEvent) {
  let socket = null;
  let closedByUs = false;
  let reconnectTimer = null;
  let attempts = 0;
  // 'live' = socket open, 'connecting' = reconnecting, 'polling' = no WS URL,
  // 'idle' = voluntarily disconnected
  const connectionState = ref("idle");
  // Keep the old `connected` boolean for backward-compat with callers
  const connected = computed(() => connectionState.value === "live");

  const scheduleReconnect = () => {
    if (closedByUs) return;
    clearTimeout(reconnectTimer);
    attempts += 1;
    // Cap at 30 s, add jitter so multiple clients don't thunder-herd
    const delay = Math.min(30000, 1000 * 2 ** attempts) + Math.random() * 500;
    connectionState.value = "connecting";
    reconnectTimer = setTimeout(connect, delay);
  };

  function connect() {
    if (typeof window === "undefined" || !("WebSocket" in window)) return;
    if (socket) return; // already connected/connecting
    // A fresh voluntary connect() starts a clean backoff sequence.
    closedByUs = false;
    attempts = 0;
    const url = buildPath();
    if (!url) {
      // No WS URL configured — stay in 'polling' mode permanently
      connectionState.value = "polling";
      return;
    }
    closedByUs = false;
    connectionState.value = "connecting";
    let ws;
    try {
      ws = new WebSocket(url);
    } catch {
      scheduleReconnect();
      return;
    }
    socket = ws;
    ws.onopen = () => {
      connectionState.value = "live";
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
      socket = null;
      if (closedByUs) {
        connectionState.value = "idle";
      } else {
        connectionState.value = "connecting";
        scheduleReconnect();
      }
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
    attempts = 0; // next connect() starts a fresh backoff sequence
    if (socket) {
      try {
        socket.close();
      } catch {
        /* ignore */
      }
      socket = null;
    }
    connectionState.value = "idle";
  }

  return { connect, disconnect, connected, connectionState };
}
