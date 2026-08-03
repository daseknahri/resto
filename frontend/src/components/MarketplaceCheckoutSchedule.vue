<template>
  <!-- When: ASAP vs scheduled -->
  <div>
    <p class="text-xs font-medium text-slate-400 mb-1.5">{{ t('mktMenu.whenTitle') }}</p>
    <div class="grid grid-cols-2 gap-2">
      <button
        type="button"
        class="rounded-xl border px-3 py-2.5 text-xs font-semibold transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
        :class="!scheduleEnabled ? 'border-emerald-500/55 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-600'"
        :aria-pressed="!scheduleEnabled"
        @click="scheduleEnabled = false"
      >{{ t('mktMenu.scheduleAsap') }}</button>
      <button
        type="button"
        class="rounded-xl border px-3 py-2.5 text-xs font-semibold transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
        :class="scheduleEnabled ? 'border-emerald-500/55 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-600'"
        :aria-pressed="scheduleEnabled"
        @click="scheduleEnabled = true"
      >{{ t('mktMenu.scheduleLater') }}</button>
    </div>
    <input
      v-if="scheduleEnabled"
      v-model="scheduledFor"
      type="datetime-local"
      :min="minScheduleDatetime"
      class="ui-input mt-2"
      :aria-label="t('mktMenu.scheduleLater')"
    />
    <p v-if="scheduleEnabled" class="mt-1 text-[11px] text-slate-500">{{ t('mktMenu.scheduleHint') }}</p>
  </div>
</template>

<script setup>
// The "when" (ASAP vs scheduled) picker of MarketplaceMenuPage.vue's checkout
// drawer, extracted as a small child (RISK FE-2) — sub-part 3 of the checkout-drawer
// split. Two-way models: `scheduleEnabled` toggles the datetime input, and
// `scheduledFor` holds the chosen time; `minScheduleDatetime` (the earliest bookable
// slot) is a prop. No logic here — the parent keeps everything downstream.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

/** Whether a later time is being scheduled (scheduleEnabled), two-way. */
const scheduleEnabled = defineModel('scheduleEnabled', { type: Boolean, default: false });
/** The chosen datetime-local value (scheduledFor), two-way. */
const scheduledFor = defineModel('scheduledFor', { type: String, default: '' });

defineProps({
  /** Earliest selectable datetime (minScheduleDatetime) for the input's `min`. */
  minScheduleDatetime: { type: String, default: '' },
});
</script>
