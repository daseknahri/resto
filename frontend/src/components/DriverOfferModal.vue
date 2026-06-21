<!--
  DriverOfferModal — full-screen exclusive-offer takeover (Uber Driver / DoorDash
  Dasher parity). When a delivery job is exclusively offered to THIS driver, the
  app must make it unmissable: it takes over the screen, plays a chime + fires a
  haptic buzz, and shows a shrinking countdown ring bound to the offer's deadline.

  Purely additive overlay. It does NOT own any data: the parent (DriverPage) feeds
  it the offer object and the live remaining seconds, and listens for accept/pass —
  reusing the existing accept(id) / decline(id) handlers. The inline pending list
  stays as the fallback for open-pool (non-exclusive) offers.
-->
<template>
  <Teleport to="body">
    <div
      v-if="offer"
      class="fixed inset-0 z-[3000] flex flex-col items-center justify-between bg-slate-950/97 px-5 py-8 backdrop-blur-md safe-b"
      role="dialog"
      aria-modal="true"
      :aria-label="t('driverOffer.title')"
    >
      <!-- Header: new-offer banner -->
      <div class="w-full max-w-md text-center space-y-1.5">
        <p class="ui-kicker text-emerald-300">{{ t('driverOffer.newOffer') }}</p>
        <h2 class="ui-display text-2xl font-bold text-white">{{ t('driverOffer.title') }}</h2>
      </div>

      <!-- Countdown ring + payout in the centre -->
      <div class="flex flex-col items-center gap-5">
        <div class="relative flex h-44 w-44 items-center justify-center">
          <svg viewBox="0 0 120 120" class="h-44 w-44 -rotate-90" aria-hidden="true">
            <circle
              cx="60" cy="60" :r="RADIUS"
              fill="none" stroke="currentColor" stroke-width="8"
              class="text-slate-700/60"
            />
            <circle
              cx="60" cy="60" :r="RADIUS"
              fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round"
              :stroke-dasharray="CIRCUMFERENCE"
              :stroke-dashoffset="dashOffset"
              :class="ringColorClass"
              style="transition: stroke-dashoffset 0.95s linear, stroke 0.3s"
            />
          </svg>
          <div class="absolute inset-0 flex flex-col items-center justify-center">
            <span class="text-4xl font-bold tabular-nums" :class="secondsLeft <= 5 ? 'text-red-300' : 'text-white'">
              {{ secondsLeft }}
            </span>
            <span class="text-[11px] uppercase tracking-wider text-slate-400">{{ t('driverOffer.secondsUnit') }}</span>
          </div>
        </div>

        <!-- Payout — the number that decides the tap -->
        <p class="text-3xl font-bold tabular-nums text-emerald-300">{{ fmtMoney(offer.driver_payout) }}</p>

        <!-- Offer meta chips -->
        <div class="flex flex-wrap items-center justify-center gap-2 text-xs text-slate-300">
          <span v-if="offer.restaurant_name" class="font-semibold text-slate-100">{{ offer.restaurant_name }}</span>
          <span
            v-if="offer.distance_to_pickup_km != null"
            class="inline-flex items-center gap-1 rounded-full bg-sky-500/15 px-2.5 py-0.5 font-semibold text-sky-300"
          >
            <AppIcon name="location" class="h-3 w-3" aria-hidden="true" />{{ t('driver.toPickupKm', { km: offer.distance_to_pickup_km }) }}
          </span>
          <span v-if="offer.distance_km != null" class="inline-flex items-center gap-1">
            <AppIcon name="location" class="h-3 w-3" aria-hidden="true" />{{ t('driver.distanceKm', { km: offer.distance_km }) }}
          </span>
          <span v-if="offer.items_count">{{ t('driver.itemsCount', { n: offer.items_count }) }}</span>
        </div>

        <!-- Drop-off address -->
        <p v-if="offer.delivery_address" class="max-w-md text-center text-sm text-slate-300">
          <AppIcon name="location" class="mr-1 inline h-3.5 w-3.5 text-emerald-300" aria-hidden="true" />{{ offer.delivery_address }}
        </p>

        <!-- COD vs prepaid -->
        <span
          v-if="offer.collect_cash"
          class="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-300"
        >{{ t('driver.cashShort', { amount: fmtMoney(offer.order_total) }) }}</span>
        <span
          v-else-if="offer.order_total"
          class="rounded-full bg-emerald-500/12 px-3 py-1 text-xs font-semibold text-emerald-300"
        >{{ t('driver.prepaidShort') }}</span>
      </div>

      <!-- Actions: big full-width Accept, small Pass -->
      <div class="w-full max-w-md space-y-3">
        <!-- One-time enable-sound tap: browsers block autoplay until a user gesture. -->
        <button
          v-if="!soundEnabled"
          class="ui-touch-target flex w-full items-center justify-center gap-2 rounded-xl border border-slate-600 py-2 text-xs text-slate-300 hover:border-slate-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
          @click="enableSound"
        >
          🔔 {{ t('driverOffer.enableSound') }}
        </button>

        <button
          class="ui-btn-primary w-full rounded-2xl py-4 text-lg font-bold shadow-lg shadow-emerald-900/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400"
          style="min-height: 56px"
          :disabled="busy"
          :aria-busy="busy"
          @click="$emit('accept', offer.id)"
        >
          {{ t('driverOffer.accept') }}
        </button>
        <button
          class="ui-touch-target w-full rounded-xl py-3 text-sm text-slate-400 hover:text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
          style="min-height: 48px"
          :disabled="busy"
          @click="$emit('pass', offer.id)"
        >
          {{ t('driverOffer.pass') }}
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue';
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const props = defineProps({
  // The exclusively-offered delivery job, or null when there's nothing to show.
  offer: { type: Object, default: null },
  // Live remaining seconds for the offer (parent drives this off its shared clock).
  secondsLeft: { type: Number, default: 0 },
  // Total offer window in seconds — sizes the ring's "full" state.
  totalSeconds: { type: Number, default: 30 },
  // Disables the action buttons while an accept/pass request is in flight.
  busy: { type: Boolean, default: false },
  // Per-locale currency formatter from the parent (keeps one source of truth).
  fmtMoney: { type: Function, default: (v) => String(v ?? '') },
});

defineEmits(['accept', 'pass']);

const { t } = useI18n();

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

// Fraction of the window remaining (0..1) → ring fill. Guard against a zero/short
// window so the ring is full at the start rather than NaN.
const fraction = computed(() => {
  const total = props.totalSeconds > 0 ? props.totalSeconds : 30;
  return Math.max(0, Math.min(1, props.secondsLeft / total));
});
const dashOffset = computed(() => CIRCUMFERENCE * (1 - fraction.value));

const ringColorClass = computed(() => {
  if (props.secondsLeft <= 5) return 'text-red-400';
  if (props.secondsLeft <= 10) return 'text-amber-400';
  return 'text-emerald-400';
});

// ── Sound + haptic ──────────────────────────────────────────────────────────
// Autoplay is blocked until a user gesture, so the chime is gated behind a
// one-time "enable sound" tap (persisted). The haptic buzz needs no gesture.
const SOUND_KEY = 'kepoli.driver.offerSound';
const soundEnabled = ref(false);
try { soundEnabled.value = localStorage.getItem(SOUND_KEY) === '1'; } catch (e) { void e; }

let audioCtx = null;
const playChime = () => {
  if (!soundEnabled.value) return;
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    if (!audioCtx) audioCtx = new AC();
    if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {});
    // Two short rising beeps — an attention chime, not a long tone.
    [0, 0.18].forEach((startAt, i) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.value = i === 0 ? 880 : 1175;
      const t0 = audioCtx.currentTime + startAt;
      gain.gain.setValueAtTime(0.0001, t0);
      gain.gain.exponentialRampToValueAtTime(0.25, t0 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.14);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(t0);
      osc.stop(t0 + 0.16);
    });
  } catch (e) { void e; }
};

const buzz = () => {
  try { navigator.vibrate?.([200, 100, 200]); } catch (e) { void e; }
};

const enableSound = () => {
  soundEnabled.value = true;
  try { localStorage.setItem(SOUND_KEY, '1'); } catch (e) { void e; }
  playChime(); // confirm it works (and unlock the audio context within the gesture)
};

// Fire the alert each time a NEW offer takes over the screen (id changes).
watch(
  () => props.offer?.id,
  (id, prev) => {
    if (id != null && id !== prev) {
      buzz();
      playChime();
    }
  },
);

onBeforeUnmount(() => {
  try { audioCtx?.close?.(); } catch (e) { void e; }
});
</script>
