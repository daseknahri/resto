/**
 * useNowTicker — reactive "now" that ticks every 30 seconds.
 * Use elapsed-time displays on active order cards.
 *
 * Usage:
 *   const { now } = useNowTicker()
 *   const elapsedMin = computed(() => Math.floor((now.value - new Date(order.status_updated_at)) / 60_000))
 */
import { ref, onMounted, onUnmounted } from "vue";

export function useNowTicker(intervalMs = 30_000) {
  const now = ref(Date.now());
  let timer = null;

  onMounted(() => {
    timer = setInterval(() => {
      now.value = Date.now();
    }, intervalMs);
  });

  onUnmounted(() => {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  });

  return { now };
}
