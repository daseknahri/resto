import { ref } from "vue";

/**
 * Lightweight WebSocket client for owner/staff real-time pings.
 *
 * The server only sends low-sensitivity "something changed" events (e.g.
 * `order.new`); we react by refetching over the authenticated HTTP API — the
 * socket is never trusted as a data source. Entirely optional: if the socket
 * can't connect (WS infra not deployed, proxy without upgrade, offline), we give
 * up quietly after a few tries and the existing polling carries the experience.
 *
 * Usage:
 *   const rt = useOwnerRealtime((event, payload) => { ... });
 *   onMounted(rt.connect); onBeforeUnmount(rt.disconnect);
 */
export function useOwnerRealtime(onEvent) {
  let socket = null;
  let closedByUs = false;
  let reconnectTimer = null;
  let attempts = 0;
  const connected = ref(false);

  const wsUrl = () => {
    if (typeof window === "undefined") return "";
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}/ws/owner/`;
  };

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
    closedByUs = false;
    let ws;
    try {
      ws = new WebSocket(wsUrl());
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
