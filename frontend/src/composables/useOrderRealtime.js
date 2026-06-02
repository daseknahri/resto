import { useRealtimeChannel } from "./useRealtimeChannel";

/**
 * Live status for a single order on the customer tracking page (guest channel —
 * the order number is the access credential, same as the HTTP status endpoint).
 * Thin wrapper over the generic channel client.
 *
 * Usage:
 *   const rt = useOrderRealtime(() => orderNumber.value, (event, payload) => { ... });
 *   onMounted(rt.connect); onBeforeUnmount(rt.disconnect);
 */
export function useOrderRealtime(getOrderNumber, onEvent) {
  return useRealtimeChannel(() => {
    if (typeof window === "undefined") return "";
    const num = typeof getOrderNumber === "function" ? getOrderNumber() : getOrderNumber;
    if (!num) return "";
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}/ws/order/${encodeURIComponent(num)}/`;
  }, onEvent);
}
