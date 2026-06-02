import { useRealtimeChannel } from "./useRealtimeChannel";

/**
 * Owner/staff real-time pings (e.g. `order.new`, `order.updated`, `waiter.call`).
 * Thin wrapper over the generic channel client — see useRealtimeChannel.
 *
 * Usage:
 *   const rt = useOwnerRealtime((event, payload) => { ... });
 *   onMounted(rt.connect); onBeforeUnmount(rt.disconnect);
 */
export function useOwnerRealtime(onEvent) {
  return useRealtimeChannel(() => {
    if (typeof window === "undefined") return "";
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}/ws/owner/`;
  }, onEvent);
}
