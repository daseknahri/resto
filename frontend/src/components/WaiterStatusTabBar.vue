<template>
  <div class="overflow-x-auto" style="scrollbar-width:none;-webkit-overflow-scrolling:touch">
    <div class="flex min-w-max items-center gap-2 pb-0.5">
      <!-- Tablist (ARIA-correct container for the tab buttons) -->
      <div
        class="flex shrink-0 items-center gap-2"
        role="tablist"
        :aria-label="t('waiterPage.tablistLabel')"
        @keydown.left.prevent="focusPrevTab"
        @keydown.right.prevent="focusNextTab"
      >
        <button
          v-for="tab in tabs"
          :id="`waiter-tab-${tab.key}`"
          :key="tab.key"
          role="tab"
          :aria-selected="activeTab === tab.key"
          :aria-controls="`waiter-panel-${tab.key}`"
          class="ui-state-chip ui-press ui-touch-target shrink-0"
          :data-active="activeTab === tab.key"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
          <span
            v-if="tab.count > 0"
            class="ms-1 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full px-1 text-[10px] font-bold tabular-nums leading-none"
            :class="['pending', 'unpaid'].includes(tab.key) ? 'bg-amber-500 text-white shadow-sm shadow-amber-900/30' : 'bg-slate-700/80 text-slate-100'"
          >{{ tab.count }}</span>
        </button>
        <!-- Recent / past orders tab -->
        <button
          id="waiter-tab-recent"
          role="tab"
          :aria-selected="activeTab === 'recent'"
          aria-controls="waiter-panel-recent"
          class="ui-state-chip ui-press ui-touch-target shrink-0"
          :data-active="activeTab === 'recent'"
          @click="activeTab = 'recent'"
        >
          {{ t('waiterPage.tabRecent') }}
        </button>
        <!-- Shift summary tab -->
        <button
          id="waiter-tab-shift"
          role="tab"
          :aria-selected="activeTab === 'shift'"
          aria-controls="waiter-panel-shift"
          class="ui-state-chip ui-press ui-touch-target shrink-0"
          :data-active="activeTab === 'shift'"
          @click="emit('selectShift')"
        >
          {{ t('waiterPage.tabShift') }}
        </button>
      </div>
      <!-- Separator -->
      <span class="waiter-tab-sep h-5 w-px shrink-0 self-center bg-slate-600/50" aria-hidden="true" />
      <!-- Action buttons — outside the tablist per ARIA spec but scroll with the tabs -->
      <div class="flex shrink-0 items-center gap-2">
        <!-- Sound mute toggle -->
        <button
          class="ui-btn-outline ui-press ui-touch-target px-3 py-1.5 text-sm"
          :class="soundOn ? '' : 'opacity-50'"
          :aria-label="soundOn ? t('ownerOrders.muteAlerts') : t('ownerOrders.unmuteAlerts')"
          @click="soundOn = !soundOn"
        >
          <span aria-hidden="true">{{ soundOn ? '🔔' : '🔕' }}</span>
        </button>
        <!-- Clock-in / clock-out (B4) -->
        <button
          v-if="canManage && !currentShift"
          :disabled="clockBusy"
          class="ui-state-chip ui-press ui-touch-target shrink-0 border-sky-500/40 bg-sky-500/8 font-semibold text-sky-300 disabled:opacity-50"
          @click="emit('clock', 'in')"
        >{{ t('waiterPage.clockIn') }}</button>
        <button
          v-if="canManage && currentShift"
          :disabled="clockBusy"
          class="ui-state-chip ui-press ui-touch-target shrink-0 border-amber-500/40 bg-amber-500/8 font-semibold text-amber-300 disabled:opacity-50"
          :title="currentShift?.clock_in ? t('waiterPage.clockedInSince', { time: formatDateTime(currentShift.clock_in) }) : ''"
          @click="emit('clock', 'out')"
        >{{ t('waiterPage.clockedIn') }}<template v-if="shiftElapsed"> · {{ shiftElapsed }}</template> ·&nbsp;{{ t('waiterPage.clockOut') }}</button>
        <button
          v-if="canManage"
          class="ui-btn-outline ui-press ui-touch-target shrink-0 px-3 py-1.5 text-sm"
          @click="emit('charge')"
        >
          {{ t('waiterPage.chargeWalletBtn') }}
        </button>
        <button
          v-if="canManage"
          class="ui-btn-primary ui-press ui-touch-target shrink-0 px-3 py-1.5 text-sm"
          @click="emit('newOrder')"
        >
          + {{ t('waiterPage.newOrderBtn') }}
        </button>
        <!-- Floor / List view toggle -->
        <button
          v-if="activeTab !== 'shift' && activeTab !== 'recent'"
          class="ui-btn-outline ui-press ui-touch-target shrink-0 px-3 py-1.5 text-sm"
          :class="floorView ? 'border-[var(--color-secondary)]/60 text-[var(--color-secondary)]' : ''"
          :data-active="floorView"
          :aria-pressed="floorView"
          :aria-label="floorView ? t('waiterPage.listViewToggle') : t('waiterPage.floorViewToggle')"
          @click="floorView = !floorView"
        >
          <svg v-if="!floorView" aria-hidden="true" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 me-1 shrink-0 inline-block"><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>
          <svg v-else aria-hidden="true" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 me-1 shrink-0 inline-block"><path fill-rule="evenodd" d="M2 3.5A.5.5 0 0 1 2.5 3h11a.5.5 0 0 1 0 1h-11A.5.5 0 0 1 2 3.5Zm0 4A.5.5 0 0 1 2.5 7h11a.5.5 0 0 1 0 1h-11A.5.5 0 0 1 2 7.5Zm0 4A.5.5 0 0 1 2.5 11h11a.5.5 0 0 1 0 1h-11A.5.5 0 0 1 2 11.5Z" clip-rule="evenodd"/></svg>
          {{ floorView ? t('waiterPage.listViewToggle') : t('waiterPage.tabFloor') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
// Status-tab bar + action toolbar of WaiterPage.vue, extracted as a standalone
// child (RISK FE-2). It renders the status tabs (+ recent / shift), the sound
// toggle, clock-in/out, charge-wallet, new-order and floor/list-view controls.
//
// Read/write state round-trips via v-model: `activeTab` (regular + recent tabs set
// it directly; the shift tab emits `selectShift` since the parent's openShiftSummary
// also loads the summary), `soundOn` (waiterSoundOn), and `floorView`. Everything
// else stays in the parent: `tabs` / `currentShift` / `clockBusy` / `shiftElapsed` /
// `formatDateTime` are props, and the actions are emits — `selectShift`, `clock`
// (payload 'in'|'out'), `charge`, `newOrder` (the parent keeps the clock-in guard +
// toast). The tablist arrow-key focus nav is self-contained here (it focuses the
// waiter-tab-<key> buttons by id).
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

const activeTab = defineModel('activeTab', { type: String, default: '' });
const soundOn = defineModel('soundOn', { type: Boolean, default: true });
const floorView = defineModel('floorView', { type: Boolean, default: false });

defineProps({
  /** The status-tab descriptors ({ key, label, count }). */
  tabs: { type: Array, default: () => [] },
  /** Whether the waiter can manage orders (gates the action buttons). */
  canManage: { type: Boolean, default: false },
  /** The current open shift, or null (drives clock-in vs clock-out). */
  currentShift: { type: Object, default: null },
  /** True while a clock-in/out request is in flight. */
  clockBusy: { type: Boolean, default: false },
  /** Pre-formatted elapsed-since-clock-in string, or ''. */
  shiftElapsed: { type: String, default: '' },
  /** Date-time formatter (value) => string, for the clocked-in-since title. */
  formatDateTime: { type: Function, required: true },
});

const emit = defineEmits(['selectShift', 'clock', 'charge', 'newOrder']);

// Tablist arrow-key focus nav (self-contained — focuses the waiter-tab-<key> buttons).
const _allTabKeys = ["needs_action", "all", "pending", "confirmed", "preparing", "ready", "unpaid", "recent", "shift"];
const _focusTabByKey = (key) => {
  const el = document.getElementById(`waiter-tab-${key}`);
  el?.focus();
};
const focusPrevTab = () => {
  const idx = _allTabKeys.indexOf(activeTab.value);
  const prev = _allTabKeys[(idx - 1 + _allTabKeys.length) % _allTabKeys.length];
  _focusTabByKey(prev);
};
const focusNextTab = () => {
  const idx = _allTabKeys.indexOf(activeTab.value);
  const next = _allTabKeys[(idx + 1) % _allTabKeys.length];
  _focusTabByKey(next);
};
</script>
