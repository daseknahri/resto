<template>
  <span
    class="inline-flex items-center gap-1.5"
    role="status"
    :aria-label="label"
    :title="label"
  >
    <span class="relative flex h-2 w-2" aria-hidden="true">
      <span
        v-if="isLive"
        class="absolute inline-flex h-full w-full rounded-full bg-emerald-400/70 opacity-75 motion-safe:animate-ping"
      />
      <span
        class="relative inline-flex h-2 w-2 rounded-full"
        :class="isLive ? 'bg-emerald-400' : 'bg-amber-400 motion-safe:animate-pulse'"
      />
    </span>
    <span
      v-if="showLabel"
      class="text-[10px] font-semibold uppercase tracking-wide"
      :class="isLive ? 'text-emerald-300' : 'text-amber-300'"
    >{{ label }}</span>
  </span>
</template>

<script setup>
/**
 * ConnectionDot — tiny presentational live-connection indicator for real-time
 * surfaces (order-status / ride tracking). Green pulsing dot when the realtime
 * channel/poll is healthy ('live'); muted amber pulse otherwise
 * ('connecting'|'polling'|'idle' / offline). Consumes the connectionState the
 * useRealtimeChannel composable already emits — purely presentational, no logic.
 */
import { computed } from "vue";
import { useI18n } from "../composables/useI18n";

const props = defineProps({
  // 'live' | 'connecting' | 'polling' | 'idle'
  state: { type: String, default: "connecting" },
  // when true, show a short text label next to the dot (not just the dot)
  showLabel: { type: Boolean, default: false },
});

const { t } = useI18n();

const isLive = computed(() => props.state === "live");
const label = computed(() =>
  isLive.value ? t("realtime.live") : t("realtime.reconnecting"),
);
</script>
